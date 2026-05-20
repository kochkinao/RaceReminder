"""
Database layer.

Optimizations vs initial version:
  - Single persistent aiosqlite connection (not open/close per query)
  - Batch methods for scheduler: get_all_subscriptions(), get_all_sent_notifications()
  - write_notifications_batch() for bulk INSERT
  - _execute_many() for batch writes
"""
import json
import logging
from typing import Any

import aiosqlite

from config import DATABASE_PATH

log = logging.getLogger(__name__)

type Row = dict[str, Any]


class Database:

    def __init__(self, path: str = DATABASE_PATH) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript("""
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;
            PRAGMA synchronous  = NORMAL;
            PRAGMA cache_size   = -8000;

            CREATE TABLE IF NOT EXISTS users (
                chat_id           INTEGER PRIMARY KEY,
                username          TEXT,
                timezone          TEXT    NOT NULL DEFAULT 'Europe/Moscow',
                preferred_langs   TEXT    NOT NULL DEFAULT '["English"]',
                digest_enabled    INTEGER NOT NULL DEFAULT 1,
                digest_time       TEXT    NOT NULL DEFAULT '08:00',
                quiet_enabled     INTEGER NOT NULL DEFAULT 1,
                quiet_start       INTEGER NOT NULL DEFAULT 23,
                quiet_end         INTEGER NOT NULL DEFAULT 7,
                show_no_broadcast INTEGER NOT NULL DEFAULT 1,
                notify_3days      INTEGER NOT NULL DEFAULT 1,
                notify_1day       INTEGER NOT NULL DEFAULT 1,
                notify_1hour      INTEGER NOT NULL DEFAULT 1,
                notify_start      INTEGER NOT NULL DEFAULT 0,
                created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                type        TEXT    NOT NULL CHECK(type IN ('series','vehicle_class')),
                ref_id      TEXT    NOT NULL,
                ref_name    TEXT    NOT NULL DEFAULT '',
                qual_notify INTEGER NOT NULL DEFAULT 1,
                UNIQUE(chat_id, type, ref_id)
            );

            CREATE TABLE IF NOT EXISTS sent_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                session_id  TEXT    NOT NULL,
                notif_type  TEXT    NOT NULL,
                sent_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(chat_id, session_id, notif_type)
            );

            CREATE TABLE IF NOT EXISTS favorites (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id      INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                session_id   TEXT    NOT NULL,
                session_name TEXT    NOT NULL DEFAULT '',
                added_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(chat_id, session_id)
            );

            CREATE TABLE IF NOT EXISTS api_cache (
                key       TEXT PRIMARY KEY,
                value     TEXT NOT NULL,
                cached_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        await self._conn.commit()
        log.info("Database ready: %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    @property
    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() was not called")
        return self._conn

    async def _fetchone(self, sql: str, params: tuple = ()) -> Row | None:
        async with self._db.execute(sql, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[Row]:
        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def _execute(self, sql: str, params: tuple = ()) -> None:
        await self._db.execute(sql, params)
        await self._db.commit()

    async def _execute_many(self, sql: str, params_seq: list[tuple]) -> None:
        await self._db.executemany(sql, params_seq)
        await self._db.commit()

    # ── Users ─────────────────────────────────────────────────────────────────

    async def get_user(self, chat_id: int) -> Row | None:
        return await self._fetchone("SELECT * FROM users WHERE chat_id=?", (chat_id,))

    async def user_exists(self, chat_id: int) -> bool:
        return await self.get_user(chat_id) is not None

    async def create_user(self, chat_id: int, username: str | None = None) -> Row:
        await self._execute(
            "INSERT OR IGNORE INTO users (chat_id, username) VALUES (?,?)",
            (chat_id, username),
        )
        return await self.get_user(chat_id)  # type: ignore[return-value]

    async def update_user(self, chat_id: int, **fields: Any) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        await self._execute(
            f"UPDATE users SET {sets} WHERE chat_id=?",
            (*fields.values(), chat_id),
        )

    async def get_all_users(self) -> list[Row]:
        return await self._fetchall("SELECT * FROM users")

    # ── Subscriptions ─────────────────────────────────────────────────────────

    async def get_subscriptions(self, chat_id: int) -> list[Row]:
        return await self._fetchall(
            "SELECT * FROM subscriptions WHERE chat_id=? ORDER BY type, ref_name",
            (chat_id,),
        )

    async def has_subscriptions(self, chat_id: int) -> bool:
        return bool(await self.get_subscriptions(chat_id))

    async def add_subscription(
        self, chat_id: int, type_: str, ref_id: str, ref_name: str = ""
    ) -> None:
        await self._execute(
            "INSERT OR IGNORE INTO subscriptions (chat_id,type,ref_id,ref_name) VALUES (?,?,?,?)",
            (chat_id, type_, ref_id, ref_name),
        )

    async def remove_subscription(self, chat_id: int, type_: str, ref_id: str) -> None:
        await self._execute(
            "DELETE FROM subscriptions WHERE chat_id=? AND type=? AND ref_id=?",
            (chat_id, type_, ref_id),
        )

    async def is_subscribed(self, chat_id: int, type_: str, ref_id: str) -> bool:
        return await self._fetchone(
            "SELECT 1 FROM subscriptions WHERE chat_id=? AND type=? AND ref_id=?",
            (chat_id, type_, ref_id),
        ) is not None

    async def set_qual_notify(self, chat_id: int, ref_id: str, value: bool) -> None:
        await self._execute(
            "UPDATE subscriptions SET qual_notify=? WHERE chat_id=? AND ref_id=?",
            (int(value), chat_id, ref_id),
        )

    # ── Batch subscriptions (scheduler) ──────────────────────────────────────

    async def get_all_subscriptions(self) -> dict[int, list[Row]]:
        """
        One query for all users.
        Returns {chat_id: [subscription_rows]}.
        """
        rows = await self._fetchall(
            "SELECT * FROM subscriptions ORDER BY chat_id, type, ref_name"
        )
        result: dict[int, list[Row]] = {}
        for row in rows:
            result.setdefault(row["chat_id"], []).append(row)
        return result

    # ── Notifications ─────────────────────────────────────────────────────────

    async def was_notified(self, chat_id: int, session_id: str, notif_type: str) -> bool:
        return await self._fetchone(
            "SELECT 1 FROM sent_notifications WHERE chat_id=? AND session_id=? AND notif_type=?",
            (chat_id, session_id, notif_type),
        ) is not None

    async def mark_notified(self, chat_id: int, session_id: str, notif_type: str) -> None:
        await self._execute(
            "INSERT OR IGNORE INTO sent_notifications (chat_id,session_id,notif_type) VALUES (?,?,?)",
            (chat_id, session_id, notif_type),
        )

    # ── Batch notifications (scheduler) ──────────────────────────────────────

    async def get_all_sent_notifications(self) -> set[tuple[int, str, str]]:
        """
        One query → set of (chat_id, session_id, notif_type).
        Scheduler uses this to check without hitting DB per pair.
        """
        rows = await self._fetchall(
            "SELECT chat_id, session_id, notif_type FROM sent_notifications"
        )
        return {(r["chat_id"], r["session_id"], r["notif_type"]) for r in rows}

    async def mark_notified_batch(
        self, items: list[tuple[int, str, str]]
    ) -> None:
        """Bulk-insert (chat_id, session_id, notif_type) tuples."""
        if not items:
            return
        await self._execute_many(
            "INSERT OR IGNORE INTO sent_notifications (chat_id,session_id,notif_type) VALUES (?,?,?)",
            items,
        )

    # ── Favorites ─────────────────────────────────────────────────────────────

    async def get_favorites(self, chat_id: int) -> list[Row]:
        return await self._fetchall(
            "SELECT * FROM favorites WHERE chat_id=? ORDER BY added_at DESC",
            (chat_id,),
        )

    async def add_favorite(
        self, chat_id: int, session_id: str, session_name: str = ""
    ) -> None:
        await self._execute(
            "INSERT OR IGNORE INTO favorites (chat_id,session_id,session_name) VALUES (?,?,?)",
            (chat_id, session_id, session_name),
        )

    async def remove_favorite(self, chat_id: int, session_id: str) -> None:
        await self._execute(
            "DELETE FROM favorites WHERE chat_id=? AND session_id=?",
            (chat_id, session_id),
        )

    async def is_favorite(self, chat_id: int, session_id: str) -> bool:
        return await self._fetchone(
            "SELECT 1 FROM favorites WHERE chat_id=? AND session_id=?",
            (chat_id, session_id),
        ) is not None

    # ── API cache ─────────────────────────────────────────────────────────────

    async def set_cache(self, key: str, value: Any) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO api_cache (key,value,cached_at) VALUES (?,?,datetime('now'))",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    async def get_cache(self, key: str, max_age_seconds: int = 3_600) -> Any:
        row = await self._fetchone(
            """SELECT value FROM api_cache
               WHERE key=?
               AND (julianday('now') - julianday(cached_at)) * 86400 < ?""",
            (key, max_age_seconds),
        )
        return json.loads(row["value"]) if row else None

    async def clear_cache(self) -> None:
        await self._execute("DELETE FROM api_cache")
