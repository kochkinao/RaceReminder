import handlers.session_details as session_details
import utils


async def test_load_session_context_merges_windows_and_deduplicates(monkeypatch) -> None:
    target_session = {
        "id": "session-42",
        "name": "Main Race",
        "series": [],
    }

    async def fake_get_sessions(mem, db, start, end):
        if start == 1:
            return [target_session]
        return []

    async def fake_get_broadcasts(mem, db, start):
        return [
            {"id": "bc-1", "session": {"id": "session-42"}, "description": "A"},
            {"id": "bc-1", "session": {"id": "session-42"}, "description": "A"},
        ]

    async def fake_get_live_timings(session_id):
        return [{"description": "Live", "url": "https://example.com"}]

    monkeypatch.setattr(session_details.utils, "history_window", lambda: (1, 2))
    monkeypatch.setattr(session_details.utils, "today_window", lambda: (3, 4))
    monkeypatch.setattr(session_details.utils, "week_window", lambda: (5, 6))
    monkeypatch.setattr(session_details.utils, "notify_window", lambda: (7, 8))
    monkeypatch.setattr(session_details.utils, "get_sessions", fake_get_sessions)
    monkeypatch.setattr(session_details.utils, "get_broadcasts", fake_get_broadcasts)
    monkeypatch.setattr(session_details.utils, "get_live_timings", fake_get_live_timings)

    session, broadcasts, live_timings = await utils.load_session_context(
        db=None,
        mem=None,
        session_id="session-42",
    )

    assert session == target_session
    assert len(broadcasts) == 1
    assert live_timings == [{"description": "Live", "url": "https://example.com"}]


async def test_migrate_legacy_favorites_to_event_level() -> None:
    class FakeDb:
        def __init__(self) -> None:
            self.saved: list[tuple[int, str, str, int]] = []

        async def get_favorites(self, chat_id: int):
            return [{"session_id": "session-42"}]

        async def add_event_favorite(self, chat_id: int, event_key: str, title: str, sort_ts: int):
            self.saved.append((chat_id, event_key, title, sort_ts))

    fake_db = FakeDb()
    await session_details._migrate_legacy_favorites(
        1001,
        fake_db,
        {
            "session-42": {
                "event_key": "event-42",
                "title": "Formula Test · Imola · 01.06.2026",
                "sort_ts": 1234,
            }
        },
    )

    assert fake_db.saved == [(1001, "event-42", "Formula Test · Imola · 01.06.2026", 1234)]
