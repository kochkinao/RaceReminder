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
