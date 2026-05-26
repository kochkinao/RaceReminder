import utils
from datetime import datetime, timezone


def test_resolve_timezone_input_matches_alias_and_suffix() -> None:
    assert utils.resolve_timezone_input("Samara") == ["Europe/Samara"]
    assert utils.resolve_timezone_input("Europe/Samara") == ["Europe/Samara"]


def test_group_sessions_by_event_clusters_same_weekend() -> None:
    base = {
        "series": [{"name": "Formula 1"}],
        "location": {"name": "Monaco", "id": "track-1"},
    }
    fp = {**base, "id": "s1", "name": "Practice 1", "start": 1770000000}
    race = {**base, "id": "s2", "name": "Race", "start": 1770172800}

    mapping = utils.map_sessions_to_events([fp, race])
    assert mapping["s1"]["event_key"] == mapping["s2"]["event_key"]


def test_group_sessions_by_event_keeps_key_stable_for_same_weekend_subset() -> None:
    base = {
        "series": [{"name": "Formula 1"}],
        "location": {"name": "Monaco", "id": "track-1"},
    }
    practice = {
        **base,
        "id": "s1",
        "name": "Practice 1",
        "start": int(datetime(2026, 5, 28, 10, 0, tzinfo=timezone.utc).timestamp()),
    }
    race = {
        **base,
        "id": "s2",
        "name": "Race",
        "start": int(datetime(2026, 5, 31, 13, 0, tzinfo=timezone.utc).timestamp()),
    }

    full_mapping = utils.map_sessions_to_events([practice, race])
    partial_mapping = utils.map_sessions_to_events([race])

    assert full_mapping["s2"]["event_key"] == partial_mapping["s2"]["event_key"]
