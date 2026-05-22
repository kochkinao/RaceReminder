"""
All keyboards live here. Handlers import from utils.kb — no keyboard
construction logic scattered across handler files.
"""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import DEFAULT_SERIES_NAMES, POPULAR_TIMEZONES
from utils.i18n import DEFAULT_UI_LANG, UI_LANGUAGE_OPTIONS, tr


# ── CallbackData factories (TrainingSchedule pattern) ─────────────────────────

class SubToggleCD(CallbackData, prefix="sub"):
    type:  str   # 'series' | 'vehicle_class'
    ref_id: str
    page:  int = 0
    group: str = ""
    subgroup: str = ""


class SearchToggleCD(CallbackData, prefix="searchsub"):
    type: str   # 'series' | 'vehicle_class'
    ref_id: str


class SeriesBrowseCD(CallbackData, prefix="seriesnav"):
    group: str = "menu"
    page: int = 0
    subgroup: str = ""


class SeriesInfoCD(CallbackData, prefix="seriesinfo"):
    ref_id: str
    group: str = ""
    page: int = 0
    subgroup: str = ""


class KbShowCD(CallbackData, prefix="kb"):
    name: str


class FavCD(CallbackData, prefix="fav"):
    action:     str   # 'add' | 'remove'
    session_id: str


class RemindCD(CallbackData, prefix="remind"):
    action: str = "menu"
    session_id: str = ""
    remind_type: str = ""


class HistoryViewCD(CallbackData, prefix="histv"):
    filter_type: str = "all"
    ref_id: str = ""
    page: int = 0


class HistoryPickCD(CallbackData, prefix="histpick"):
    kind: str
    page: int = 0


class DigestViewCD(CallbackData, prefix="dig"):
    kind: str
    action: str = "view"
    scope: str = "all"
    ref_id: str = ""
    page: int = 0
    pick_page: int = 0
    field: str = ""


class ProfileToggleCD(CallbackData, prefix="ptoggle"):
    field: str


class LangToggleCD(CallbackData, prefix="lang"):
    lang_id: str


class QualToggleCD(CallbackData, prefix="qual"):
    ref_id: str
    value:  int


class SubNotifyCD(CallbackData, prefix="subnotify"):
    action: str
    type: str
    ref_id: str
    field: str = ""


# ── Static keyboards ──────────────────────────────────────────────────────────

def ui_language_picker() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"ui_lang:{lang}")]
        for label, lang in UI_LANGUAGE_OPTIONS
    ])


def main_menu(lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=tr(lang, "menu.today"), callback_data="today"),
            InlineKeyboardButton(text=tr(lang, "menu.week"), callback_data="week"),
        ],
        [
            InlineKeyboardButton(text=tr(lang, "menu.subscriptions"), callback_data="subs_menu"),
            InlineKeyboardButton(text=tr(lang, "menu.search"), callback_data="search_prompt"),
        ],
        [
            InlineKeyboardButton(text=tr(lang, "menu.knowledge_base"), callback_data="kb_menu"),
            InlineKeyboardButton(text=tr(lang, "menu.favorites"), callback_data="favorites"),
        ],
        [InlineKeyboardButton(text=tr(lang, "menu.profile"), callback_data="profile_menu")],
    ])


def subs_main(lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang, "menu.series"), callback_data="subs:series")],
        [InlineKeyboardButton(text=tr(lang, "menu.classes"), callback_data="subs:classes")],
        [InlineKeyboardButton(text=tr(lang, "menu.my_subscriptions"), callback_data="subs:mine")],
        [InlineKeyboardButton(text=tr(lang, "menu.back_to_menu"), callback_data="main_menu")],
    ])


def back_to_menu(lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "menu.back_to_menu"), callback_data="main_menu")
    ]])


def back_to_subs(lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr(lang, "menu.back_to_subscriptions"), callback_data="subs_menu")
    ]])


def week_pager(page: int, total: int, lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"week_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if page + 1 < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"week_page:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text=tr(lang, "menu.back_to_menu"), callback_data="main_menu")],
    ])


def today_pager(page: int, total: int, lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"today_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if page + 1 < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"today_page:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text=tr(lang, "menu.back_to_menu"), callback_data="main_menu")],
    ])


# ── Dynamic keyboards ─────────────────────────────────────────────────────────

_SERIES_GROUPS: list[str] = [
    "mine",
    "popular",
    "formula",
    "gt_sportscar",
    "endurance_proto",
    "touring_stock",
    "nascar_oval",
    "rally_raid_rx",
    "moto_bike",
    "dirt_drift_offroad",
    "other",
]

_SERIES_GROUP_LABELS: dict[str, dict[str, str]] = {
    "mine": {"ru": "✅ Мои подписки", "en": "✅ My Subscriptions"},
    "popular": {"ru": "🔥 Популярные", "en": "🔥 Popular"},
    "formula": {"ru": "🏎️ Formula", "en": "🏎️ Formula"},
    "gt_sportscar": {"ru": "🚗 GT и спорткары", "en": "🚗 GT and Sports Cars"},
    "endurance_proto": {"ru": "⏱️ Endurance и prototypes", "en": "⏱️ Endurance and Prototypes"},
    "touring_stock": {"ru": "🚙 Touring", "en": "🚙 Touring"},
    "nascar_oval": {"ru": "🇺🇸 NASCAR и oval", "en": "🇺🇸 NASCAR and Oval"},
    "rally_raid_rx": {"ru": "🧭 Rally / rallycross / raid", "en": "🧭 Rally / Rallycross / Raid"},
    "moto_bike": {"ru": "🏍️ Moto", "en": "🏍️ Moto"},
    "dirt_drift_offroad": {"ru": "💨 Drift, dirt и off-road", "en": "💨 Drift, Dirt, and Off-road"},
    "other": {"ru": "📦 Остальное", "en": "📦 Other"},
}

_SERIES_GROUP_CODES: dict[str, str] = {
    "menu": "mn",
    "all": "al",
    "mine": "mi",
    "popular": "po",
    "formula": "fo",
    "gt_sportscar": "gs",
    "endurance_proto": "ep",
    "nascar_oval": "no",
    "touring_stock": "ts",
    "rally_raid_rx": "rr",
    "moto_bike": "mb",
    "dirt_drift_offroad": "dd",
    "other": "ot",
}

