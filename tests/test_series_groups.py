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
        "DTM",
        "European Le Mans Series",
        "INDYCAR SERIES",
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
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar")] == [
        "GT World Challenge Europe",
        "DTM",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto")] == ["European Le Mans Series"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "nascar_oval")] == [
        "INDYCAR SERIES",
        "NASCAR Cup Series",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock")] == ["British Touring Car Championship"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "rally_raid_rx")] == ["Dakar Rally"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "moto_bike")] == ["MotoGP"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "dirt_drift_offroad")] == ["Formula DRIFT"]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other")] == ["Random Championship"]


def test_filter_series_by_mine_and_popular() -> None:
    all_series = _make_series(
        "Formula 1",
        "INDYCAR SERIES",
        "World Endurance Championship",
        "IMSA WeatherTech SportsCar Championship",
        "GT World Challenge Europe Sprint Cup",
        "Random Championship",
    )
    subscribed_ids = {"id-2", "id-5"}

    assert [s["name"] for s in utils.filter_series_by_group(all_series, "mine", subscribed_ids)] == [
        "GT World Challenge Europe Sprint Cup",
        "INDYCAR SERIES",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "popular", subscribed_ids)] == [
        "Formula 1",
        "World Endurance Championship",
        "IMSA WeatherTech SportsCar Championship",
        "INDYCAR SERIES",
        "GT World Challenge Europe Sprint Cup",
    ]


def test_filter_series_prioritizes_default_names_inside_group() -> None:
    all_series = _make_series(
        "Super Formula",
        "Formula 1",
        "Formula Regional European Championship",
        "Formula E",
    )

    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula")] == [
        "Formula 1",
        "Formula E",
        "Super Formula",
        "Formula Regional European Championship",
    ]


def test_series_group_menu_shows_priority_groups() -> None:
    all_series = _make_series("Formula 1", "GT World Challenge Europe", "Random Championship")
    subscribed_ids = {"id-3"}

    kb = utils.series_group_menu(all_series, subscribed_ids)

    assert kb.inline_keyboard[0][0].text == "✅ Мои подписки · 1"
    assert kb.inline_keyboard[1][0].text == "🔥 Популярные · 2"
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
        "Porsche Supercup",
        "Porsche Carrera Cup North America",
        "Porsche Sprint Challenge Australia",
        "Porsche Endurance Challenge North America",
        "Porsche Sports Cup Deutschland",
        "Ferrari Challenge Europe",
        "GT World Challenge Europe",
        "GT4 America",
        "BMW M2 Cup",
    )

    kb = utils.series_subgroup_menu(all_series, "gt_sportscar", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "Porsche · 5",
        "Ferrari Challenge · 1",
        "GT World Challenge · 1",
        "GT4 · 1",
        "Марочные кубки · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="po")] == [
        "Porsche Supercup",
        "Porsche Carrera Cup North America",
        "Porsche Endurance Challenge North America",
        "Porsche Sports Cup Deutschland",
        "Porsche Sprint Challenge Australia",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="fe")] == [
        "Ferrari Challenge Europe"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="gw")] == [
        "GT World Challenge Europe"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="g4")] == [
        "GT4 America"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="mc")] == [
        "BMW M2 Cup"
    ]
    assert utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="ot") == []

    nested_kb = utils.series_subgroup_menu(all_series, "gt_sportscar", set(), subgroup="po")
    assert [row[0].text for row in nested_kb.inline_keyboard[:-1]] == [
        "Porsche Supercup · 1",
        "Porsche Carrera Cup · 1",
        "Porsche Sprint Challenge · 1",
        "Porsche Endurance · 1",
        "Остальное Porsche · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="po.su")] == [
        "Porsche Supercup",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="po.ca")] == [
        "Porsche Carrera Cup North America",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="po.sp")] == [
        "Porsche Sprint Challenge Australia",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="po.en")] == [
        "Porsche Endurance Challenge North America",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "gt_sportscar", subgroup="po.ot")] == [
        "Porsche Sports Cup Deutschland",
    ]


def test_formula_group_splits_into_subfamilies() -> None:
    all_series = _make_series(
        "Formula 1",
        "Formula 2",
        "Formula 3",
        "Formula E",
        "Super Formula",
        "Super Formula Lights",
        "Italian F4 Championship",
        "Formula Regional European Championship",
        "USF2000",
        "EuroFormula Open",
    )

    kb = utils.series_subgroup_menu(all_series, "formula", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "Formula · 4",
        "Super Formula · 2",
        "F4 · 1",
        "Formula Regional · 1",
        "Road to Indy / USF · 1",
        "Остальное · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula", subgroup="fm")] == [
        "Formula 1",
        "Formula 2",
        "Formula 3",
        "Formula E",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula", subgroup="sf")] == [
        "Super Formula",
        "Super Formula Lights",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula", subgroup="f4")] == [
        "Italian F4 Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula", subgroup="fr")] == [
        "Formula Regional European Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula", subgroup="us")] == [
        "USF2000",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "formula", subgroup="ot")] == [
        "EuroFormula Open",
    ]


