from datetime import date, datetime, timezone
from html import escape
from typing import Any

import pytz

from config import BROADCAST_TYPES
from utils.i18n import DEFAULT_UI_LANG, tr
from utils.rscg import RscgStage

type SessionDict   = dict[str, Any]
type BroadcastDict = dict[str, Any]

_CLASS_EMOJIS: dict[str, str] = {
    "Single-Seaters": "🏎️", "GT3": "🏆",  "GT4": "🥈",
    "Endurance":      "⏱️",  "Rally": "🚗", "Motorcycles": "🏍️",
    "Touring Cars":   "🚙",  "TCR":  "🚙", "Stock Cars": "🏁",
    "Oval Racing":    "🔄",  "Electric": "⚡", "Off-road Racing": "🌵",
    "Drag Racing":    "💨",  "Rallycross": "🌧️", "Prototypes": "🔬",
    "Sports Cars":    "🏅",  "Truck Racing": "🚛", "Karting": "🎮",
    "Drifting":       "💨",  "Motocross": "🏍️",
}

# Session status codes
_STATUS_LABELS: dict[int, str] = {
    0: "",           # unknown / default
    1: "🟢 Идёт",
    2: "✅ Завершена",
    3: "❌ Отменена",
    4: "⏸ Отложена",
}

_CATEGORY_LABELS: dict[str, str] = {
    "race": "🏁 Гонка",
    "qualifying": "🎯 Квалификация",
    "practice": "🛠 Практика",
}

_STATUS_LABELS_EN: dict[int, str] = {
    0: "",
    1: "🟢 Live",
    2: "✅ Finished",
    3: "❌ Cancelled",
    4: "⏸ Postponed",
}

_CATEGORY_LABELS_EN: dict[str, str] = {
    "race": "🏁 Race",
    "qualifying": "🎯 Qualifying",
    "practice": "🛠 Practice",
}

_MONTHS_RU = ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTHS_RU_FULL = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")
_MONTHS_EN_FULL = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
_DAYS_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
_DAYS_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

QUALIFYING_KEYWORDS = frozenset({
    "quali", "qualifying", "квали", "pole",
    "hyperpole", "shootout",
})

PRACTICE_KEYWORDS = frozenset({
    "practice", "fp1", "fp2", "fp3",
    "fp4", "warm-up", "warmup", "free practice",
    "test", "testing",
})

_SERIES_DISPLAY_ALIASES = {
    "IMSA WeatherTech SportsCar Championship": "IMSA WeatherTech Championship",
}


# ── Time helpers ──────────────────────────────────────────────────────────────

def to_local(ts: int, tz_name: str) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(pytz.timezone(tz_name))

def _month_name(dt: datetime, ui_lang: str) -> str:
    return (_MONTHS_EN if ui_lang == "en" else _MONTHS_RU)[dt.month - 1]


def _day_name(dt: datetime, ui_lang: str) -> str:
    return (_DAYS_EN if ui_lang == "en" else _DAYS_RU)[dt.weekday()]


def _month_name_date(value: date, ui_lang: str, *, short: bool = False) -> str:
    if ui_lang == "en":
        months = _MONTHS_EN if short else _MONTHS_EN_FULL
    else:
        months = _MONTHS_RU if short else _MONTHS_RU_FULL
    return months[value.month - 1]


def fmt_datetime(ts: int, tz_name: str, ui_lang: str = DEFAULT_UI_LANG) -> str:
    dt = to_local(ts, tz_name)
    return f"{dt.day:02d} {_month_name(dt, ui_lang)} {dt.year}, {dt:%H:%M}"


def fmt_time(ts: int, tz_name: str, ui_lang: str = DEFAULT_UI_LANG) -> str:
    return to_local(ts, tz_name).strftime("%H:%M")

def fmt_duration(minutes: int, ui_lang: str = DEFAULT_UI_LANG) -> str:
    match minutes // 60, minutes % 60:
        case 0, m: return f"{m} {'min' if ui_lang == 'en' else 'мин'}"
        case h, 0: return f"{h}{'h' if ui_lang == 'en' else 'ч'}"
        case h, m: return f"{h}{'h' if ui_lang == 'en' else 'ч'} {m}{'min' if ui_lang == 'en' else 'мин'}"

def is_qualifying(name: str) -> bool:
    low = name.lower()
    return any(k in low for k in QUALIFYING_KEYWORDS)

