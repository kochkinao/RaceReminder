import utils


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