_SERIES_GROUP_CODES_REV = {value: key for key, value in _SERIES_GROUP_CODES.items()}

_POPULAR_SERIES_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Formula 1", ("formula 1",)),
    ("MotoGP", ("motogp",)),
    ("World Endurance Championship", ("world endurance championship",)),
    ("IMSA", ("imsa weathertech sportscar championship", "imsa sportscar championship")),
]


def _series_group_names() -> dict[str, set[str]]:
    return {"popular": set(DEFAULT_SERIES_NAMES)}


def series_group_to_callback(group: str) -> str:
    return _SERIES_GROUP_CODES.get(group, group)


def series_group_from_callback(value: str) -> str:
    return _SERIES_GROUP_CODES_REV.get(value, value or "all")


def _series_name(name: str) -> str:
    return name.lower().strip()


def _popular_series_index(name: str) -> int | None:
    n = _series_name(name)
    for idx, (_label, tokens) in enumerate(_POPULAR_SERIES_RULES):
        if any(token in n for token in tokens):
            return idx
    return None


def _series_matches_group(name: str, group: str) -> bool:
    n = _series_name(name)
    if group == "formula":
        return "drift" not in n and any(
            token in n
            for token in (
                "formula",
                " f1",
                "f1 ",
                "f2",
                "f3",
                "f4",
                "f1 academy",
                "euroformula",
                "eurocup-3",
                "super formula",
                "usf",
            )
        )
    if group == "gt_sportscar":
        return any(
            token in n
            for token in (
                " gt",
                "gt ",
                "gt3",
                "gt4",
                "bmw",
                "ferrari challenge",
                "porsche",
                "carrera cup",
                "sprint challenge",
                "supercup",
                "alpine elf cup",
                "992",
                "mclaren",
                "lamborghini",
                "aston martin",
                "audi",
                "mercedes",
                "amg",
                "intercontinental gt challenge",
                "international gt open",
                "super gt",
                "dtm",
                "deutsche tourenwagen masters",
            )
        )
    if group == "endurance_proto":
        return any(
            token in n
            for token in (
                "endurance",
                "le mans",
                "24h",
                "24 hours",
                "1000km",
                "1006km",
                "6 hour",
                "12 horas",
                "prototype",
                "imsa",
                "sportscar",
                "sportscar championship",
                "world endurance championship",
            )
        )
    if group == "nascar_oval":
        return any(
            token in n
            for token in (
                "indycar",
                "indy nxt",
                "nascar",
                "arca",
                "late model",
                "sprintcar",
                "sprint car",
                "modified",
                "menards",
                "supermodified",
            )
        )
    if group == "touring_stock":
        return any(
            token in n
            for token in (
                "touring",
                "tcr",
                "stock car pro series",
                "supercars championship",
                "truck",
                "clio cup",
                "bmw 318ti",
                "tourenwagen",
            )
        )
    if group == "rally_raid_rx":
        return any(token in n for token in ("rally", "rallycross", "dakar", "raid", "rx"))
    if group == "moto_bike":
        return any(token in n for token in ("moto", "superbike", "motocross", "arenacross", "speedway", "road racing", "sgp", "supercross", "superenduro"))
    if group == "dirt_drift_offroad":
        return any(token in n for token in ("drift", "off road", "off-road", "snocross", "flat track", "dirt", "toboggan"))
    return False


def _series_primary_group(name: str) -> str:
    for group in (
        "formula",
        "gt_sportscar",
        "endurance_proto",
        "nascar_oval",
        "touring_stock",
        "rally_raid_rx",
        "moto_bike",
        "dirt_drift_offroad",
    ):
        if _series_matches_group(name, group):
            return group
    return "other"

