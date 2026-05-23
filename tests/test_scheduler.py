from datetime import datetime, timezone

import scheduler


def _session(name: str = "Main Race") -> dict:
    return {
        "id": "session-1",
        "name": name,
        "series": [
            {
                "id": "series-1",
                "name": "Formula Test",
                "vehicleClasses": [{"id": "class-1", "name": "GT3"}],
            }
        ],
    }


def test_allows_session_type_for_race() -> None:
    assert scheduler._allows_session_type(_session("Main Race"), []) is True


def test_allows_session_type_uses_subscription_flags() -> None:
    subs = [
        {
            "type": "series",
            "ref_id": "series-1",
            "qualifying_notify": 0,
            "practice_notify": 1,
            "qual_notify": 0,
        }
    ]

    assert scheduler._allows_session_type(_session("Qualifying"), subs) is False
    assert scheduler._allows_session_type(_session("Free Practice 1"), subs) is True


def test_allows_session_type_falls_back_to_legacy_qual_notify() -> None:
    subs = [{"type": "series", "ref_id": "series-1", "qual_notify": 1}]
    assert scheduler._allows_session_type(_session("Hyperpole"), subs) is True


def test_in_quiet_hours_handles_cross_midnight_window() -> None:
    user = {
        "quiet_enabled": 1,
        "quiet_start": 23,
        "quiet_end": 7,
        "timezone": "Europe/Moscow",
    }

    inside = int(datetime(2026, 5, 19, 21, 30, tzinfo=timezone.utc).timestamp())  # 00:30 MSK
    outside = int(datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc).timestamp())  # 15:00 MSK

    assert scheduler._in_quiet_hours(inside, user) is True
    assert scheduler._in_quiet_hours(outside, user) is False


def test_digest_due_now_uses_local_monday_and_digest_time() -> None:
    user = {"timezone": "Europe/Moscow", "digest_time": "08:00"}

    due = int(datetime(2026, 5, 18, 5, 2, tzinfo=timezone.utc).timestamp())  # 08:02 MSK Monday
    not_due = int(datetime(2026, 5, 18, 5, 6, tzinfo=timezone.utc).timestamp())  # 08:06 MSK Monday
    wrong_day = int(datetime(2026, 5, 19, 5, 2, tzinfo=timezone.utc).timestamp())  # Tuesday

    assert scheduler._digest_due_now(due, user) is True
    assert scheduler._digest_due_now(not_due, user) is False
    assert scheduler._digest_due_now(wrong_day, user) is False


async def test_notifications_job_uses_each_users_ui_language(monkeypatch) -> None:
    fixed_now = 1_800_000_000
    sent_texts: list[str] = []

    class FakeDb:
        async def get_all_users(self, active_only: bool = True):
            return [
                {
                    "chat_id": 1,
                    "timezone": "Europe/Moscow",
                    "preferred_langs": '["English"]',
                    "ui_lang": "en",
                    "notify_1day": 1,
                    "notify_1hour": 0,
                    "notify_3days": 0,
                    "notify_start": 0,
                    "show_no_broadcast": 1,
                    "quiet_enabled": 0,
                },
                {
                    "chat_id": 2,
                    "timezone": "Europe/Moscow",
                    "preferred_langs": '["English"]',
                    "ui_lang": "ru",
                    "notify_1day": 1,
                    "notify_1hour": 0,
                    "notify_3days": 0,
                    "notify_start": 0,
                    "show_no_broadcast": 1,
                    "quiet_enabled": 0,
                },
            ]

        async def get_all_subscriptions(self):
            return {
                1: [{"type": "series", "ref_id": "series-1"}],
                2: [{"type": "series", "ref_id": "series-1"}],
            }

        async def get_all_sent_notifications(self):
            return set()

    class FakeState:
        http_session = None

        def mark_job_success(self, *_args, **_kwargs):
            return None

        def mark_job_failure(self, *_args, **_kwargs):
            return None

    class FakeMetrics:
        class Counter:
            def inc(self, *_args, **_kwargs):
                return None

        api_requests = Counter()
        api_errors = Counter()
        notifications_sent = Counter()
        notifications_failed = Counter()
        digests_sent = Counter()
        blocked_users = Counter()

        def record_error(self, *_args, **_kwargs):
            return None

    session = {
        "id": "session-1",
        "name": "Main Race",
        "start": fixed_now + scheduler.NOTIFICATION_OFFSETS["1day"],
        "series": [
            {
                "id": "series-1",
                "name": "Formula Test",
                "vehicleClasses": [],
            }
        ],
    }

    async def fake_get_sessions(mem, db, http_session, start, end):
        return [session]

    async def fake_get_broadcasts(mem, db, http_session, start):
        return []

    async def fake_process_delivery(bot, db, metrics, item, *, allow_queue):
        sent_texts.append(item.text)
        return True

    monkeypatch.setattr(scheduler.time, "time", lambda: fixed_now)
    monkeypatch.setattr(scheduler.utils, "get_sessions", fake_get_sessions)
    monkeypatch.setattr(scheduler.utils, "get_broadcasts", fake_get_broadcasts)
    monkeypatch.setattr(scheduler.utils, "broadcasts_by_session", lambda rows: {})
    monkeypatch.setattr(scheduler, "_process_delivery", fake_process_delivery)
    monkeypatch.setattr(scheduler.utils.delivery_queue, "has", lambda _key: False)

    await scheduler._notifications_job(
        bot=None,
        db=FakeDb(),
        mem=None,
        metrics=FakeMetrics(),
        state=FakeState(),
    )

    assert len(sent_texts) == 2
    assert any(text.startswith("🔔 Tomorrow") for text in sent_texts)
    assert any(text.startswith("🔔 Завтра") for text in sent_texts)
