"""
Database layer.

- Single persistent aiosqlite connection (WAL mode)
- Batch methods for scheduler
- Field whitelist in update_user (SQL injection prevention)
- User deactivation, event log, stats, cleanup
"""
from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from config import ALLOWED_USER_FIELDS, DATABASE_PATH, SENT_NOTIFICATIONS_TTL_DAYS

log = logging.getLogger(__name__)

Row = dict[str, Any]


class Database:
    def __init__(self) -> None:
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(DATABASE_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            PRAGMA journal_mode   = WAL;
            PRAGMA synchronous    = NORMAL;
            PRAGMA cache_size     = -8000;
            PRAGMA foreign_keys   = ON;
            PRAGMA temp_store     = MEMORY;
        """)
        await self._create_tables()
        await self._migrate_subscriptions_schema()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def _create_tables(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id           INTEGER PRIMARY KEY,
                username          TEXT,
                timezone          TEXT    NOT NULL DEFAULT 'Europe/Moscow',
                preferred_langs   TEXT    NOT NULL DEFAULT '["English"]',
                digest_enabled    INTEGER NOT NULL DEFAULT 0,
                digest_time       TEXT    NOT NULL DEFAULT '08:00',
                quiet_enabled     INTEGER NOT NULL DEFAULT 0,
                quiet_start       INTEGER NOT NULL DEFAULT 23,
                quiet_end         INTEGER NOT NULL DEFAULT 7,
                show_no_broadcast INTEGER NOT NULL DEFAULT 1,
                notify_3days      INTEGER NOT NULL DEFAULT 0,
                notify_1day       INTEGER NOT NULL DEFAULT 1,
                notify_1hour      INTEGER NOT NULL DEFAULT 1,
                notify_start      INTEGER NOT NULL DEFAULT 0,
                is_active         INTEGER NOT NULL DEFAULT 1,
                created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
                last_seen_at      TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id      INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                type         TEXT    NOT NULL,
                ref_id       TEXT    NOT NULL,
                ref_name     TEXT    NOT NULL DEFAULT '',
                qual_notify  INTEGER NOT NULL DEFAULT 1,
                UNIQUE(chat_id, type, ref_id)
            );

            CREATE TABLE IF NOT EXISTS sent_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL,
                session_id  TEXT    NOT NULL,
                notif_type  TEXT    NOT NULL,
                sent_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(chat_id, session_id, notif_type)
            );

            CREATE TABLE IF NOT EXISTS favorites (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                session_id TEXT    NOT NULL,
                added_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(chat_id, session_id)
            );

            CREATE TABLE IF NOT EXISTS api_cache (
                key       TEXT PRIMARY KEY,
                value     TEXT NOT NULL,
                cached_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS event_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT    NOT NULL DEFAULT (datetime('now')),
                event_type TEXT    NOT NULL,
                chat_id    INTEGER,
                payload    TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_subs_chat  ON subscriptions(chat_id);
            CREATE INDEX IF NOT EXISTS idx_sent_chat  ON sent_notifications(chat_id);
            CREATE INDEX IF NOT EXISTS idx_sent_ts    ON sent_notifications(sent_at);
            CREATE INDEX IF NOT EXISTS idx_log_type   ON event_log(event_type);
            CREATE INDEX IF NOT EXISTS idx_log_chat   ON event_log(chat_id);
        """)
        await self._db.commit()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _execute(self, sql: str, params: tuple = ()) -> None:
        await self._db.execute(sql, params)
        await self._db.commit()

    async def _execute_many(self, sql: str, params_list: list[tuple]) -> None:
        await self._db.executemany(sql, params_list)
        await self._db.commit()

    async def _fetchone(self, sql: str, params: tuple = ()) -> Row | None:
        async with self._db.execute(sql, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[Row]:
        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def _migrate_subscriptions_schema(self) -> None:
        rows = await self._fetchall("PRAGMA table_info(subscriptions)")
        columns = {row["name"] for row in rows}

        if "qualifying_notify" not in columns:
            await self._db.execute(
                "ALTER TABLE subscriptions ADD COLUMN qualifying_notify INTEGER NOT NULL DEFAULT 1"
            )
            await self._db.execute(
                "UPDATE subscriptions SET qualifying_notify = qual_notify"
            )

        if "practice_notify" not in columns:
            await self._db.execute(
                "ALTER TABLE subscriptions ADD COLUMN practice_notify INTEGER NOT NULL DEFAULT 1"
            )
            await self._db.execute(
                "UPDATE subscriptions SET practice_notify = qual_notify"
            )

        await self._db.commit()

    # ── Users ─────────────────────────────────────────────────────────────────

    async def user_exists(self, chat_id: int) -> bool:
        row = await self._fetchone("SELECT 1 FROM users WHERE chat_id=?", (chat_id,))
        return row is not None

    async def get_user(self, chat_id: int) -> Row | None:
        return await self._fetchone("SELECT * FROM users WHERE chat_id=?", (chat_id,))

    async def create_user(self, chat_id: int, username: str | None = None) -> Row:
        await self._execute(
            "INSERT OR IGNORE INTO users (chat_id, username) VALUES (?, ?)",
            (chat_id, username),
        )
        await self.log_event("user_created", chat_id)
        return await self._fetchone("SELECT * FROM users WHERE chat_id=?", (chat_id,))

    async def get_or_create_user(self, chat_id: int, username: str | None = None) -> Row:
        user = await self.get_user(chat_id)
        if not user:
            user = await self.create_user(chat_id, username)
        return user

    async def update_user(self, chat_id: int, **fields: Any) -> None:
        bad = set(fields) - ALLOWED_USER_FIELDS
        if bad:
            raise ValueError(f"update_user: disallowed fields: {bad}")
        sets = ", ".join(f"{k}=?" for k in fields)
        await self._execute(
            f"UPDATE users SET {sets}, last_seen_at=datetime('now') WHERE chat_id=?",
            (*fields.values(), chat_id),
        )

    async def touch_user(self, chat_id: int) -> None:
        await self._execute(
            "UPDATE users SET last_seen_at=datetime('now') WHERE chat_id=?", (chat_id,)
        )

    async def deactivate_user(self, chat_id: int) -> None:
        await self._execute("UPDATE users SET is_active=0 WHERE chat_id=?", (chat_id,))
        await self.log_event("user_blocked", chat_id)
        log.info("User deactivated (blocked bot): %d", chat_id)

    async def get_all_users(self, active_only: bool = True) -> list[Row]:
        sql = "SELECT * FROM users" + (" WHERE is_active=1" if active_only else "")
        return await self._fetchall(sql)

    async def get_stats(self) -> dict[str, Any]:
        rows = {
            "total":          await self._fetchone("SELECT COUNT(*) n FROM users"),
            "active":         await self._fetchone("SELECT COUNT(*) n FROM users WHERE is_active=1"),
            "new_today":      await self._fetchone("SELECT COUNT(*) n FROM users WHERE date(created_at)=date('now')"),
            "new_week":       await self._fetchone("SELECT COUNT(*) n FROM users WHERE created_at>=datetime('now','-7 days')"),
            "subs":           await self._fetchone("SELECT COUNT(*) n FROM subscriptions"),
            "notifs_last_24h": await self._fetchone("SELECT COUNT(*) n FROM sent_notifications WHERE sent_at>=datetime('now','-24 hours')"),
            "blocked":        await self._fetchone("SELECT COUNT(*) n FROM users WHERE is_active=0"),
        }
        return {k: (v["n"] if v else 0) for k, v in rows.items()}

    # ── Subscriptions ─────────────────────────────────────────────────────────

    async def get_subscriptions(self, chat_id: int) -> list[Row]:
        return await self._fetchall(
            "SELECT * FROM subscriptions WHERE chat_id=? ORDER BY type, ref_name",
            (chat_id,),
        )

    async def is_subscribed(self, chat_id: int, type_: str, ref_id: str) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM subscriptions WHERE chat_id=? AND type=? AND ref_id=?",
            (chat_id, type_, ref_id),
        )
        return row is not None

    async def add_subscription(
        self, chat_id: int, type_: str, ref_id: str, ref_name: str
    ) -> None:
        await self._execute(
            "INSERT OR IGNORE INTO subscriptions (chat_id, type, ref_id, ref_name) VALUES (?,?,?,?)",
            (chat_id, type_, ref_id, ref_name),
        )

    async def remove_subscription(self, chat_id: int, type_: str, ref_id: str) -> None:
        await self._execute(
            "DELETE FROM subscriptions WHERE chat_id=? AND type=? AND ref_id=?",
            (chat_id, type_, ref_id),
        )

    async def update_subscription(
        self,
        chat_id: int,
        type_: str,
        ref_id: str,
        **fields: Any,
    ) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        await self._execute(
            f"UPDATE subscriptions SET {sets} WHERE chat_id=? AND type=? AND ref_id=?",
            (*fields.values(), chat_id, type_, ref_id),
        )

    # ── Batch subscriptions (scheduler) ──────────────────────────────────────

    async def get_all_subscriptions(self) -> dict[int, list[Row]]:
        """
        One query for all users.
        Returns {chat_id: [subscription_rows]}.
        """
        rows = await self._fetchall(
            "SELECT s.* FROM subscriptions s "
            "JOIN users u ON u.chat_id=s.chat_id WHERE u.is_active=1 "
            "ORDER BY s.chat_id, s.type, s.ref_name"
        )
        result: dict[int, list[Row]] = {}
        for r in rows:
            result.setdefault(r["chat_id"], []).append(r)
        return result

    # ── Batch notifications (scheduler) ──────────────────────────────────────

    async def get_all_sent_notifications(self) -> set[tuple[int, str, str]]:
        """
        One query → set of (chat_id, session_id, notif_type).
        Scheduler uses this to check without hitting DB per pair.
        """
        rows = await self._fetchall(
            "SELECT sn.chat_id, sn.session_id, sn.notif_type "
            "FROM sent_notifications sn "
            "JOIN users u ON u.chat_id=sn.chat_id WHERE u.is_active=1"
        )
        return {(r["chat_id"], r["session_id"], r["notif_type"]) for r in rows}

    async def mark_notified_batch(
        self, items: list[tuple[int, str, str]]
    ) -> None:
        """Bulk-insert (chat_id, session_id, notif_type) tuples."""
        await self._execute_many(
            "INSERT OR IGNORE INTO sent_notifications (chat_id, session_id, notif_type) VALUES (?,?,?)",
            items,
        )

    async def cleanup_old_notifications(self) -> int:
        async with self._db.execute(
            "DELETE FROM sent_notifications WHERE sent_at < datetime('now', ?)",
            (f"-{SENT_NOTIFICATIONS_TTL_DAYS} days",),
        ) as cur:
            deleted = cur.rowcount
        await self._db.commit()
        if deleted:
            log.info("Cleaned %d old sent_notifications", deleted)
        return deleted

    # ── Favorites ─────────────────────────────────────────────────────────────

    async def get_favorites(self, chat_id: int) -> list[Row]:
        return await self._fetchall(
            "SELECT * FROM favorites WHERE chat_id=? ORDER BY added_at DESC",
            (chat_id,),
        )

    async def is_favorite(self, chat_id: int, session_id: str) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM favorites WHERE chat_id=? AND session_id=?",
            (chat_id, session_id),
        )
        return row is not None

    async def add_favorite(self, chat_id: int, session_id: str) -> None:
        await self._execute(
            "INSERT OR IGNORE INTO favorites (chat_id, session_id) VALUES (?,?)",
            (chat_id, session_id),
        )

    async def remove_favorite(self, chat_id: int, session_id: str) -> None:
        await self._execute(
            "DELETE FROM favorites WHERE chat_id=? AND session_id=?",
            (chat_id, session_id),
        )

    # ── Event log ─────────────────────────────────────────────────────────────

    async def log_event(
        self, event_type: str,
        chat_id: int | None = None,
        payload: dict | None = None,
    ) -> None:
        await self._execute(
            "INSERT INTO event_log (event_type,chat_id,payload) VALUES (?,?,?)",
            (event_type, chat_id,
             json.dumps(payload, ensure_ascii=False) if payload else None),
        )

    async def get_recent_events(self, limit: int = 50) -> list[Row]:
        return await self._fetchall(
            "SELECT * FROM event_log ORDER BY id DESC LIMIT ?", (limit,)
        )

    # ── API cache ─────────────────────────────────────────────────────────────

    async def get_cache(self, key: str, ttl_seconds: int) -> str | None:
        row = await self._fetchone(
            """SELECT value FROM api_cache
               WHERE key=?
               AND (julianday('now') - julianday(cached_at)) * 86400 < ?""",
            (key, ttl_seconds),
        )
        return row["value"] if row else None

    async def set_cache(self, key: str, value: str) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO api_cache (key, value, cached_at) VALUES (?,?,datetime('now'))",
            (key, value),
        )

    async def clear_cache(self) -> None:
        await self._execute("DELETE FROM api_cache")
