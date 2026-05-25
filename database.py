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
import sqlite3
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
            PRAGMA mmap_size      = 268435456;
        """)
        await self._create_tables()
        await self._migrate_users_schema()
        await self._migrate_subscriptions_schema()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def _create_tables(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id           INTEGER PRIMARY KEY,
                username          TEXT,
                ui_lang           TEXT    NOT NULL DEFAULT 'ru',
                timezone          TEXT    NOT NULL DEFAULT 'Europe/Moscow',
                preferred_langs   TEXT    NOT NULL DEFAULT '["English"]',
                digest_enabled    INTEGER NOT NULL DEFAULT 0,
                digest_time       TEXT    NOT NULL DEFAULT '08:00',
                quiet_enabled     INTEGER NOT NULL DEFAULT 0,
                quiet_start       INTEGER NOT NULL DEFAULT 23,
                quiet_end         INTEGER NOT NULL DEFAULT 7,
                show_no_broadcast INTEGER NOT NULL DEFAULT 1,
                show_qualifying   INTEGER NOT NULL DEFAULT 1,
                show_practice     INTEGER NOT NULL DEFAULT 1,
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

            CREATE TABLE IF NOT EXISTS event_favorites (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                event_key  TEXT    NOT NULL,
                title      TEXT    NOT NULL DEFAULT '',
                sort_ts    INTEGER NOT NULL DEFAULT 0,
                added_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(chat_id, event_key)
            );

            CREATE TABLE IF NOT EXISTS ignored_events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id       INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                event_key     TEXT    NOT NULL,
                title         TEXT    NOT NULL DEFAULT '',
                sort_ts       INTEGER NOT NULL DEFAULT 0,
                expires_at_ts INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(chat_id, event_key)
            );

            CREATE TABLE IF NOT EXISTS session_reminders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id      INTEGER NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
                session_id   TEXT    NOT NULL,
                remind_type  TEXT    NOT NULL,
                remind_at_ts INTEGER NOT NULL,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(chat_id, session_id, remind_type)
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
            CREATE INDEX IF NOT EXISTS idx_event_favorites_chat ON event_favorites(chat_id);
            CREATE INDEX IF NOT EXISTS idx_ignored_events_chat ON ignored_events(chat_id);
            CREATE INDEX IF NOT EXISTS idx_ignored_events_expiry ON ignored_events(expires_at_ts);
            CREATE INDEX IF NOT EXISTS idx_reminders_due ON session_reminders(remind_at_ts);
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

    async def _migrate_users_schema(self) -> None:
        rows = await self._fetchall("PRAGMA table_info(users)")
        columns = {row["name"] for row in rows}

        if "show_qualifying" not in columns:
            await self._db.execute(
                "ALTER TABLE users ADD COLUMN show_qualifying INTEGER NOT NULL DEFAULT 1"
            )

        if "ui_lang" not in columns:
            await self._db.execute(
                "ALTER TABLE users ADD COLUMN ui_lang TEXT NOT NULL DEFAULT 'ru'"
            )

        if "show_practice" not in columns:
            await self._db.execute(
                "ALTER TABLE users ADD COLUMN show_practice INTEGER NOT NULL DEFAULT 1"
            )

        await self._db.commit()

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

        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_subs_type ON subscriptions(type)"
        )

        await self._db.commit()

    # ── Users ─────────────────────────────────────────────────────────────────

    async def user_exists(self, chat_id: int) -> bool:
        row = await self._fetchone("SELECT 1 FROM users WHERE chat_id=?", (chat_id,))
        return row is not None

    async def get_user(self, chat_id: int) -> Row | None:
        return await self._fetchone("SELECT * FROM users WHERE chat_id=?", (chat_id,))

    async def get_user_by_username(self, username: str) -> Row | None:
        return await self._fetchone(
            "SELECT * FROM users WHERE lower(username)=lower(?)",
            (username.lstrip("@"),),
        )

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

    async def get_user_counts(self, chat_id: int) -> dict[str, int]:
        rows = {
            "subscriptions": await self._fetchone(
                "SELECT COUNT(*) n FROM subscriptions WHERE chat_id=?", (chat_id,)
            ),
            "favorites": await self._fetchone(
                "SELECT COUNT(*) n FROM favorites WHERE chat_id=?", (chat_id,)
            ),
            "event_favorites": await self._fetchone(
                "SELECT COUNT(*) n FROM event_favorites WHERE chat_id=?", (chat_id,)
            ),
            "ignored_events": await self._fetchone(
                "SELECT COUNT(*) n FROM ignored_events WHERE chat_id=?", (chat_id,)
            ),
            "reminders": await self._fetchone(
                "SELECT COUNT(*) n FROM session_reminders WHERE chat_id=?", (chat_id,)
            ),
            "sent_notifications": await self._fetchone(
                "SELECT COUNT(*) n FROM sent_notifications WHERE chat_id=?", (chat_id,)
            ),
        }
        return {k: (v["n"] if v else 0) for k, v in rows.items()}

    async def get_user_sent_notifications(self, chat_id: int, limit: int = 10) -> list[Row]:
        return await self._fetchall(
            "SELECT session_id, notif_type, sent_at "
            "FROM sent_notifications WHERE chat_id=? "
            "ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        )

    async def get_user_event_log(self, chat_id: int, limit: int = 10) -> list[Row]:
        return await self._fetchall(
            "SELECT ts, event_type, payload FROM event_log WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        )

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

    async def remove_all_subscriptions(self, chat_id: int) -> None:
        await self._execute(
            "DELETE FROM subscriptions WHERE chat_id=?",
            (chat_id,),
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

    async def get_event_favorites(self, chat_id: int) -> list[Row]:
        return await self._fetchall(
            "SELECT * FROM event_favorites WHERE chat_id=? ORDER BY sort_ts DESC, added_at DESC",
            (chat_id,),
        )

    async def is_event_favorite(self, chat_id: int, event_key: str) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM event_favorites WHERE chat_id=? AND event_key=?",
            (chat_id, event_key),
        )
        return row is not None

    async def add_event_favorite(self, chat_id: int, event_key: str, title: str, sort_ts: int) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO event_favorites (chat_id, event_key, title, sort_ts) VALUES (?,?,?,?)",
            (chat_id, event_key, title, sort_ts),
        )

    async def remove_event_favorite(self, chat_id: int, event_key: str) -> None:
        await self._execute(
            "DELETE FROM event_favorites WHERE chat_id=? AND event_key=?",
            (chat_id, event_key),
        )

    async def get_ignored_events(self, chat_id: int, now_ts: int | None = None) -> list[Row]:
        sql = "SELECT * FROM ignored_events WHERE chat_id=?"
        params: list[Any] = [chat_id]
        if now_ts is not None:
            sql += " AND expires_at_ts>?"
            params.append(now_ts)
        sql += " ORDER BY sort_ts DESC, created_at DESC"
        return await self._fetchall(sql, tuple(params))

    async def is_event_ignored(self, chat_id: int, event_key: str, now_ts: int | None = None) -> bool:
        sql = "SELECT 1 FROM ignored_events WHERE chat_id=? AND event_key=?"
        params: list[Any] = [chat_id, event_key]
        if now_ts is not None:
            sql += " AND expires_at_ts>?"
            params.append(now_ts)
        row = await self._fetchone(sql, tuple(params))
        return row is not None

    async def ignore_event(
        self,
        chat_id: int,
        event_key: str,
        title: str,
        sort_ts: int,
        expires_at_ts: int,
    ) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO ignored_events (chat_id, event_key, title, sort_ts, expires_at_ts) VALUES (?,?,?,?,?)",
            (chat_id, event_key, title, sort_ts, expires_at_ts),
        )

    async def unignore_event(self, chat_id: int, event_key: str) -> None:
        await self._execute(
            "DELETE FROM ignored_events WHERE chat_id=? AND event_key=?",
            (chat_id, event_key),
        )

    async def cleanup_expired_ignored_events(self, now_ts: int) -> int:
        async with self._db.execute(
            "DELETE FROM ignored_events WHERE expires_at_ts<=?",
            (now_ts,),
        ) as cur:
            deleted = cur.rowcount
        await self._db.commit()
        return deleted

    # ── Session reminders ────────────────────────────────────────────────────

    async def get_session_reminders(self, chat_id: int, session_id: str) -> list[Row]:
        return await self._fetchall(
            "SELECT * FROM session_reminders WHERE chat_id=? AND session_id=? ORDER BY remind_at_ts",
            (chat_id, session_id),
        )

    async def add_session_reminder(
        self, chat_id: int, session_id: str, remind_type: str, remind_at_ts: int
    ) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO session_reminders (chat_id, session_id, remind_type, remind_at_ts) VALUES (?,?,?,?)",
            (chat_id, session_id, remind_type, remind_at_ts),
        )

    async def remove_session_reminder(
        self, chat_id: int, session_id: str, remind_type: str
    ) -> None:
        await self._execute(
            "DELETE FROM session_reminders WHERE chat_id=? AND session_id=? AND remind_type=?",
            (chat_id, session_id, remind_type),
        )

    async def get_due_session_reminders(self, now_ts: int) -> list[Row]:
        return await self._fetchall(
            "SELECT sr.* FROM session_reminders sr "
            "JOIN users u ON u.chat_id=sr.chat_id "
            "WHERE u.is_active=1 AND sr.remind_at_ts<=? "
            "ORDER BY sr.remind_at_ts, sr.id",
            (now_ts,),
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

    async def get_cache_stale(self, key: str, max_age_seconds: int) -> str | None:
        row = await self._fetchone(
            """SELECT value FROM api_cache
               WHERE key=?
               AND (julianday('now') - julianday(cached_at)) * 86400 < ?""",
            (key, max_age_seconds),
        )
        return row["value"] if row else None

    async def set_cache(self, key: str, value: str) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO api_cache (key, value, cached_at) VALUES (?,?,datetime('now'))",
            (key, value),
        )

    async def clear_cache(self) -> None:
        await self._execute("DELETE FROM api_cache")

    async def export_backup(self, target_path: str) -> None:
        target = sqlite3.connect(target_path)
        try:
            await self._db.backup(target)
        finally:
            target.close()
