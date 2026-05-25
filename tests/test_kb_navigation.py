import utils


def test_main_menu_does_not_include_rscg_button() -> None:
    kb = utils.main_menu(lang="ru")

    callback_data = [
        button.callback_data
        for row in kb.inline_keyboard
        for button in row
        if button.callback_data
    ]

    assert utils.RscgCD(action="list").pack() not in callback_data


def test_kb_menu_uses_section_navigation() -> None:
    kb = utils.kb_menu(utils.KNOWLEDGE_BASE, lang="ru")

    callback_data = [
        button.callback_data
        for row in kb.inline_keyboard
        for button in row
        if button.callback_data
    ]

    assert utils.KbGroupCD(group="series").pack() in callback_data
    assert utils.KbGroupCD(group="national").pack() in callback_data
    assert utils.KbGroupCD(group="classes").pack() in callback_data
    assert utils.KbGroupCD(group="formats").pack() in callback_data
    assert all(not data.startswith("kb:") for data in callback_data if data != "main_menu")


def test_kb_group_articles_keep_group_context() -> None:
    kb = utils.kb_group_menu(utils.KNOWLEDGE_BASE, "formats", page=0, lang="ru")

    article_callbacks = [
        button.callback_data
        for row in kb.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("kb:")
    ]

    assert article_callbacks
    assert utils.KbShowCD(name="Endurance Racing", group="formats", page=0).pack() in article_callbacks


def test_kb_group_menu_uses_localized_back_to_sections_label() -> None:
    kb = utils.kb_group_menu(utils.KNOWLEDGE_BASE, "formats", page=0, lang="en")

    labels = [
        button.text
        for row in kb.inline_keyboard
        for button in row
    ]

    assert "◀️ Sections" in labels


def test_subscriptions_notify_list_uses_single_bulk_toggles() -> None:
    kb = utils.subscriptions_notify_list([
        {"type": "series", "ref_id": "1", "ref_name": "Formula 1", "qualifying_notify": 1, "practice_notify": 0},
    ], lang="ru")

    assert kb.inline_keyboard[0][0].text == "✅ Все квалы"
    assert kb.inline_keyboard[0][1].text == "❌ Все практики"
    assert len(kb.inline_keyboard[0]) == 2


def test_subscriptions_notify_list_shows_partial_state() -> None:
    kb = utils.subscriptions_notify_list([
        {"type": "series", "ref_id": "1", "ref_name": "Formula 1", "qualifying_notify": 1, "practice_notify": 1},
        {"type": "vehicle_class", "ref_id": "2", "ref_name": "GT3", "qualifying_notify": 0, "practice_notify": 1},
    ], lang="ru")

    assert kb.inline_keyboard[0][0].text == "◐ Все квалы"
    assert kb.inline_keyboard[0][1].text == "✅ Все практики"


def test_subscription_notify_callback_fits_telegram_limit() -> None:
    callback = utils.SubNotifyCD(
        action="t",
        type="s",
        ref_id="b4b60889-3e21-427d-a4fc-ff1b04e09a6d",
        field="q",
    ).pack()

    assert len(callback.encode()) <= 64
