from handlers import digest


def _session(session_id: str, name: str, series_id: str = "series-1", class_id: str = "class-1") -> dict:
    return {
        "id": session_id,
        "name": name,
        "series": [
            {
                "id": series_id,
                "name": "Series",
                "vehicleClasses": [{"id": class_id, "name": "Class"}],
            }
        ],
    }


def test_history_filter_sessions_by_status() -> None:
    sessions = [
        _session("1", "Main Race"),
        _session("2", "Qualifying"),
        _session("3", "Free Practice 1"),
    ]

    assert [s["id"] for s in digest._history_filter_sessions(sessions, "race")] == ["1"]
    assert [s["id"] for s in digest._history_filter_sessions(sessions, "qualifying")] == ["2"]
    assert [s["id"] for s in digest._history_filter_sessions(sessions, "practice")] == ["3"]


def test_history_filter_sessions_by_series_and_class() -> None:
    sessions = [
        _session("1", "Main Race", series_id="series-1", class_id="class-1"),
        _session("2", "Main Race", series_id="series-2", class_id="class-2"),
    ]

    assert [s["id"] for s in digest._history_filter_sessions(sessions, "series", "series-2")] == ["2"]
    assert [s["id"] for s in digest._history_filter_sessions(sessions, "vehicle_class", "class-1")] == ["1"]