def is_practice(name: str) -> bool:
    low = name.lower()
    return any(k in low for k in PRACTICE_KEYWORDS)

def session_category(name: str) -> str:
    if is_qualifying(name):
        return "qualifying"
    if is_practice(name):
        return "practice"
    return "race"


def display_series_name(name: str) -> str:
    return _SERIES_DISPLAY_ALIASES.get(name, name)


def display_subject_icon(name: str, kind: str = "series") -> str:
    normalized = display_series_name(name or "").lower()

    if any(token in normalized for token in ("rookies", "junior", "juniors", "academy", "feeder", "f1 academy")):
        return "🧒"
    if any(token in normalized for token in ("motogp", "moto2", "moto3", "superbike", "motocross", "supercross", "motoamerica", "speedway")):
        return "🏍️"
    if any(token in normalized for token in ("kart", "karting")):
        return "🟨"
    if any(token in normalized for token in ("rallycross", "rally", "dakar", "raid", "wrc", "erc")):
        return "🚗"
    if any(token in normalized for token in ("touring", "tcr", "stock car", "truck", "supercars championship")):
        return "🚙"
    if any(token in normalized for token in ("nascar", "indycar", "indy nxt", "arca", "oval", "sprint car", "late model")):
        return "🏁"
    if any(token in normalized for token in ("wec", "world endurance championship", "endurance", "prototype", "hypercar", "lmp", "imsa")):
        return "⏱️"
    if any(token in normalized for token in ("gt3", "gt4", "gt ", " super gt", "sportscar", "porsche", "ferrari challenge", "lamborghini", "dtm")):
        return "🏎️"
    if any(token in normalized for token in ("formula", "f1", "f2", "f3", "f4", "formula e", "formula regional", "super formula")):
        return "🏎️"
    if kind == "vehicle_class":
        return "🏷️"
    return "🏁"


def _category_label(name: str, ui_lang: str = DEFAULT_UI_LANG) -> str:
    labels = _CATEGORY_LABELS_EN if ui_lang == "en" else _CATEGORY_LABELS
    fallback = "🏁 Session" if ui_lang == "en" else "🏁 Сессия"
    return labels.get(session_category(name), fallback)


def _local_day_label(ts: int, tz_name: str, ui_lang: str = DEFAULT_UI_LANG) -> str:
    dt = to_local(ts, tz_name)
    return f"{_day_name(dt, ui_lang)}, {dt.day:02d} {_month_name(dt, ui_lang)}"


def _format_date_range(start: date, end: date, ui_lang: str = DEFAULT_UI_LANG) -> str:
    if start == end:
        return f"{start.day} {_month_name_date(start, ui_lang)} {start.year}"
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {_month_name_date(start, ui_lang)} {start.year}"
    if start.year == end.year:
        return (
            f"{start.day} {_month_name_date(start, ui_lang)}"
            f" – {end.day} {_month_name_date(end, ui_lang)} {end.year}"
        )
    return (
        f"{start.day} {_month_name_date(start, ui_lang)} {start.year}"
        f" – {end.day} {_month_name_date(end, ui_lang)} {end.year}"
    )


# ── Visual helpers ────────────────────────────────────────────────────────────

def class_emojis(session: SessionDict) -> str:
    seen: dict[str, None] = {}
    for sr in session.get("series", []):
        for vc in sr.get("vehicleClasses", []):
            seen[_CLASS_EMOJIS.get(vc.get("name", ""), "🏁")] = None
    return "".join(seen) or "🏁"


# ── Session card ──────────────────────────────────────────────────────────────

