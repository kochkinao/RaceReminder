from __future__ import annotations

import re
import unicodedata

from utils.i18n import DEFAULT_UI_LANG, normalize_ui_lang

type LocalizedText = dict[str, str]
type SeriesInfo = dict[str, str | list[str] | LocalizedText]


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _loc(ru: str, en: str) -> LocalizedText:
    return {"ru": ru, "en": en}


SERIES_KB: dict[str, SeriesInfo] = {
    "Formula 1": {
        "emoji": "🔴",
        "short": _loc(
            "Высший класс мирового автоспорта. ~24 этапа, 5 континентов.",
            "The top tier of global motorsport. Roughly 24 rounds across 5 continents.",
        ),
        "long": _loc(
            "Formula 1 — вершина мирового автоспорта. Сезон длится с марта по декабрь. Автомобили развивают мощность свыше 1000 л.с. и разгоняются до 100 км/ч менее чем за 2 секунды.",
            "Formula 1 is the pinnacle of world motorsport. The season runs from March to December. The cars produce over 1000 hp and can reach 100 km/h in under 2 seconds.",
        ),
        "similar": ["Formula 2", "IndyCar Series"],
        "highlight": _loc("Гран-При Монако, Монца, Сузука", "Monaco Grand Prix, Monza, Suzuka"),
        "website": "https://www.formula1.com",
    },
    "FIA World Endurance Championship": {
        "emoji": "🏆",
        "short": _loc(
            "Гонки на выносливость с прототипами и GT. Включает Ле-Ман 24ч.",
            "Endurance racing with prototypes and GT cars. Includes the 24 Hours of Le Mans.",
        ),
        "long": _loc(
            "WEC — чемпионат мира по автогонкам на выносливость под эгидой FIA. Главное событие — легендарная гонка Ле-Ман 24 часа. Заводские команды: Porsche, Ferrari, Toyota, BMW.",
            "WEC is the FIA world championship for endurance racing. Its headline event is the legendary 24 Hours of Le Mans. Major factory teams include Porsche, Ferrari, Toyota, and BMW.",
        ),
        "similar": ["IMSA SportsCar Championship", "Asian Le Mans Series"],
        "highlight": _loc("24h Le Mans, 6h Spa, 6h Fuji", "24h Le Mans, 6h Spa, 6h Fuji"),
        "website": "https://www.fiawec.com",
    },
    "IMSA SportsCar Championship": {
        "emoji": "🇺🇸",
        "short": _loc(
            "Американские гонки на выносливость. Daytona, Sebring, Road Atlanta.",
            "American endurance racing. Daytona, Sebring, Road Atlanta.",
        ),
        "long": _loc(
            "IMSA — ведущий американский многоклассовый чемпионат по гонкам на выносливость. Сезон открывается знаменитой Daytona 24 Hours.",
            "IMSA is the leading American multi-class endurance championship. The season opens with the famous Daytona 24 Hours.",
        ),
        "similar": ["FIA World Endurance Championship"],
        "highlight": _loc("Daytona 24h, Sebring 12h, Petit Le Mans", "Daytona 24h, Sebring 12h, Petit Le Mans"),
        "website": "https://www.imsa.com",
    },
    "FIA World Rally Championship": {
        "emoji": "🚗",
        "short": _loc(
            "Ралли по дорогам общего пользования: грунт, асфальт, снег.",
            "Rally on public roads: gravel, asphalt, and snow.",
        ),
        "long": _loc(
            "WRC охватывает этапы в Европе, Азии, Африке и Океании. Покрытие меняется от ледяных дорог Финляндии до гравийных троп Кении.",
            "WRC spans rounds in Europe, Asia, Africa, and Oceania. Surfaces range from icy Finnish roads to the gravel tracks of Kenya.",
        ),
        "similar": ["WRC2", "ERC", "Rallycross"],
        "highlight": _loc("Rally Monte Carlo, Safari Rally Kenya, Rally Finland", "Rally Monte Carlo, Safari Rally Kenya, Rally Finland"),
        "website": "https://www.wrc.com",
    },
    "NASCAR Cup Series": {
        "emoji": "🏁",
        "short": _loc(
            "Стоковые автомобили на американских овалах. Daytona 500.",
            "Stock cars on American ovals. Daytona 500.",
        ),
        "long": _loc(
            "NASCAR Cup Series — флагманский чемпионат NASCAR. ~36 этапов с февраля по ноябрь. Главная гонка — Daytona 500. Специфика — плотные пелотоны и система плей-офф.",
            "The NASCAR Cup Series is NASCAR's flagship championship. It runs about 36 rounds from February to November. Its marquee race is the Daytona 500, with pack racing and a playoff system as defining traits.",
        ),
        "similar": ["NASCAR Xfinity Series", "IndyCar Series"],
        "highlight": _loc("Daytona 500, Coca-Cola 600, Brickyard 400", "Daytona 500, Coca-Cola 600, Brickyard 400"),
        "website": "https://www.nascar.com",
    },
    "IndyCar Series": {
        "emoji": "🏎️",
        "short": _loc(
            "Американские формульные гонки: овалы, уличные трассы и кольца.",
            "American open-wheel racing: ovals, street circuits, and road courses.",
        ),
        "long": _loc(
            "IndyCar — главная американская серия открытых колёс. Те же автомобили гоняются на суперовалах и городских трассах. Венец сезона — Indy 500.",
            "IndyCar is the premier American open-wheel series. The same cars race on superspeedways and city streets. The jewel of the season is the Indy 500.",
        ),
        "similar": ["Formula 1", "Indy NXT"],
        "highlight": _loc("Indianapolis 500, Long Beach GP", "Indianapolis 500, Long Beach GP"),
        "website": "https://www.indycar.com",
    },
    "Formula E": {
        "emoji": "⚡",
        "short": _loc(
            "Электрические болиды на городских улицах. Чемпионат мира FIA.",
            "Electric single-seaters on city streets. An FIA world championship.",
        ),
        "long": _loc(
            "Formula E — первый чемпионат мира для полностью электрических автомобилей. Гонки на временных трассах в центрах Лондона, Монако, Токио, Рима.",
            "Formula E is the first world championship for fully electric race cars. It runs on temporary city circuits in places like London, Monaco, Tokyo, and Rome.",
        ),
        "similar": ["Extreme E", "MotoE"],
        "highlight": _loc("Monaco E-Prix, London E-Prix", "Monaco E-Prix, London E-Prix"),
        "website": "https://www.fiaformulae.com",
    },
    "DTM": {
        "emoji": "🇩🇪",
        "short": _loc(
            "Немецкий туринговый чемпионат. GT3-класс, европейские трассы.",
            "German touring championship. GT3 machinery on European circuits.",
        ),
        "long": _loc(
            "DTM (Deutsche Tourenwagen Masters) — один из самых престижных туринговых чемпионатов Европы. С 2021 года на GT3-регламенте.",
            "DTM (Deutsche Tourenwagen Masters) is one of Europe's most prestigious touring championships. Since 2021 it has used GT3 regulations.",
        ),
        "similar": ["GT World Challenge Europe", "ADAC GT Masters"],
        "highlight": _loc("Norisring, Nürburgring, Hockenheim", "Norisring, Nürburgring, Hockenheim"),
        "website": "https://www.dtm.com",
    },
    "MotoGP": {
        "emoji": "🏍️",
        "short": _loc(
            "Высший класс мотогонок. Прототипы мощностью 260+ л.с.",
            "The top class of motorcycle racing. 260+ hp prototypes.",
        ),
        "long": _loc(
            "MotoGP — чемпионат мира по шоссейно-кольцевым мотогонкам. ~20 этапов. Заводские команды: Honda, Yamaha, Ducati, KTM, Aprilia.",
            "MotoGP is the world championship for grand prix motorcycle racing. It runs roughly 20 rounds. Major factory teams include Honda, Yamaha, Ducati, KTM, and Aprilia.",
        ),
        "similar": ["Moto2", "Moto3", "WorldSBK"],
        "highlight": _loc("GP Италии (Муджелло), GP Катара", "Italian GP (Mugello), Qatar GP"),
        "website": "https://www.motogp.com",
    },
    "GT World Challenge Europe": {
        "emoji": "🏆",
        "short": _loc(
            "GT3 на европейских трассах. Sprint + Endurance. 24ч Спа.",
            "GT3 racing on European circuits. Sprint + Endurance. 24h Spa.",
        ),
        "long": _loc(
            "GTWCE — ведущий европейский GT3-чемпионат. Sprint Cup + Endurance Cup. Участвуют Ferrari, Lamborghini, McLaren, Porsche, Mercedes, BMW.",
            "GTWCE is the leading European GT3 championship. It combines Sprint Cup and Endurance Cup competition, with brands such as Ferrari, Lamborghini, McLaren, Porsche, Mercedes, and BMW.",
        ),
        "similar": ["DTM", "IMSA GTD"],
        "highlight": _loc("24h Spa, 3h Barcelona", "24h Spa, 3h Barcelona"),
        "website": "https://www.gt-world-challenge-europe.com",
    },
    "Supercars Championship": {
        "emoji": "🦘",
        "short": _loc(
            "Главная австралийская серия. Ford vs Chevrolet. Bathurst 1000.",
            "Australia's top series. Ford vs Chevrolet. Bathurst 1000.",
        ),
        "long": _loc(
            "Supercars Championship — главный автогоночный чемпионат Австралии. Высшая точка сезона — Bathurst 1000 на горном треке Mount Panorama.",
            "The Supercars Championship is Australia's premier racing series. The season highlight is the Bathurst 1000 at the Mount Panorama circuit.",
        ),
        "similar": ["TCR Australia"],
        "highlight": _loc("Bathurst 1000, Sydney 500", "Bathurst 1000, Sydney 500"),
        "website": "https://www.supercars.com.au",
    },
}


