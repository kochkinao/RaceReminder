import utils


def test_display_series_name_shortens_imsa_variants() -> None:
    assert utils.display_series_name("IMSA WeatherTech SportsCar Championship") == "IMSA WeatherTech Championship"
    assert utils.display_series_name("IMSA SportsCar Championship") == "IMSA SportsCar Championship"


def test_series_list_uses_short_display_name() -> None:
    kb = utils.series_list(
        [{"id": "1", "name": "IMSA WeatherTech SportsCar Championship"}],
        set(),
        group="all",
        page=0,
        lang="ru",
    )

    assert "IMSA WeatherTech Championship" in kb.inline_keyboard[0][0].text


def test_display_subject_icon_uses_meaningful_icons() -> None:
    assert utils.display_subject_icon("MotoGP", "series") == "🏍️"
    assert utils.display_subject_icon("Red Bull MotoGP Rookies Cup", "series") == "🧒"