def session_card(
    session:      SessionDict,
    broadcasts:   list[BroadcastDict],
    live_timings: list[dict],
    user_tz:      str,
    user_langs:   list[str],
    show_no_bc:   bool = True,
    compact:      bool = False,
    ui_lang:      str = DEFAULT_UI_LANG,
) -> str | None:
    bc = [b for b in broadcasts if any(l in b.get("langIds", []) for l in user_langs)]

    if not show_no_bc and not bc and not live_timings:
        return None

    name:     str  = session.get("name", "Race" if ui_lang == "en" else "Гонка")
    start_ts: int  = session.get("start", 0)
    duration: int  = session.get("durationMinutes", 0)
    location: dict = session.get("location", {})
    notes:    str  = session.get("notes") or ""
    status:   int  = session.get("status", 0)
    emoji          = class_emojis(session)
    series_names   = " · ".join(
        f"{display_subject_icon(s.get('name', ''), 'series')} {display_series_name(s.get('name', ''))}"
        for s in session.get("series", [])
        if s.get("name")
    )
    category_label = _category_label(name, ui_lang)

    if compact:
        t      = fmt_time(start_ts, user_tz) if start_ts else "?"
        bc_str = ""
        if bc:
            b0    = bc[0]
            desc  = b0.get("description") or ("Broadcast" if ui_lang == "en" else "Трансляция")
            bc_str = f" · 📺 {desc}" + (" [$]" if b0.get("isPaid") else "")
        elif live_timings:
            bc_str = " · 📊 Live Timing"
        labels = _STATUS_LABELS_EN if ui_lang == "en" else _STATUS_LABELS
        status_str = f" {labels[status]}" if status else ""
        series_str = f" · {series_names}" if series_names else ""
        return f"{t} · {category_label}\n{emoji} <b>{name}</b>{series_str}{status_str}{bc_str}"

    lines = [f"{emoji} <b>{name}</b>"]

    # Status (only show non-default)
    status_labels = _STATUS_LABELS_EN if ui_lang == "en" else _STATUS_LABELS
    if status_label := status_labels.get(status, ""):
        lines.append(status_label)
    lines.append(category_label)

    if series_names:
        lines.append(f"📋 {series_names}")
    if start_ts and duration:
        lines.append(f"🕐 {fmt_datetime(start_ts, user_tz, ui_lang)} · {fmt_duration(duration, ui_lang)}")
    elif start_ts:
        lines.append(f"🕐 {fmt_datetime(start_ts, user_tz, ui_lang)}")
    elif duration:
        lines.append(f"⏱ {fmt_duration(duration, ui_lang)}")

    # Location — use alternateName if available, fallback to name
    if location:
        display_name  = location.get("alternateName") or location.get("name", "")
        country       = location.get("country", "")
        region        = location.get("regionName", "")
        year_opened   = location.get("yearOpened")
        year_closed   = location.get("yearClosed")

        loc_parts = [p for p in (display_name, region, country) if p]
        if loc_str := ", ".join(loc_parts):
            year_s = ""
            if year_opened:
                year_s = f" ({'since' if ui_lang == 'en' else 'с'} {year_opened})"
                if year_closed:
                    year_s = f" ({year_opened}–{year_closed})"
            lines.append(f"📍 {loc_str}{year_s}")

        if (lat := location.get("lat")) and (lon := location.get("lon")):
            lines.append(
                f"🗺 <a href='https://maps.google.com/?q={lat},{lon}'>Открыть на карте</a>"
                if ui_lang == "ru"
                else f"🗺 <a href='https://maps.google.com/?q={lat},{lon}'>Open on map</a>"
            )

    if notes:
        lines.append(f"📝 {notes}")

    # Broadcasts
    if bc:
        lines.append("")
        lines.append("📺 <b>Broadcasts</b>" if ui_lang == "en" else "📺 <b>Трансляции</b>")
        for b in bc[:5]:
            desc   = b.get("description") or ("Broadcast" if ui_lang == "en" else "Трансляция")
            url    = b.get("url", "")
            btype  = BROADCAST_TYPES.get(b.get("type"), "")
            paid   = " <b>[$]</b>" if b.get("isPaid") else ""
            geo    = " 🌍" if b.get("isGeoblocked") else ""
            langs  = f" [{' · '.join(b.get('langIds', []))}]" if b.get("langIds") else ""
            body   = f"<a href='{url}'>{desc}</a>" if url else desc
            lines.append(f"• {btype} {body}{paid}{geo}{langs}".strip())
    elif show_no_bc:
        lines.append("")
        lines.append(
            "📺 No broadcast found yet for the selected languages"
            if ui_lang == "en"
            else "📺 Для выбранных языков трансляция пока не найдена"
        )

    if live_timings:
        lines.append("")
        lines.append("📊 <b>Live Timing</b>")
        for lt in live_timings[:3]:
            desc = lt.get("description", "Live Timing")
            url  = lt.get("url", "")
            lines.append("• " + (f"<a href='{url}'>{desc}</a>" if url else desc))

    return "\n".join(lines)


# ── Digest builder ────────────────────────────────────────────────────────────