_SERIES_SUBGROUPS: dict[str, list[tuple[str, str, tuple[str, ...]]]] = {
    "formula": [
        ("fm", "Formula", ("formula 1", "formula 2", "formula 3", "formula e")),
        ("sf", "Super Formula", ("super formula", "super formula lights")),
        ("f4", "F4", ("formula 4 world cup", " f4", "f4 ")),
        ("fr", "Formula Regional", ("formula regional", "toyota formula regional")),
        ("us", "Road to Indy / USF", ("usf",)),
    ],
    "endurance_proto": [
        ("we", "WEC", ("wec", "world endurance championship", "fia world endurance championship")),
        ("im", "IMSA", ("imsa", "sportscar championship", "michelin pilot challenge", "vp racing sportscar challenge")),
        ("el", "ELMS", ("european le mans series", "elms")),
        ("as", "Asian Le Mans", ("asian le mans series", "asia le mans series", "aslms")),
        ("lp", "Le Mans Cup / Prototype Cup", ("le mans cup", "prototype cup", "prototype winter series")),
        ("24", "24H Series", ("24h series", "24h series european", "24h series middle east", "24 hours of nürburgring", "24 hours of nurburgring")),
    ],
    "gt_sportscar": [
        ("po", "Porsche", ("porsche", "carrera cup", "supercup", "992", "sprint challenge")),
        ("fe", "Ferrari Challenge", ("ferrari challenge", "ferrari world final")),
        ("gw", "GT World Challenge", ("gt world challenge", "intercontinental gt challenge")),
        ("gt", "GT", ("adac gt masters", "british gt", "china gt", "gt america", "gt cup", "gt winter series", "gt2", "super gt", "international gt open", "italian gt", "spain gt", "sro gt cup")),
        ("g4", "GT4", ("gt4",)),
        ("mc", "Марочные кубки", ("bmw", "m2 cup", "m4 cup", "alpine elf cup", "ginetta gt", "amg cup", "radical cup", "mustang cup", "toyota gazoo racing", "mazda mx-5 cup", "japan cup")),
    ],
    "touring_stock": [
        ("tc", "Touring Cars", ("touring car", "touring cars", "british touring car", "china touring car", "touring car masters", "touring championship")),
        ("cr", "TCR", ("tcr",)),
        ("tr", "Trucks", ("truck", "trucks", "copa truck", "truck racing", "european truck racing", "british truck racing", "nascar craftsman truck series", "stadium super trucks", "trucks mexico series")),
        ("st", "Stock Cars South America", ("stock car pro series", "stock light", "supercars championship")),
    ],
    "nascar_oval": [
        ("in", "IndyCar", ("indycar", "indy nxt")),
        ("cu", "NASCAR Cup", ("nascar cup series",)),
        ("ns", "NASCAR support", ("nascar craftsman truck series", "nascar brasil", "nascar canada", "nascar méxico", "nascar mexico", "nascar euro series", "nascar o'reilly", "nascar whelen modified tour", "nascar late model stock car")),
        ("ar", "ARCA", ("arca", "menards")),
        ("sm", "Sprint Cars / Modified / Late Models", ("late model", "sprint car", "sprintcar", "modified", "supermodified", "cars tour", "pro late model", "smart modified tour", "whelen modified tour", "world of outlaws", "big block modifieds", "short track super series")),
    ],
    "rally_raid_rx": [
        ("wr", "WRC", ("world rally championship", "wrc")),
        ("er", "ERC", ("european rally championship",)),
        ("rx", "Rallycross", ("rallycross", "rallyx", "rallycross world cup")),
        ("rd", "Dakar / Raid", ("dakar", "raid")),
        ("rt", "National Rally", ("rallyes", "rally show", "assoluto rally", "rally terra", "jnnerrallye", "monza rally show")),
    ],
    "moto_bike": [
        ("gp", "MotoGP", ("motogp", "moto2", "moto3", "motoe", "moto4", "motoamerica talent cup", "red bull motogp rookies cup")),
        ("sb", "Superbike", ("superbike",)),
        ("am", "AMA", ("ama ", "motoamerica")),
        ("fm", "FIM", ("fim ",)),
    ],
    "other": [
        ("jr", "Junior / feeder", ("gb3", "gb4", "au4", "e4 championship", "uae4", "spanish winter championship", "ginetta junior", "ligier european series")),
        ("ka", "Karting", ("karting",)),
        ("dr", "Drag racing", ("nhra", "ihra", "ndrc", "top fuel", "nitro", "pro mod", "drag racing")),
        ("di", "Short track / dirt", ("chili bowl", "tulsa shootout", "midgets", "all star circuit", "ascs", "imca", "world 100", "wild west shootout", "floracing night in america", "high limit", "snowball derby", "world series of asphalt")),
        ("cu", "Cups / club racing", ("mx-5 cup", "radical cup", "mustang cup", "mustang challenge", "gr cup", "toyota gazoo racing", "mitjet", "japan cup", "ultimate cup", "scca runoffs", "nasa championships", "hoosier racing tire scca super tour", "inex legend cars", "legend cars", "aussie racing cars")),
        ("tn", "Turismo / national", ("turismo", "tc2000", "tc america", "tc france", "tc mouras", "tc pick up", "tc pickup", "tc pista", "top race v6", "stock light", "copa hyundai hb20", "trans am", "super2 series", "v8 superute")),
        ("hh", "Historic / hillclimb", ("goodwood", "historique", "pikes peak", "time attack", "members' meeting", "revival", "festival of speed", "international race of champions")),
        ("bm", "Bikes other", ("isle of man tt", "north west 200", "southern 100", "campionato italiano velocità", "supersport world championship", "world sportbike championship", "yamaha r3", "harley-davidson bagger", "women's circuit racing world championship")),
        ("sp", "Special / adventure", ("x games", "king of the hammers", "crandon", "red bull crandon", "score world desert", "snowmobile derby", "enduropale", "e1 world championship", "extreme h", "f1h20", "race for the million", "world championship snowmobile derby")),
    ],
}

_SERIES_SUBGROUP_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "formula": {
        "fm": {"ru": "Formula", "en": "Formula"},
        "sf": {"ru": "Super Formula", "en": "Super Formula"},
        "f4": {"ru": "F4", "en": "F4"},
        "fr": {"ru": "Formula Regional", "en": "Formula Regional"},
        "us": {"ru": "Road to Indy / USF", "en": "Road to Indy / USF"},
    },
    "endurance_proto": {
        "we": {"ru": "WEC", "en": "WEC"},
        "im": {"ru": "IMSA", "en": "IMSA"},
        "el": {"ru": "ELMS", "en": "ELMS"},
        "as": {"ru": "Asian Le Mans", "en": "Asian Le Mans"},
        "lp": {"ru": "Le Mans Cup / Prototype Cup", "en": "Le Mans Cup / Prototype Cup"},
        "24": {"ru": "24H Series", "en": "24H Series"},
    },
    "gt_sportscar": {
        "po": {"ru": "Porsche", "en": "Porsche"},
        "fe": {"ru": "Ferrari Challenge", "en": "Ferrari Challenge"},
        "gw": {"ru": "GT World Challenge", "en": "GT World Challenge"},
        "gt": {"ru": "GT", "en": "GT"},
        "g4": {"ru": "GT4", "en": "GT4"},
        "mc": {"ru": "Марочные кубки", "en": "One-make Cups"},
    },
    "touring_stock": {
        "tc": {"ru": "Touring Cars", "en": "Touring Cars"},
        "cr": {"ru": "TCR", "en": "TCR"},
        "tr": {"ru": "Trucks", "en": "Trucks"},
        "st": {"ru": "Stock Cars South America", "en": "Stock Cars South America"},
    },
    "nascar_oval": {
        "in": {"ru": "IndyCar", "en": "IndyCar"},
        "cu": {"ru": "NASCAR Cup", "en": "NASCAR Cup"},
        "ns": {"ru": "NASCAR support", "en": "NASCAR Support"},
        "ar": {"ru": "ARCA", "en": "ARCA"},
        "sm": {"ru": "Sprint Cars / Modified / Late Models", "en": "Sprint Cars / Modified / Late Models"},
    },
    "rally_raid_rx": {
        "wr": {"ru": "WRC", "en": "WRC"},
        "er": {"ru": "ERC", "en": "ERC"},
        "rx": {"ru": "Rallycross", "en": "Rallycross"},
        "rd": {"ru": "Dakar / Raid", "en": "Dakar / Raid"},
        "rt": {"ru": "National Rally", "en": "National Rally"},
    },
    "moto_bike": {
        "gp": {"ru": "MotoGP", "en": "MotoGP"},
        "sb": {"ru": "Superbike", "en": "Superbike"},
        "am": {"ru": "AMA", "en": "AMA"},
        "fm": {"ru": "FIM", "en": "FIM"},
    },
    "other": {
        "jr": {"ru": "Junior / feeder", "en": "Junior / Feeder"},
        "ka": {"ru": "Karting", "en": "Karting"},
        "dr": {"ru": "Drag racing", "en": "Drag Racing"},
        "di": {"ru": "Short track / dirt", "en": "Short Track / Dirt"},
        "cu": {"ru": "Cups / club racing", "en": "Cups / Club Racing"},
        "tn": {"ru": "Turismo / national", "en": "Turismo / National"},
        "hh": {"ru": "Historic / hillclimb", "en": "Historic / Hillclimb"},
        "bm": {"ru": "Bikes other", "en": "Other Bikes"},
        "sp": {"ru": "Special / adventure", "en": "Special / Adventure"},
    },
}

