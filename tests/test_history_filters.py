from datetime import date
from types import SimpleNamespace

from handlers import digest
from utils.rscg import RscgStage
import utils


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


def test_digest_filter_sessions_respects_practice_and_qualifying_flags() -> None:
    sessions = [
        _session("1", "Main Race"),
        _session("2", "Qualifying"),
        _session("3", "Free Practice 1"),
    ]
    subs = [{
        "type": "series",
        "ref_id": "series-1",
        "ref_name": "Series",
        "qualifying_notify": 0,
        "practice_notify": 1,
        "qual_notify": 0,
    }]

    user = {"show_qualifying": 1, "show_practice": 0}
    assert [s["id"] for s in digest._filter_digest_sessions(sessions, subs, user)] == ["1"]


def test_digest_filter_sessions_uses_selected_subscription() -> None:
    sessions = [
        _session("1", "Main Race", series_id="series-1", class_id="class-1"),
        _session("2", "Main Race", series_id="series-2", class_id="class-2"),
    ]
    subs = [
        {"type": "series", "ref_id": "series-1", "ref_name": "Series 1", "qualifying_notify": 1, "practice_notify": 1, "qual_notify": 1},
        {"type": "series", "ref_id": "series-2", "ref_name": "Series 2", "qualifying_notify": 1, "practice_notify": 1, "qual_notify": 1},
    ]

    user = {"show_qualifying": 1, "show_practice": 1}
    assert [s["id"] for s in digest._filter_digest_sessions(sessions, subs, user, selected_sub=subs[1])] == ["2"]


def test_profile_menu_contains_subscription_notify_entry() -> None:
    kb = utils.profile_menu({
        "timezone": "Europe/Moscow",
        "digest_enabled": 1,
        "digest_time": "08:00",
        "show_no_broadcast": 1,
        "show_qualifying": 1,
        "show_practice": 1,
        "quiet_enabled": 0,
        "quiet_start": 23,
        "quiet_end": 7,
        "notify_3days": 0,
        "notify_1day": 1,
        "notify_1hour": 1,
        "notify_start": 0,
    })

    assert any(
        button.callback_data == "subs:notify"
        for row in kb.inline_keyboard
        for button in row
    )


def test_digest_view_menu_uses_back_button_for_selected_subscription() -> None:
    kb = utils.digest_view_menu(
        "week",
        page=0,
        total_pages=1,
        selected_sub={"type": "vehicle_class", "ref_id": "class-12345678"},
        user={"show_qualifying": 1, "show_practice": 0},
        pick_page=2,
        allow_pick=True,
    )

    assert kb.inline_keyboard[-1][0].text == "◀️ Назад"
    assert kb.inline_keyboard[-1][0].callback_data == utils.DigestViewCD(kind="week", action="pick", page=2).pack()
    assert kb.inline_keyboard[0][0].text == "✅ Квалификации"
    assert kb.inline_keyboard[0][1].text == "❌ Практики"


def test_digest_view_menu_uses_back_button_for_all_scope_without_menu() -> None:
    kb = utils.digest_view_menu(
        "today",
        page=0,
        total_pages=1,
        selected_sub=None,
        user={"show_qualifying": 0, "show_practice": 1},
        allow_pick=True,
    )

    assert kb.inline_keyboard[0][0].text == "❌ Квалификации"
    assert kb.inline_keyboard[0][1].text == "✅ Практики"
    assert kb.inline_keyboard[-1][0].text == "◀️ Назад"
    assert all(
        button.callback_data != "main_menu"
        for row in kb.inline_keyboard
        for button in row
    )


def test_digest_pick_menu_passes_origin_page_into_view_callbacks() -> None:
    subs = [
        {"type": "vehicle_class", "ref_id": f"class-{idx:08d}", "ref_name": f"Class {idx}"}
        for idx in range(1, 10)
    ]
    counts = {
        ("vehicle_class", "class-00000001"): 3,
        ("vehicle_class", "class-00000002"): 1,
    }
    kb = utils.digest_pick_menu(
        "today",
        subs,
        counts,
        page=0,
    )

    assert kb.inline_keyboard[0][0].callback_data == utils.DigestViewCD(
        kind="today",
        action="view",
        scope="all",
        page=0,
        pick_page=0,
    ).pack()
    assert kb.inline_keyboard[1][0].callback_data == utils.DigestViewCD(
        kind="today",
        action="view",
        scope="vehicle_class",
        ref_id="class-00",
        page=0,
        pick_page=0,
    ).pack()
    assert kb.inline_keyboard[1][0].text.endswith("· 3")


def test_history_pick_menu_uses_counts() -> None:
    items = [
        {"type": "series", "ref_id": "series-1", "ref_name": "Series 1"},
        {"type": "series", "ref_id": "series-2", "ref_name": "Series 2"},
    ]
    counts = {
        ("series", "series-1"): 4,
    }

    kb = utils.history_pick_menu("series", items, counts, page=0)

    assert kb.inline_keyboard[0][0].text.endswith("· 4")


async def test_render_digest_uses_rscg_stages_for_rscg_subscription(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_safe_edit_text(message, text, **kwargs):
        captured["text"] = text
        captured["reply_markup"] = kwargs.get("reply_markup")

    async def fake_rscg_stages(*_args, **_kwargs):
        return [
            RscgStage(
                id=64,
                round=1,
                date_start=date.today(),
                date_end=date.today(),
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
        ]

    monkeypatch.setattr(digest.utils, "safe_edit_text", fake_safe_edit_text)
    monkeypatch.setattr(digest, "_rscg_digest_stages", fake_rscg_stages)

    target = SimpleNamespace(chat=SimpleNamespace(id=1))
    await digest._render_digest(
        target,
        db=SimpleNamespace(),
        mem=SimpleNamespace(),
        http_session=None,
        kind="today",
        sessions=[],
        bc_map={},
        user={"timezone": "Europe/Moscow", "preferred_langs": '["English"]', "ui_lang": "en"},
        subs=[{"type": "rscg", "ref_id": "rscg", "ref_name": "SMP RSKG"}],
        header="📅 <b>My Racing Day</b>",
        scope="rscg",
        ref_id="rscg",
        action="view",
        as_edit=True,
    )

    assert "Moscow Raceway" in str(captured["text"])
    assert "SMP RSKG" in str(captured["text"])