def build_digest(
    sessions:       list[SessionDict],
    broadcasts_map: dict[str, list[BroadcastDict]],
    timings_map:    dict[str, list],
    user_tz:        str,
    user_langs:     list[str],
    show_no_bc:     bool = True,
    header:         str  = "",
    ui_lang:        str = DEFAULT_UI_LANG,
) -> list[str]:
    messages: list[str] = []
    current = header + "\n" if header else ""
    current_day = ""

    for s in sessions:
        sid  = s.get("id", "")
        card = session_card(
            s,
            broadcasts=broadcasts_map.get(sid, []),
            live_timings=timings_map.get(sid, []),
            user_tz=user_tz,
            user_langs=user_langs,
            show_no_bc=show_no_bc,
            ui_lang=ui_lang,
        )
        if card is None:
            continue
        day_heading = ""
        if s.get("start"):
            session_day = _local_day_label(s["start"], user_tz)
            if session_day != current_day:
                current_day = session_day
                day_heading = f"\n\n<b>{session_day}</b>\n"
        entry = f"{day_heading}\n{'─' * 30}\n{card}"
        if len(current) + len(entry) > 3_800:
            messages.append(current)
            current = ((header + "\n") if header else "") + entry.lstrip("\n")
        else:
            current += entry

    if current.strip():
        messages.append(current)
    if not messages:
        messages.append(
            (header + "\n\n" if header else "") +
            ("😴 No sessions found for your subscriptions." if ui_lang == "en" else "😴 Нет гонок по вашим подпискам.")
        )
    return messages


# ── Notification text ─────────────────────────────────────────────────────────

def notification_text(
    session:      SessionDict,
    broadcasts:   list[BroadcastDict],
    live_timings: list[dict],
    user_tz:      str,
    user_langs:   list[str],
    notif_type:   str,
    ui_lang:      str = DEFAULT_UI_LANG,
) -> str:
    labels = {
        "3days": "🔔 In 3 Days" if ui_lang == "en" else "🔔 Через 3 дня",
        "1day": "🔔 Tomorrow" if ui_lang == "en" else "🔔 Завтра",
        "1hour": "🚨 In 1 Hour" if ui_lang == "en" else "🚨 Через час",
        "start": "🏁 Starting Now" if ui_lang == "en" else "🏁 Сейчас начинается",
    }
    label = labels.get(notif_type, "🔔 Reminder" if ui_lang == "en" else "🔔 Напоминание")
    card  = session_card(session, broadcasts, live_timings, user_tz, user_langs, ui_lang=ui_lang) or ""
    return f"{label}\n\n{card}"


def rscg_stage_card(stage: RscgStage, user: dict) -> str:
    ui_lang = user.get("ui_lang", DEFAULT_UI_LANG)
    title = "SMP RSKG" if ui_lang == "en" else "СМП РСКГ"
    lines = [
        f"🏁 <b>{title} — {'Round' if ui_lang == 'en' else 'Этап'} {stage.round}</b>",
        f"🕐 {_format_date_range(stage.date_start, stage.date_end, ui_lang)}",
    ]

    location_parts = [escape(stage.track)]
    if stage.location:
        location_parts.append(escape(stage.location))
    lines.append(f"📍 {', '.join(location_parts)}")

    if stage.description:
        lines.append(f"📝 {escape(stage.description)}")
    if stage.sprint:
        lines.append(f"🏎️ {'Sprint' if ui_lang == 'en' else 'Спринт'}: {escape(stage.sprint)}")
    if stage.endurance:
        lines.append(f"⏱️ {'Endurance' if ui_lang == 'en' else 'Эндуранс'}: {escape(stage.endurance)}")
    if stage.additional:
        lines.append(f"ℹ️ {escape(stage.additional)}")
    if stage.note:
        lines.append(f"⚠️ {escape(stage.note)}")

    return "\n".join(lines)


def rscg_notification_text(
    stage: RscgStage,
    offset_label: str,
    ui_lang: str = DEFAULT_UI_LANG,
) -> str:
    labels = {
        "3days": "🔔 In 3 Days" if ui_lang == "en" else "🔔 Через 3 дня",
        "1day": "🔔 Tomorrow" if ui_lang == "en" else "🔔 Завтра",
        "start": "🏁 Starts Today" if ui_lang == "en" else "🏁 Сегодня",
    }
    label = labels.get(offset_label, "🔔 Reminder" if ui_lang == "en" else "🔔 Напоминание")
    card = rscg_stage_card(stage, {"ui_lang": ui_lang})
    return f"{label}\n\n{card}"