_SERIES_NESTED_SUBGROUP_LABELS: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "gt_sportscar": {
        "po": {
            "su": {"ru": "Porsche Supercup", "en": "Porsche Supercup"},
            "ca": {"ru": "Porsche Carrera Cup", "en": "Porsche Carrera Cup"},
            "sp": {"ru": "Porsche Sprint Challenge", "en": "Porsche Sprint Challenge"},
            "en": {"ru": "Porsche Endurance", "en": "Porsche Endurance"},
        },
    },
}

_SERIES_NESTED_SUBGROUPS: dict[str, dict[str, list[tuple[str, str, tuple[str, ...]]]]] = {
    "gt_sportscar": {
        "po": [
            ("su", "Porsche Supercup", ("porsche supercup", "porsche carrera world cup")),
            ("ca", "Porsche Carrera Cup", ("porsche carrera cup",)),
            ("sp", "Porsche Sprint Challenge", ("porsche sprint challenge", "porsche sprint trophy")),
            ("en", "Porsche Endurance", ("porsche endurance", "992 endurance cup")),
        ],
    },
}

_SUBGROUP_PATH_SEPARATOR = "."

_SERIES_SUBGROUP_CODES_REV: dict[str, dict[str, str]] = {
    group: {code: label for code, label, _tokens in items}
    for group, items in _SERIES_SUBGROUPS.items()
}


def _series_order_key(series: dict, group: str) -> tuple[int, str]:
    name = series.get("name", "")
    lower_name = _series_name(name)
    if group == "popular":
        popular_idx = _popular_series_index(name)
        if popular_idx is not None:
            return (popular_idx, name)
    priorities: dict[str, tuple[str, ...]] = {
        "formula": (
            "formula 1",
            "formula 2",
            "formula 3",
            "formula e",
            "super formula",
            "formula 4 world cup",
            "formula regional",
            "usf",
        ),
        "gt_sportscar": (
            "porsche supercup",
            "porsche carrera cup",
            "ferrari challenge",
            "gt world challenge",
            "intercontinental gt challenge",
            "super gt",
            "dtm",
            "gt4",
        ),
        "endurance_proto": (
            "world endurance championship",
            "imsa",
            "european le mans series",
            "asian le mans series",
            "le mans cup",
            "prototype cup",
            "24h series",
        ),
        "touring_stock": (
            "supercars championship",
            "tcr world tour",
            "british touring car championship",
            "touring car masters",
            "european truck racing championship",
            "stock car pro series",
        ),
        "nascar_oval": (
            "indycar",
            "indy nxt",
            "nascar cup series",
            "nascar craftsman truck series",
            "arca menards series",
        ),
        "moto_bike": (
            "motogp",
            "moto2",
            "moto3",
            "superbike world championship",
            "motoamerica",
        ),
        "rally_raid_rx": (
            "world rally championship",
            "european rally championship",
            "rallyx",
            "dakar rally",
        ),
        "dirt_drift_offroad": (
            "formula drift",
        ),
    }
    for idx, token in enumerate(priorities.get(group, ())):
        if token in lower_name:
            return (idx, name)
    if name in DEFAULT_SERIES_NAMES:
        return (10 + DEFAULT_SERIES_NAMES.index(name), name)
    return (20, name)


def _label_text(entry: dict[str, str], lang: str) -> str:
    return entry.get(lang) or entry.get("ru") or next(iter(entry.values()))


def _series_subgroup_label(group: str, subgroup: str, lang: str = DEFAULT_UI_LANG) -> str:
    parent, child = _split_subgroup(subgroup)
    if child:
        labels = _SERIES_NESTED_SUBGROUP_LABELS.get(group, {}).get(parent, {}).get(child)
        if labels:
            return _label_text(labels, lang)
    for code, _label, _tokens in _SERIES_SUBGROUPS.get(group, []):
        if code == parent:
            return _label_text(_SERIES_SUBGROUP_LABELS.get(group, {}).get(code, {"ru": code}), lang)
    defs = _subgroup_defs(group, parent)
    for code, _label, _tokens in defs:
        if code == child:
            if child and parent:
                labels = _SERIES_NESTED_SUBGROUP_LABELS.get(group, {}).get(parent, {}).get(code, {"ru": code})
                return _label_text(labels, lang)
    if child and parent:
        return _series_subgroup_label(group, parent, lang)
    if parent == "ot":
        return "Other" if lang == "en" else "Остальное"
    if child == "ot":
        return f"{'Other' if lang == 'en' else 'Остальное'} {_series_subgroup_label(group, parent, lang)}"
    return "Other" if lang == "en" else "Остальное"


def series_subgroup_label(group: str, subgroup: str, lang: str = DEFAULT_UI_LANG) -> str:
    return _series_subgroup_label(group, subgroup, lang)


