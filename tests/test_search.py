from handlers import search
import utils


def test_extract_search_query_from_results_text() -> None:
    text = (
        "🔍 Результаты поиска\n\n"
        "Запрос: Formula 1\n"
        "Найдено: серии — 1, классы — 0, статьи базы знаний — 1\n\n"
        "✅ / 💔 — подписка, 📚 — открыть справку."
    )

    assert search._extract_search_query(text) == "Formula 1"


def test_search_results_keyboard_uses_dedicated_callbacks() -> None:
    kb = search._search_results_keyboard(
        series_matches=[{"id": "series-1", "name": "Formula 1"}],
        class_matches=[{"id": "class-1", "name": "GT3"}],
        kb_matches=["Hypercar"],
        subscribed_series_ids={"series-1"},
        subscribed_class_ids=set(),
    )

    assert kb.inline_keyboard[0][0].text == "💔 🏎️ Formula 1"
    assert kb.inline_keyboard[0][0].callback_data == utils.SearchToggleCD(
        type="series",
        ref_id="series-1",
    ).pack()
    assert kb.inline_keyboard[1][0].text == "✅ 🏷️ GT3"
    assert kb.inline_keyboard[1][0].callback_data == utils.SearchToggleCD(
        type="vehicle_class",
        ref_id="class-1",
    ).pack()
    assert kb.inline_keyboard[2][0].text == "📚 Hypercar"
    assert kb.inline_keyboard[2][0].callback_data == utils.KbShowCD(name="Hypercar").pack()
    assert all(
        button.callback_data != "noop"
        for row in kb.inline_keyboard[:-1]
        for button in row
    )


def test_format_card_supports_english_localization() -> None:
    text = utils.format_card("Formula 1", lang="en")

    assert "The top tier of global motorsport" in text
    assert "Key Examples" in text
    assert "Official Website" in text


def test_search_results_text_uses_kb_only_variant() -> None:
    text = search._search_results_text(
        query="hypercar",
        series_count=0,
        class_count=0,
        kb_count=1,
        lang="en",
    )

    assert "No subscription targets matched this query" in text
    assert "knowledge base articles" in text
