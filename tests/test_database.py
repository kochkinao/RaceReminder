from pathlib import Path

import pytest

import database


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