def get_series_info(name: str) -> SeriesInfo | None:
    if name in SERIES_KB:
        return SERIES_KB[name]
    norm = _normalize(name)
    return next(
        (v for k, v in SERIES_KB.items() if _normalize(k) in norm or norm in _normalize(k)),
        None,
    )


def _text(value: str | LocalizedText | None, lang: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        lang = normalize_ui_lang(lang)
        return value.get(lang) or value.get(DEFAULT_UI_LANG) or next(iter(value.values()), "")
    return value


def format_card(name: str, info: SeriesInfo | None = None, lang: str = DEFAULT_UI_LANG) -> str:
    d = info or get_series_info(name) or {}
    lines = [f"{d.get('emoji', '🏁')} <b>{name}</b>"]
    if short_text := _text(d.get("short"), lang):
        lines.append(f"<i>{short_text}</i>")
    if long_text := _text(d.get("long"), lang):
        lines.append(f"\n{long_text}")
    if highlight := _text(d.get("highlight"), lang):
        lines.append(
            f"\n🌟 <b>{'Key Events' if lang == 'en' else 'Знаковые гонки'}:</b> {highlight}"
        )
    if similar := d.get("similar"):
        lines.append(
            f"{'🔗 <b>Similar Series:</b>' if lang == 'en' else '🔗 <b>Похожие серии:</b>'} {', '.join(similar)}"
        )
    if website := d.get("website"):
        lines.append(
            f"🌐 <a href='{website}'>{'Official Website' if lang == 'en' else 'Официальный сайт'}</a>"
        )
    return "\n".join(lines)