def test_touring_group_splits_into_subfamilies() -> None:
    all_series = _make_series(
        "British Touring Car Championship",
        "TCR World Tour",
        "European Truck Racing Championship",
        "Stock Car Pro Series",
        "Supercars Championship",
    )

    kb = utils.series_subgroup_menu(all_series, "touring_stock", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "Touring Cars · 1",
        "TCR · 1",
        "Trucks · 1",
        "Stock Cars South America · 2",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="tc")] == [
        "British Touring Car Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="cr")] == [
        "TCR World Tour",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="tr")] == [
        "European Truck Racing Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "touring_stock", subgroup="st")] == [
        "Supercars Championship",
        "Stock Car Pro Series",
    ]


def test_endurance_group_splits_into_wec_and_imsa() -> None:
    all_series = _make_series(
        "FIA World Endurance Championship",
        "IMSA SportsCar Championship",
        "European Le Mans Series",
        "Asian Le Mans Series",
        "Le Mans Cup",
        "24H Series European Series",
        "24 Hours of Nürburgring",
    )

    kb = utils.series_subgroup_menu(all_series, "endurance_proto", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "WEC · 1",
        "IMSA · 1",
        "ELMS · 1",
        "Asian Le Mans · 1",
        "Le Mans Cup / Prototype Cup · 1",
        "24H Series · 2",
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
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto", subgroup="lp")] == [
        "Le Mans Cup"
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "endurance_proto", subgroup="24")] == [
        "24H Series European Series",
        "24 Hours of Nürburgring",
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


def test_nascar_group_splits_indycar_and_support_ladders() -> None:
    all_series = _make_series(
        "INDYCAR SERIES",
        "INDY NXT",
        "NASCAR Cup Series",
        "NASCAR Craftsman Truck Series",
        "ARCA Menards Series",
        "SMART Modified Tour",
    )

    kb = utils.series_subgroup_menu(all_series, "nascar_oval", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "IndyCar · 2",
        "NASCAR Cup · 1",
        "NASCAR support · 1",
        "ARCA · 1",
        "Sprint Cars / Modified / Late Models · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "nascar_oval", subgroup="in")] == [
        "INDYCAR SERIES",
        "INDY NXT",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "nascar_oval", subgroup="cu")] == [
        "NASCAR Cup Series",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "nascar_oval", subgroup="ns")] == [
        "NASCAR Craftsman Truck Series",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "nascar_oval", subgroup="ar")] == [
        "ARCA Menards Series",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "nascar_oval", subgroup="sm")] == [
        "SMART Modified Tour",
    ]


def test_moto_group_splits_into_key_subfamilies() -> None:
    all_series = _make_series(
        "MotoGP",
        "Moto2",
        "Moto3",
        "MotoAmerica",
        "MotoAmerica Talent Cup",
        "Superbike World Championship",
        "AMA Supercross",
        "FIM Motocross World Championship",
        "FIM Speedway GP",
        "Macau Motorcycle Grand Prix",
    )

    kb = utils.series_subgroup_menu(all_series, "moto_bike", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "MotoGP · 4",
        "Superbike · 1",
        "AMA · 2",
        "FIM · 2",
        "Остальное · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "moto_bike", subgroup="gp")] == [
        "MotoGP",
        "Moto2",
        "Moto3",
        "MotoAmerica Talent Cup",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "moto_bike", subgroup="sb")] == [
        "Superbike World Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "moto_bike", subgroup="am")] == [
        "MotoAmerica",
        "AMA Supercross",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "moto_bike", subgroup="fm")] == [
        "FIM Motocross World Championship",
        "FIM Speedway GP",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "moto_bike", subgroup="ot")] == [
        "Macau Motorcycle Grand Prix",
    ]


def test_other_group_splits_misc_series_into_useful_buckets() -> None:
    all_series = _make_series(
        "GB3 Championship",
        "FIA Karting World Championship",
        "NHRA Mission Foods Drag Racing Series",
        "Chili Bowl Nationals",
        "Mazda MX-5 Cup",
        "Turismo Carretera",
        "Goodwood Revival",
        "Isle of Man TT",
        "King of the Hammers",
        "Random Championship",
    )

    kb = utils.series_subgroup_menu(all_series, "other", set())

    assert [row[0].text for row in kb.inline_keyboard[:-1]] == [
        "Junior / feeder · 1",
        "Karting · 1",
        "Drag racing · 1",
        "Short track / dirt · 1",
        "Cups / club racing · 1",
        "Turismo / national · 1",
        "Historic / hillclimb · 1",
        "Bikes other · 1",
        "Special / adventure · 1",
        "Остальное · 1",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="jr")] == [
        "GB3 Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="ka")] == [
        "FIA Karting World Championship",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="dr")] == [
        "NHRA Mission Foods Drag Racing Series",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="di")] == [
        "Chili Bowl Nationals",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="cu")] == [
        "Mazda MX-5 Cup",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="tn")] == [
        "Turismo Carretera",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="hh")] == [
        "Goodwood Revival",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="bm")] == [
        "Isle of Man TT",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="sp")] == [
        "King of the Hammers",
    ]
    assert [s["name"] for s in utils.filter_series_by_group(all_series, "other", subgroup="ot")] == [
        "Random Championship",
    ]
