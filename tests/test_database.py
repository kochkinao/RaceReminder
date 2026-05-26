from pathlib import Path

import pytest

import database
import utils


@pytest.fixture
async def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_db_path = tmp_path / "test_raceday.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(test_db_path))
    db = database.Database()
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_create_update_and_fetch_user(db: database.Database) -> None:
    user = await db.create_user(1001, "alex")
    assert user["chat_id"] == 1001
    assert user["username"] == "alex"

    await db.update_user(1001, timezone="Europe/Berlin", digest_enabled=1)
    updated = await db.get_user(1001)

    assert updated["timezone"] == "Europe/Berlin"
    assert updated["digest_enabled"] == 1
    assert updated["show_qualifying"] == 1
    assert updated["show_practice"] == 1

    events = await db.get_user_event_log(1001, limit=5)
    assert any(row["event_type"] == "user_settings_updated" for row in events)


@pytest.mark.asyncio
async def test_get_all_subscriptions_groups_by_user(db: database.Database) -> None:
    await db.create_user(1001, "u1")
    await db.create_user(1002, "u2")
    await db.add_subscription(1001, "series", "series-1", "Formula Test")
    await db.add_subscription(1001, "vehicle_class", "class-1", "GT3")
    await db.add_subscription(1002, "series", "series-2", "WEC")

    grouped = await db.get_all_subscriptions()

    assert len(grouped[1001]) == 2
    assert len(grouped[1002]) == 1
    assert {row["ref_id"] for row in grouped[1001]} == {"series-1", "class-1"}


@pytest.mark.asyncio
async def test_mark_notified_batch_and_get_all_sent_notifications(db: database.Database) -> None:
    await db.create_user(1001, "u1")
    await db.mark_notified_batch(
        [
            (1001, "session-1", "1hour"),
            (1001, "session-1", "start"),
            (1001, "session-1", "1hour"),
        ]
    )

    sent = await db.get_all_sent_notifications()

    assert (1001, "session-1", "1hour") in sent
    assert (1001, "session-1", "start") in sent
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_update_user_rejects_unknown_fields(db: database.Database) -> None:
    await db.create_user(1001, "u1")

    with pytest.raises(ValueError):
        await db.update_user(1001, unknown_field=1)


@pytest.mark.asyncio
async def test_schema_version_is_up_to_date(db: database.Database) -> None:
    row = await db._fetchone("SELECT version FROM schema_version LIMIT 1")
    assert row["version"] == database.LATEST_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_session_reminders_crud(db: database.Database) -> None:
    await db.create_user(1001, "u1")
    await db.add_session_reminder(1001, "session-1", "1hour", 1000)
    await db.add_session_reminder(1001, "session-1", "start", 2000)

    rows = await db.get_session_reminders(1001, "session-1")
    assert [row["remind_type"] for row in rows] == ["1hour", "start"]

    due = await db.get_due_session_reminders(1500)
    assert [(row["chat_id"], row["session_id"], row["remind_type"]) for row in due] == [
        (1001, "session-1", "1hour")
    ]

    await db.remove_session_reminder(1001, "session-1", "1hour")
    rows = await db.get_session_reminders(1001, "session-1")
    assert [row["remind_type"] for row in rows] == ["start"]


@pytest.mark.asyncio
async def test_user_counts_and_debug_queries(db: database.Database) -> None:
    await db.create_user(1001, "u1")
    await db.add_subscription(1001, "series", "series-1", "Formula Test")
    await db.add_favorite(1001, "session-1")
    await db.add_event_favorite(1001, "event-1", "Formula Test · Imola", 1000)
    await db.ignore_event(1001, "event-2", "Muted Weekend", 1100, 999999)
    await db.add_session_reminder(1001, "session-1", "1hour", 1000)
    await db.mark_notified_batch([(1001, "session-1", "1hour")])
    await db.log_event("custom_debug", 1001, {"ok": True})

    counts = await db.get_user_counts(1001)
    sent = await db.get_user_sent_notifications(1001, limit=5)
    events = await db.get_user_event_log(1001, limit=5)

    assert counts == {
        "subscriptions": 1,
        "favorites": 1,
        "event_favorites": 1,
        "ignored_events": 1,
        "reminders": 1,
        "sent_notifications": 1,
    }
    assert sent[0]["session_id"] == "session-1"
    assert events[0]["event_type"] == "custom_debug"


@pytest.mark.asyncio
async def test_event_favorites_and_ignored_events(db: database.Database) -> None:
    await db.create_user(1001, "u1")
    await db.add_event_favorite(1001, "event-a", "Weekend A", 200)
    await db.ignore_event(1001, "event-b", "Weekend B", 300, 5000)

    favorites = await db.get_event_favorites(1001)
    ignored = await db.get_ignored_events(1001, now_ts=1000)

    assert favorites[0]["event_key"] == "event-a"
    assert ignored[0]["event_key"] == "event-b"
    assert await db.is_event_favorite(1001, "event-a") is True
    assert await db.is_event_ignored(1001, "event-b", now_ts=1000) is True


@pytest.mark.asyncio
async def test_pending_deliveries_crud(db: database.Database) -> None:
    item = utils.PendingDelivery(
        kind="notification",
        chat_id=1001,
        text="hello",
        dedupe_key=("notification", 1001, "session-1", "1hour"),
        session_id="session-1",
        notif_type="1hour",
    )

    assert await db.enqueue_pending_delivery(item, delay_seconds=0) is True
    assert await db.has_pending_delivery(item.dedupe_key) is True
    assert await db.count_pending_deliveries() == 1

    due = await db.get_due_pending_deliveries(limit=10)
    assert len(due) == 1
    assert due[0].chat_id == 1001
    assert due[0].session_id == "session-1"

    due[0].attempts = 2
    due[0].last_error = "temporary"
    await db.requeue_pending_delivery(due[0], delay_seconds=60)
    assert await db.count_pending_deliveries() == 1

    await db.complete_pending_delivery(due[0])
    assert await db.count_pending_deliveries() == 0


@pytest.mark.asyncio
async def test_audit_log_tracks_real_user_actions_only(db: database.Database) -> None:
    await db.create_user(1001, "u1")
    await db.add_subscription(1001, "series", "series-1", "Formula Test")
    await db.update_subscription(1001, "series", "series-1", qualifying_notify=0)
    await db.update_subscription(1001, "series", "series-1", qualifying_notify=0)
    await db.add_event_favorite(1001, "event-1", "Weekend 1", 1000)
    await db.add_event_favorite(1001, "event-1", "Weekend 1", 1000)
    await db.ignore_event(1001, "event-2", "Weekend 2", 1100, 5000)
    await db.add_session_reminder(1001, "session-1", "1hour", 1000)
    await db.remove_session_reminder(1001, "session-1", "1hour")

    events = await db.get_user_event_log(1001, limit=20)
    event_types = [row["event_type"] for row in events]

    assert event_types.count("subscription_settings_updated") == 1
    assert event_types.count("event_favorite_added") == 1
    assert "event_ignored" in event_types
    assert "session_reminder_added" in event_types
    assert "session_reminder_removed" in event_types


@pytest.mark.asyncio
async def test_create_user_logs_created_only_once(db: database.Database) -> None:
    await db.create_user(1001, "u1")
    await db.create_user(1001, "u1")

    events = await db.get_user_event_log(1001, limit=10)
    event_types = [row["event_type"] for row in events]

    assert event_types.count("user_created") == 1
