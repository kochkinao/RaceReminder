from datetime import date

import utils
from utils.rscg import RscgStage


def _session() -> dict:
    return {
        "id": "session-1",
        "name": "Grand Prix",
        "start": 1779091200,
        "durationMinutes": 90,
        "status": 1,
        "notes": "Night race",
        "location": {
            "alternateName": "Test Circuit",
            "country": "Italy",
            "regionName": "Monza",
            "lat": 45.6156,
            "lon": 9.2811,
        },
        "series": [
            {
                "id": "series-1",
                "name": "Formula Test",
                "vehicleClasses": [{"id": "class-1", "name": "GT3"}],
            }
        ],
    }


def test_session_card_returns_none_when_hidden_and_no_media() -> None:
    card = utils.session_card(
        _session(),
        broadcasts=[],
        live_timings=[],
        user_tz="Europe/Moscow",
        user_langs=["English"],
        show_no_bc=False,
    )
    assert card is None


def test_session_card_includes_matching_broadcasts_and_live_timings() -> None:
    card = utils.session_card(
        _session(),
        broadcasts=[
            {"description": "English Stream", "url": "https://example.com", "langIds": ["English"], "type": 3},
            {"description": "German Stream", "url": "https://example.org", "langIds": ["German"], "type": 3},
        ],
        live_timings=[{"description": "Official Timing", "url": "https://timing.example"}],
        user_tz="Europe/Moscow",
        user_langs=["English"],
    )

    assert card is not None
    assert "English Stream" in card
    assert "German Stream" not in card
    assert "Official Timing" in card
    assert "Test Circuit" in card


def test_build_digest_splits_long_messages() -> None:
    sessions = []
    for idx in range(40):
        s = _session() | {"id": f"session-{idx}", "name": f"Grand Prix {idx}"}
        sessions.append(s)

    messages = utils.build_digest(
        sessions=sessions,
        broadcasts_map={},
        timings_map={},
        user_tz="Europe/Moscow",
        user_langs=["English"],
        header="Header",
    )

    assert len(messages) > 1
    assert all(len(message) <= 3800 for message in messages)


def test_notification_text_uses_label_and_card() -> None:
    text = utils.notification_text(
        _session(),
        broadcasts=[],
        live_timings=[],
        user_tz="Europe/Moscow",
        user_langs=["English"],
        notif_type="1hour",
    )

    assert text.startswith("🚨 Через час")
    assert "Grand Prix" in text


def test_rscg_notification_text_is_localized_for_english() -> None:
    stage = RscgStage(
        id=64,
        round=1,
        date_start=date(2026, 5, 15),
        date_end=date(2026, 5, 17),
        track="Moscow Raceway",
        location="Moscow Region",
        description="Season opener",
        sprint="Touring classes",
        endurance=None,
        additional=None,
        note=None,
        image_url=None,
        ticket_url=None,
        info_url=None,
    )

    text = utils.rscg_notification_text(stage, "start", ui_lang="en")

    assert text.startswith("🏁 Starts Today")
    assert "SMP RSKG — Round 1" in text