def _split_subgroup(subgroup: str) -> tuple[str, str]:
    if _SUBGROUP_PATH_SEPARATOR in subgroup:
        parent, child = subgroup.split(_SUBGROUP_PATH_SEPARATOR, 1)
        return parent, child
    return subgroup, ""


def _subgroup_defs(group: str, subgroup: str = "") -> list[tuple[str, str, tuple[str, ...]]]:
    if subgroup:
        return _SERIES_NESTED_SUBGROUPS.get(group, {}).get(subgroup, [])
    return _SERIES_SUBGROUPS.get(group, [])


def _series_subgroup_match(name: str, group: str, subgroup: str) -> bool:
    n = _series_name(name)
    parent, child = _split_subgroup(subgroup)
    if child == "ot":
        nested_defs = _subgroup_defs(group, parent)
        return _series_subgroup_match(name, group, parent) and not any(
            any(token in n for token in tokens)
            for _code, _label, tokens in nested_defs
        )
    if child:
        for code, _label, tokens in _subgroup_defs(group, parent):
            if code == child:
                return any(token in n for token in tokens)
        return False
    for code, _label, tokens in _SERIES_SUBGROUPS.get(group, []):
        if code == parent:
            if group == "moto_bike" and parent == "am" and "talent cup" in n:
                return False
            return any(token in n for token in tokens)
    return False


def _series_has_subgroups(group: str, items: list[dict], subgroup: str = "") -> bool:
    defs = _subgroup_defs(group, subgroup)
    if not defs:
        return False
    matches = 0
    for code, _label, _tokens in defs:
        code_to_match = f"{subgroup}{_SUBGROUP_PATH_SEPARATOR}{code}" if subgroup else code
        if any(_series_subgroup_match(item.get("name", ""), group, code_to_match) for item in items):
            matches += 1
    return matches > 0


def series_has_subgroups(group: str, items: list[dict], subgroup: str = "") -> bool:
    return _series_has_subgroups(group, items, subgroup)


def series_group_label(group: str, lang: str = DEFAULT_UI_LANG) -> str:
    if group in _SERIES_GROUP_LABELS:
        return _label_text(_SERIES_GROUP_LABELS[group], lang)
    return group or ("All Series" if lang == "en" else "Все серии")


def filter_series_by_group(
    all_series: list[dict],
    group: str,
    subscribed_ids: set[str] | None = None,
    subgroup: str = "",
) -> list[dict]:
    sorted_series = sorted(all_series, key=lambda s: s.get("name", ""))
    if not group or group == "all":
        return sorted_series

    if group == "mine":
        subscribed_ids = subscribed_ids or set()
        return [s for s in sorted_series if s.get("id") in subscribed_ids]

    if group == "popular":
        result = [s for s in sorted_series if _popular_series_index(s.get("name", "")) is not None]
        return sorted(result, key=lambda s: _series_order_key(s, group))

    grouped_names = _series_group_names()
    if group in grouped_names:
        names = grouped_names[group]
        result = [s for s in sorted_series if s.get("name", "") in names]
        result = sorted(result, key=lambda s: _series_order_key(s, group))
        if subgroup:
            parent, child = _split_subgroup(subgroup)
            if subgroup == "ot":
                result = [s for s in result if not any(
                    _series_subgroup_match(s.get("name", ""), group, code)
                    for code, _label, _tokens in _SERIES_SUBGROUPS.get(group, [])
                )]
            elif child == "ot":
                result = [s for s in result if _series_subgroup_match(s.get("name", ""), group, subgroup)]
            elif child or _subgroup_defs(group, parent):
                result = [s for s in result if _series_subgroup_match(s.get("name", ""), group, subgroup)]
            else:
                result = [s for s in result if _series_subgroup_match(s.get("name", ""), group, subgroup)]
        return result

    result = [s for s in sorted_series if _series_primary_group(s.get("name", "")) == group]
    result = sorted(result, key=lambda s: _series_order_key(s, group))
    if subgroup:
        parent, child = _split_subgroup(subgroup)
        if subgroup == "ot":
            result = [s for s in result if not any(
                _series_subgroup_match(s.get("name", ""), group, code)
                for code, _label, _tokens in _SERIES_SUBGROUPS.get(group, [])
            )]
        elif child == "ot":
            result = [s for s in result if _series_subgroup_match(s.get("name", ""), group, subgroup)]
        elif child or _subgroup_defs(group, parent):
            result = [s for s in result if _series_subgroup_match(s.get("name", ""), group, subgroup)]
        else:
            result = [s for s in result if _series_subgroup_match(s.get("name", ""), group, subgroup)]
    return result


def series_subgroup_menu(
    all_series: list[dict],
    group: str,
    subscribed_ids: set[str],
    subgroup: str = "",
    lang: str = DEFAULT_UI_LANG,
) -> InlineKeyboardMarkup:
    items = filter_series_by_group(all_series, group, subscribed_ids, subgroup=subgroup)
    rows: list[list[InlineKeyboardButton]] = []
    defs = _subgroup_defs(group, subgroup)
    for code, _label, _tokens in defs:
        code_value = f"{subgroup}{_SUBGROUP_PATH_SEPARATOR}{code}" if subgroup else code
        count = len(filter_series_by_group(all_series, group, subscribed_ids, subgroup=code_value))
        if count == 0:
            continue
        label = series_subgroup_label(group, code_value, lang)
        rows.append([InlineKeyboardButton(
            text=f"{label} · {count}",
            callback_data=SeriesBrowseCD(
                group=series_group_to_callback(group),
                page=0,
                subgroup=code_value,
            ).pack(),
        )])
    other_value = f"{subgroup}{_SUBGROUP_PATH_SEPARATOR}ot" if subgroup else "ot"
    other_prefix = "Other" if lang == "en" else "Остальное"
    other_label = f"{other_prefix} {series_subgroup_label(group, subgroup, lang)}" if subgroup else other_prefix
    other_count = len(filter_series_by_group(all_series, group, subscribed_ids, subgroup=other_value))
    if other_count:
        rows.append([InlineKeyboardButton(
            text=f"{other_label} · {other_count}",
            callback_data=SeriesBrowseCD(
                group=series_group_to_callback(group),
                page=0,
                subgroup=other_value,
            ).pack(),
        )])
    parent_subgroup, _child_subgroup = _split_subgroup(subgroup)
    back_group = series_group_to_callback(group if subgroup else "menu")
    back_subgroup = "" if not subgroup else ""
    if _SUBGROUP_PATH_SEPARATOR in subgroup:
        back_group = series_group_to_callback(group)
        back_subgroup = parent_subgroup
    rows.append([InlineKeyboardButton(
        text=("◀️ Back to Subgroups" if subgroup else "◀️ Back to Groups") if lang == "en" else ("◀️ К подгруппам" if subgroup else "◀️ К группам"),
        callback_data=SeriesBrowseCD(group=series_group_to_callback("menu"), page=0).pack(),
    )])
    if subgroup:
        rows[-1][0].callback_data = SeriesBrowseCD(
            group=back_group,
            page=0,
            subgroup=back_subgroup,
        ).pack()
    return InlineKeyboardMarkup(inline_keyboard=rows)


