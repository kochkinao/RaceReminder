import re
import unicodedata

type SeriesInfo = dict[str, str | list[str]]


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s

SERIES_KB: dict[str, SeriesInfo] = {
    "Formula 1": {
        "emoji": "🔴",
        "short": "Высший класс мирового автоспорта. ~24 этапа, 5 континентов.",
        "long": (
            "Formula 1 — вершина мирового автоспорта. Сезон длится с марта по декабрь. "
            "Автомобили развивают мощность свыше 1000 л.с. и разгоняются до 100 км/ч "
            "менее чем за 2 секунды."
        ),
        "similar":   ["Formula 2", "IndyCar Series"],
        "highlight": "Гран-При Монако, Монца, Сузука",
        "website":   "https://www.formula1.com",
    },
    "FIA World Endurance Championship": {
        "emoji": "🏆",
        "short": "Гонки на выносливость с прототипами и GT. Включает Ле-Ман 24ч.",
        "long": (
            "WEC — чемпионат мира по автогонкам на выносливость под эгидой FIA. "
            "Главное событие — легендарная гонка Ле-Ман 24 часа. "
            "Заводские команды: Porsche, Ferrari, Toyota, BMW."
        ),
        "similar":   ["IMSA SportsCar Championship", "Asian Le Mans Series"],
        "highlight": "24h Le Mans, 6h Spa, 6h Fuji",
        "website":   "https://www.fiawec.com",
    },
    "IMSA SportsCar Championship": {
        "emoji": "🇺🇸",
        "short": "Американские гонки на выносливость. Daytona, Sebring, Road Atlanta.",
        "long": (
            "IMSA — ведущий американский многоклассовый чемпионат по гонкам на выносливость. "
            "Сезон открывается знаменитой Daytona 24 Hours."
        ),
        "similar":   ["FIA World Endurance Championship"],
        "highlight": "Daytona 24h, Sebring 12h, Petit Le Mans",
        "website":   "https://www.imsa.com",
    },
    "FIA World Rally Championship": {
        "emoji": "🚗",
        "short": "Ралли по дорогам общего пользования: грунт, асфальт, снег.",
        "long": (
            "WRC охватывает этапы в Европе, Азии, Африке и Океании. "
            "Покрытие меняется от ледяных дорог Финляндии до гравийных троп Кении."
        ),
        "similar":   ["WRC2", "ERC", "Rallycross"],
        "highlight": "Rally Monte Carlo, Safari Rally Kenya, Rally Finland",
        "website":   "https://www.wrc.com",
    },
    "NASCAR Cup Series": {
        "emoji": "🏁",
        "short": "Стоковые автомобили на американских овалах. Daytona 500.",
        "long": (
            "NASCAR Cup Series — флагманский чемпионат NASCAR. ~36 этапов с февраля по ноябрь. "
            "Главная гонка — Daytona 500. Специфика — плотные пелотоны и система плей-офф."
        ),
        "similar":   ["NASCAR Xfinity Series", "IndyCar Series"],
        "highlight": "Daytona 500, Coca-Cola 600, Brickyard 400",
        "website":   "https://www.nascar.com",
    },
    "IndyCar Series": {
        "emoji": "🏎️",
        "short": "Американские формульные гонки: овалы, уличные трассы и кольца.",
        "long": (
            "IndyCar — главная американская серия открытых колёс. "
            "Те же автомобили гоняются на суперовалах и городских трассах. "
            "Венец сезона — Indy 500."
        ),
        "similar":   ["Formula 1", "Indy NXT"],
        "highlight": "Indianapolis 500, Long Beach GP",
        "website":   "https://www.indycar.com",
    },
    "Formula E": {
        "emoji": "⚡",
        "short": "Электрические болиды на городских улицах. Чемпионат мира FIA.",
        "long": (
            "Formula E — первый чемпионат мира для полностью электрических автомобилей. "
            "Гонки на временных трассах в центрах Лондона, Монако, Токио, Рима."
        ),
        "similar":   ["Extreme E", "MotoE"],
        "highlight": "Monaco E-Prix, London E-Prix",
        "website":   "https://www.fiaformulae.com",
    },
    "DTM": {
        "emoji": "🇩🇪",
        "short": "Немецкий туринговый чемпионат. GT3-класс, европейские трассы.",
        "long": (
            "DTM (Deutsche Tourenwagen Masters) — один из самых престижных туринговых "
            "чемпионатов Европы. С 2021 года на GT3-регламенте."
        ),
        "similar":   ["GT World Challenge Europe", "ADAC GT Masters"],
        "highlight": "Norisring, Nürburgring, Hockenheim",
        "website":   "https://www.dtm.com",
    },
    "MotoGP": {
        "emoji": "🏍️",
        "short": "Высший класс мотогонок. Прототипы мощностью 260+ л.с.",
        "long": (
            "MotoGP — чемпионат мира по шоссейно-кольцевым мотогонкам. ~20 этапов. "
            "Заводские команды: Honda, Yamaha, Ducati, KTM, Aprilia."
        ),
        "similar":   ["Moto2", "Moto3", "WorldSBK"],
        "highlight": "GP Италии (Муджелло), GP Катара",
        "website":   "https://www.motogp.com",
    },
    "GT World Challenge Europe": {
        "emoji": "🏆",
        "short": "GT3 на европейских трассах. Sprint + Endurance. 24ч Спа.",
        "long": (
            "GTWCE — ведущий европейский GT3-чемпионат. Sprint Cup + Endurance Cup. "
            "Участвуют Ferrari, Lamborghini, McLaren, Porsche, Mercedes, BMW."
        ),
        "similar":   ["DTM", "IMSA GTD"],
        "highlight": "24h Spa, 3h Barcelona",
        "website":   "https://www.gt-world-challenge-europe.com",
    },
    "Supercars Championship": {
        "emoji": "🦘",
        "short": "Главная австралийская серия. Ford vs Chevrolet. Bathurst 1000.",
        "long": (
            "Supercars Championship — главный автогоночный чемпионат Австралии. "
            "Высшая точка сезона — Bathurst 1000 на горном треке Mount Panorama."
        ),
        "similar":   ["TCR Australia"],
        "highlight": "Bathurst 1000, Sydney 500",
        "website":   "https://www.supercars.com.au",
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


def format_card(name: str, info: SeriesInfo | None = None) -> str:
    d = info or get_series_info(name) or {}
    lines = [f"{d.get('emoji','🏁')} <b>{name}</b>"]
    if s := d.get("short"):  lines.append(f"<i>{s}</i>")
    if l := d.get("long"):   lines.append(f"\n{l}")
    if h := d.get("highlight"): lines.append(f"\n🌟 <b>Знаковые гонки:</b> {h}")
    if sim := d.get("similar"):
        lines.append(f"🔗 <b>Похожие серии:</b> {', '.join(sim)}")  # type: ignore[arg-type]
    if w := d.get("website"): lines.append(f"🌐 <a href='{w}'>Официальный сайт</a>")
    return "\n".join(lines)
