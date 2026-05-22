import utils


def _make_series(*names: str) -> list[dict]:
    return [{"id": f"id-{idx}", "name": name} for idx, name in enumerate(names, start=1)]


def test_filter_series_by_thematic_group() -> None:
    all_series = _make_series(
        "Formula 1",
        "Formula 2",
        "Formula 3",
        "Formula Regional European Championship",
        "GT World Challenge Europe",
        "European Le Mans Series",
        "NASCAR Cup Series",
        "British Touring Car Championship",
        "Dakar Rally",
        "MotoGP",
        "Formula DRIFT",
        "Random Championship",
    )

    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula")] == [
        "Formula 1",
        "Formula 2",
        "Formula 3",
        "Formula Regional European Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar")] == ["GT World Challenge Europe"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto")] == ["European Le Mans Series"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "nascar_oval")] == ["NASCAR Cup Series"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock")] == ["British Touring Car Championship"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "rally_raid_rx")] == ["Dakar Rally"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "moto_bike")] == ["MotoGP"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "dirt_drift_offroad")] == ["Formula DRIFT"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other")] == ["Random Championship"]


def test_filter_series_by_mine_and_popular() -> None:
    all_series = _make_series(
        "Formula 1",
        "IndyCar Series",
        "Random Championship",
    )
    subscribed_ids = {"id-2", "id-3"}

    assert [s["name"] for s in utils.filter_series_by_group(all_series, "mine", subscribed_ids)] == [
        "IndyCar Series",
        "Random Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "popular", subscribed_ids)] == [
        "Formula 1",
        "IndyCar Series",
    ]


def test_filter_series_prioritizes_default_names_inside_group() -> None:
    all_series = _make_series(
        "Super Formula",
        "Formula 1",
        "Formula Renault",
        "Formula E",
    )

    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula")] == [
        "Formula 1",
        "Formula E",
        "Formula Renault",
        "Super Formula",
    ]


def test_series_group_menu_shows_priority_groups() -> None:
    all_series = _make_series("Formula 1", "GT World Challenge Europe", "Random Championship")
    subscribed_ids = {"id-3"}

    kb = utils.series_group_menu(all_series, subscribed_ids)

    assert kb.inline_keyboard[0][0].text == "✅ Мои подписки · 1"
    assert kb.inline_keyboard[1][0].text == "🔥 Популярные · 1"
    assert kb.inline_keyboard[2][0].text == "🏎️ Formula · 1"
    assert kb.inline_keyboard[-1][0].callback_data == "subs_menu"


def test_series_callbacks_use_short_group_codes() -> None:
    all_series = [{"id": "f2517b16-8e88-4b27-80f4-a925213fbf77", "name": "European Le Mans Series"}]
    kb = utils.series_list(all_series, set(), group="endurance_proto", page=0)

    callback_data = kb.inline_keyboard[0][0].callback_data
    assert len(callback_data.encode()) <= 64
    assert callback_data == "sub:series:f2517b16-8e88-4b27-80f4-a925213fbf77:0:ep:"


def test_gt_group_supports_manufacturer_subgroups() -> None:
    all_series = _make_series(
        "Porsche Carrera Cup",
        "Ferrari Challenge Europe",
        "BMW M2 Cup",
        "GT World Challenge Europe",
    )

    kb = utils.series_subgroup_menu(all_series, "gt_sportscar", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "GT World Challenge · 1",
        "Porsche Cup · 1",
        "Ferrari Challenge · 1",
        "BMW Cup · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="po")] == [
        "Porsche Carrera Cup"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="gw")] == [
        "GT World Challenge Europe"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="fe")] == [
        "Ferrari Challenge Europe"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="bm")] == [
        "BMW M2 Cup"
    ]
    assert utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="ot") == []


def test_touring_group_splits_into_subfamilies() -> None:
    all_series = _make_series(
        "British Touring Car Championship",
        "TCR World Tour",
        "Deutsche Tourenwagen Masters",
        "European Truck Racing Championship",
        "Stock Car Pro Series",
    )

    kb = utils.series_subgroup_menu(all_series, "touring_stock", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "Touring Cars · 1",
        "TCR · 1",
        "DTM · 1",
        "Trucks · 1",
        "Stock/Late Model · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="tc")] == [
        "British Touring Car Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="cr")] == [
        "TCR World Tour",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="dt")] == [
        "Deutsche Tourenwagen Masters",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="tr")] == [
        "European Truck Racing Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="st")] == [
        "Stock Car Pro Series",
    ]


def test_endurance_group_splits_into_wec_and_imsa() -> None:
    all_series = _make_series(
        "FIA World Endurance Championship",
        "IMSA SportsCar Championship",
        "European Le Mans Series",
        "Asian Le Mans Series",
        "24H Series European Series",
    )

    kb = utils.series_subgroup_menu(all_series, "endurance_proto", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "WEC · 1",
        "IMSA · 1",
        "ELMS · 1",
        "Asian Le Mans · 1",
        "24H Series · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto", subgroup="we")] == [
        "FIA World Endurance Championship"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto", subgroup="im")] == [
        "IMSA SportsCar Championship"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto", subgroup="el")] == [
        "European Le Mans Series"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto", subgroup="as")] == [
        "Asian Le Mans Series"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto", subgroup="24")] == [
        "24H Series European Series"
    ]


def test_rally_group_splits_into_subfamilies() -> None:
    all_series = _make_series(
        "World Rally Championship",
        "European Rally Championship",
        "RallyX Europe",
        "Dakar Rally",
        "Campionato Italiano Assoluto Rally Sparco",
    )

    kb = utils.series_subgroup_menu(all_series, "rally_raid_rx", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "WRC · 1",
        "ERC · 1",
        "Rallycross · 1",
        "Dakar / Raid · 1",
        "National Rally · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "rally_raid_rx", subgroup="wr")] == [
        "World Rally Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "rally_raid_rx", subgroup="er")] == [
        "European Rally Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "rally_raid_rx", subgroup="rx")] == [
        "RallyX Europe",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "rally_raid_rx", subgroup="rd")] == [
        "Dakar Rally",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "rally_raid_rx", subgroup="rt")] == [
        "Campionato Italiano Assoluto Rally Sparco",
    ]