def series_group_menu(all_series: list[dict], subscribed_ids: set[str], lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key in _SERIES_GROUPS:
        count = len(filter_series_by_group(all_series, key, subscribed_ids))
        label = series_group_label(key, lang)
        rows.append([InlineKeyboardButton(
            text=f"{label} · {count}",
            callback_data=SeriesBrowseCD(group=series_group_to_callback(key), page=0).pack(),
        )])
    rows.append([InlineKeyboardButton(text=tr(lang, "menu.back"), callback_data="subs_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def timezone_picker(page: int = 0, lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    per = 8
    zones = POPULAR_TIMEZONES[page * per: (page + 1) * per]
    
    # Группируем кнопки часовых поясов в строки по 2 столбца
    rows = []
    for i in range(0, len(zones), 2):
        row = [InlineKeyboardButton(text=f"🕐 {tz}", callback_data=f"tz:{tz}") 
               for tz in zones[i:i+2]]
        rows.append(row)
    
    # Навигационные кнопки (◀️ ▶️)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"tz_page:{page-1}"))
    if (page + 1) * per < len(POPULAR_TIMEZONES):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"tz_page:{page+1}"))
    if nav:
        rows.append(nav)
    
    # Кнопка ручного ввода
    rows.append([InlineKeyboardButton(text=tr(lang, "menu.enter_manually"), callback_data="tz:manual")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


def series_list(
    all_series:    list[dict],
    subscribed_ids: set[str],
    group:         str = "all",
    subgroup:      str = "",
    page:          int = 0,
    page_size:     int = 8,
    lang:          str = DEFAULT_UI_LANG,
) -> InlineKeyboardMarkup:
    filtered_series = filter_series_by_group(all_series, group, subscribed_ids, subgroup=subgroup)
    chunk = filtered_series[page * page_size: (page + 1) * page_size]
    btns = []
    for s in chunk:
        check = "✅ " if s["id"] in subscribed_ids else ""
        btns.append([
            InlineKeyboardButton(
                text=f"{check}{s.get('name','?')[:38]}",
                callback_data=SubToggleCD(
                    type="series",
                    ref_id=s["id"],
                    page=page,
                    group=series_group_to_callback(group),
                    subgroup=subgroup,
                ).pack(),
            ),
            InlineKeyboardButton(
                text="ℹ️",
                callback_data=SeriesInfoCD(
                    ref_id=s["id"],
                    group=series_group_to_callback(group),
                    page=page,
                    subgroup=subgroup,
                ).pack(),
            ),
        ])
    nav: list[InlineKeyboardButton] = []
    total = (len(filtered_series) - 1) // page_size + 1 if filtered_series else 1
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️",
            callback_data=SeriesBrowseCD(
                group=series_group_to_callback(group),
                page=page - 1,
                subgroup=subgroup,
            ).pack(),
        ))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if (page + 1) * page_size < len(filtered_series):
        nav.append(InlineKeyboardButton(
            text="▶️",
            callback_data=SeriesBrowseCD(
                group=series_group_to_callback(group),
                page=page + 1,
                subgroup=subgroup,
            ).pack(),
        ))
    if nav:
        btns.append(nav)
    back_subgroup = "" if subgroup else "menu"
    back_group = series_group_to_callback(group if subgroup else "menu")
    if _SUBGROUP_PATH_SEPARATOR in subgroup:
        back_subgroup = subgroup.split(_SUBGROUP_PATH_SEPARATOR, 1)[0]
        back_group = series_group_to_callback(group)
    btns.append([InlineKeyboardButton(
        text=f"◀️ {'К подгруппам' if subgroup else 'К группам'}" if lang == "ru" else f"◀️ {'Back to Subgroups' if subgroup else 'Back to Groups'}",
        callback_data=SeriesBrowseCD(
            group=back_group,
            page=0,
            subgroup=back_subgroup,
        ).pack(),
    )])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def class_list(
    all_classes:   list[dict],
    subscribed_ids: set[str],
    lang: str = DEFAULT_UI_LANG,
) -> InlineKeyboardMarkup:
    btns = []
    row: list[InlineKeyboardButton] = []
    for vc in all_classes:
        check = "✅ " if vc["id"] in subscribed_ids else ""
        row.append(InlineKeyboardButton(
            text=f"{check}{vc.get('name','?')}",
            callback_data=SubToggleCD(type="vehicle_class", ref_id=vc["id"]).pack(),
        ))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton(text=tr(lang, "menu.back"), callback_data="subs_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def session_actions(session_id: str, is_fav: bool, lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    fav_text = tr(lang, "menu.favorite_remove") if is_fav else tr(lang, "menu.favorite_add")
    fav_action = "remove" if is_fav else "add"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=fav_text,
            callback_data=FavCD(action=fav_action, session_id=session_id).pack(),
        ),
        InlineKeyboardButton(
            text=tr(lang, "menu.remind"),
            callback_data=RemindCD(action="menu", session_id=session_id).pack(),
        ),
    ]])


def reminder_menu(session_id: str, active_types: set[str], lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    def label(remind_type: str, title: str) -> str:
        return f"{'✅ ' if remind_type in active_types else ''}{title}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=label("1day", tr(lang, "menu.remind_1day")),
            callback_data=RemindCD(action="toggle", session_id=session_id, remind_type="1day").pack(),
        )],
        [InlineKeyboardButton(
            text=label("1hour", tr(lang, "menu.remind_1hour")),
            callback_data=RemindCD(action="toggle", session_id=session_id, remind_type="1hour").pack(),
        )],
        [InlineKeyboardButton(
            text=label("start", tr(lang, "menu.remind_start")),
            callback_data=RemindCD(action="toggle", session_id=session_id, remind_type="start").pack(),
        )],
        [InlineKeyboardButton(text=tr(lang, "menu.back_to_session"), callback_data=f"session:{session_id}")],
    ])


def history_filter_menu(
    filter_type: str,
    ref_id: str,
    page: int,
    total_pages: int,
    lang: str = DEFAULT_UI_LANG,
) -> InlineKeyboardMarkup:
    def marker(value: str) -> str:
        return "✅ " if filter_type == value else ""

    rows = [
        [
            InlineKeyboardButton(
                text=f"{marker('all')}{tr(lang, 'menu.all')}",
                callback_data=HistoryViewCD(filter_type="all", page=0).pack(),
            ),
            InlineKeyboardButton(
                text=f"{marker('race')}{tr(lang, 'menu.races')}",
                callback_data=HistoryViewCD(filter_type="race", page=0).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{marker('qualifying')}{tr(lang, 'menu.qualifying')}",
                callback_data=HistoryViewCD(filter_type="qualifying", page=0).pack(),
            ),
            InlineKeyboardButton(
                text=f"{marker('practice')}{tr(lang, 'menu.practice')}",
                callback_data=HistoryViewCD(filter_type="practice", page=0).pack(),
            ),
        ],
        [
            InlineKeyboardButton(text=tr(lang, "menu.by_series"), callback_data=HistoryPickCD(kind="series", page=0).pack()),
            InlineKeyboardButton(text=tr(lang, "menu.by_class"), callback_data=HistoryPickCD(kind="vehicle_class", page=0).pack()),
        ],
    ]

    if filter_type in {"series", "vehicle_class"} and ref_id:
        rows.append([
            InlineKeyboardButton(
                text=tr(lang, "menu.reset_filter"),
                callback_data=HistoryViewCD(filter_type="all", page=0).pack(),
            )
        ])

    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text="◀️",
                callback_data=HistoryViewCD(filter_type=filter_type, ref_id=ref_id, page=page - 1).pack(),
            ))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton(
                text="▶️",
                callback_data=HistoryViewCD(filter_type=filter_type, ref_id=ref_id, page=page + 1).pack(),
            ))
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_pick_menu(
    kind: str,
    items: list[dict],
    page: int = 0,
    page_size: int = 8,
    lang: str = DEFAULT_UI_LANG,
) -> InlineKeyboardMarkup:
    chunk = items[page * page_size: (page + 1) * page_size]
    rows = []
    filter_type = "series" if kind == "series" else "vehicle_class"
    for item in chunk:
        rows.append([InlineKeyboardButton(
            text=item.get("ref_name", item.get("name", "?"))[:48],
            callback_data=HistoryViewCD(
                filter_type=filter_type,
                ref_id=item["ref_id"],
                page=0,
            ).pack(),
        )])

    total = (len(items) - 1) // page_size + 1 if items else 1
    if total > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=HistoryPickCD(kind=kind, page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data="noop"))
        if page + 1 < total:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=HistoryPickCD(kind=kind, page=page + 1).pack()))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text=tr(lang, "menu.back_to_history"), callback_data="history")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def digest_pick_menu(
    kind: str,
    subs: list[dict],
    page: int = 0,
    page_size: int = 8,
    lang: str = DEFAULT_UI_LANG,
) -> InlineKeyboardMarkup:
    chunk = subs[page * page_size: (page + 1) * page_size]
    rows = [[InlineKeyboardButton(
        text=tr(lang, "menu.all_subscriptions"),
        callback_data=DigestViewCD(kind=kind, action="view", scope="all", page=0, pick_page=page).pack(),
    )]]
    for sub in chunk:
        kind_icon = "🏎️" if sub["type"] == "series" else "🏷️"
        rows.append([InlineKeyboardButton(
            text=f"{kind_icon} {sub['ref_name'][:42]}",
            callback_data=DigestViewCD(
                kind=kind,
                action="view",
                scope=sub["type"],
                ref_id=sub["ref_id"][:8],
                page=0,
                pick_page=page,
            ).pack(),
        )])

    total = (len(subs) - 1) // page_size + 1 if subs else 1
    if total > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text="◀️",
                callback_data=DigestViewCD(kind=kind, action="pick", page=page - 1).pack(),
            ))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data="noop"))
        if page + 1 < total:
            nav.append(InlineKeyboardButton(
                text="▶️",
                callback_data=DigestViewCD(kind=kind, action="pick", page=page + 1).pack(),
            ))
        rows.append(nav)

    rows.append([InlineKeyboardButton(text=tr(lang, "menu.back_to_menu"), callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def digest_view_menu(
    kind: str,
    page: int,
    total_pages: int,
    selected_sub: dict | None = None,
    user: dict | None = None,
    pick_page: int = 0,
    allow_pick: bool = False,
    lang: str = DEFAULT_UI_LANG,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text="◀️",
                callback_data=DigestViewCD(
                    kind=kind,
                    action="view",
                    scope=selected_sub["type"] if selected_sub else "all",
                    ref_id=selected_sub["ref_id"][:8] if selected_sub else "",
                    page=page - 1,
                    pick_page=pick_page,
                ).pack(),
            ))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton(
                text="▶️",
                callback_data=DigestViewCD(
                    kind=kind,
                    action="view",
                    scope=selected_sub["type"] if selected_sub else "all",
                    ref_id=selected_sub["ref_id"][:8] if selected_sub else "",
                    page=page + 1,
                    pick_page=pick_page,
                ).pack(),
            ))
        rows.append(nav)

    if user:
        rows.append([
            InlineKeyboardButton(
                text=f"{'✅' if user.get('show_qualifying', 1) else '❌'} {tr(lang, 'menu.qualifying')}",
                callback_data=DigestViewCD(
                    kind=kind,
                    action="toggle",
                    scope=selected_sub["type"] if selected_sub else "all",
                    ref_id=selected_sub["ref_id"][:8] if selected_sub else "",
                    field="show_qualifying",
                    page=page,
                    pick_page=pick_page,
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"{'✅' if user.get('show_practice', 1) else '❌'} {tr(lang, 'menu.practice')}",
                callback_data=DigestViewCD(
                    kind=kind,
                    action="toggle",
                    scope=selected_sub["type"] if selected_sub else "all",
                    ref_id=selected_sub["ref_id"][:8] if selected_sub else "",
                    field="show_practice",
                    page=page,
                    pick_page=pick_page,
                ).pack(),
            ),
        ])

    if allow_pick:
        rows.append([InlineKeyboardButton(
            text=tr(lang, "menu.back"),
            callback_data=DigestViewCD(kind=kind, action="pick", page=pick_page).pack(),
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profile_menu(user: dict, lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    def tog(field: str) -> str:
        return ProfileToggleCD(field=field).pack()

    def icon(field: str) -> str:
        return "✅" if user.get(field) else "❌"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{tr(lang, 'menu.timezone')}: {user['timezone']}",
            callback_data="profile:tz",
        )],
        [InlineKeyboardButton(text=tr(lang, "menu.broadcast_languages"), callback_data="profile:langs")],
        [InlineKeyboardButton(
            text=f"{icon('digest_enabled')} {tr(lang, 'menu.monday_digest')} ({user['digest_time']})",
            callback_data=tog("digest_enabled"),
        )],
        [InlineKeyboardButton(
            text=f"{icon('show_no_broadcast')} {tr(lang, 'menu.without_broadcasts')}",
            callback_data=tog("show_no_broadcast"),
        )],
        [InlineKeyboardButton(
            text=f"{icon('quiet_enabled')} {tr(lang, 'menu.quiet_hours_state')} ({user['quiet_start']}:00–{user['quiet_end']}:00)",
            callback_data=tog("quiet_enabled"),
        )],
        [
            InlineKeyboardButton(text=f"{icon('notify_3days')} {'За 3 дня' if lang == 'ru' else '3 Days Before'}", callback_data=tog("notify_3days")),
            InlineKeyboardButton(text=f"{icon('notify_1day')} {tr(lang, 'menu.remind_1day')}",  callback_data=tog("notify_1day")),
        ],
        [
            InlineKeyboardButton(text=f"{icon('notify_1hour')} {tr(lang, 'menu.remind_1hour')}", callback_data=tog("notify_1hour")),
            InlineKeyboardButton(text=f"{icon('notify_start')} {'Старт' if lang == 'ru' else 'Start'}", callback_data=tog("notify_start")),
        ],
        [InlineKeyboardButton(text=tr(lang, "menu.notification_details"), callback_data="subs:notify")],
        [InlineKeyboardButton(text=tr(lang, "menu.digest_time"), callback_data="profile:digest_time")],
        [InlineKeyboardButton(text=tr(lang, "menu.quiet_hours"), callback_data="profile:quiet_hours")],
        [InlineKeyboardButton(text=tr(lang, "menu.back_to_menu"), callback_data="main_menu")],
    ])


_LANG_OPTIONS: list[tuple[str, str]] = [
    ("🇬🇧 English",    "English"),
    ("🇷🇺 Russian",    "Russian"),
    ("🇩🇪 German",     "German"),
    ("🇫🇷 French",     "French"),
    ("🇮🇹 Italian",    "Italian"),
    ("🇪🇸 Spanish",    "Spanish"),
    ("🇯🇵 Japanese",   "Japanese"),
    ("🇵🇹 Portuguese", "Portuguese"),
]


def lang_picker(current: list[str], lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    btns = []
    row: list[InlineKeyboardButton] = []
    for label, lid in _LANG_OPTIONS:
        check = "✅ " if lid in current else ""
        row.append(InlineKeyboardButton(
            text=f"{check}{label}",
            callback_data=LangToggleCD(lang_id=lid).pack(),
        ))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton(text=tr(lang, "menu.done"), callback_data="profile_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def kb_menu(series_kb: dict, lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    btns = [
        [InlineKeyboardButton(
            text=f"{info['emoji']} {name}",
            callback_data=KbShowCD(name=name).pack(),
        )]
        for name, info in series_kb.items()
    ]
    btns.append([InlineKeyboardButton(text=tr(lang, "menu.back_to_menu"), callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def subscriptions_notify_list(subs: list[dict], lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    rows = []
    for sub in subs:
        kind = "🏎️" if sub["type"] == "series" else "🏷️"
        rows.append([InlineKeyboardButton(
            text=f"{kind} {sub['ref_name']}",
            callback_data=SubNotifyCD(
                action="open",
                type=sub["type"],
                ref_id=sub["ref_id"][:8],
            ).pack(),
        )])
    rows.append([InlineKeyboardButton(text=tr(lang, "menu.back"), callback_data="profile_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_notify_menu(sub: dict, lang: str = DEFAULT_UI_LANG) -> InlineKeyboardMarkup:
    def icon(field: str) -> str:
        return "✅" if sub.get(field, 1) else "❌"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{icon('qualifying_notify')} {tr(lang, 'menu.qualifying')}",
            callback_data=SubNotifyCD(
                action="toggle",
                type=sub["type"],
                ref_id=sub["ref_id"][:8],
                field="qualifying_notify",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text=f"{icon('practice_notify')} {tr(lang, 'menu.qualifying_and_tests')}",
            callback_data=SubNotifyCD(
                action="toggle",
                type=sub["type"],
                ref_id=sub["ref_id"][:8],
                field="practice_notify",
            ).pack(),
        )],
        [InlineKeyboardButton(text=tr(lang, "menu.back_to_list"), callback_data="subs:notify")],
    ])
