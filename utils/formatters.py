from datetime import datetime, timezone
from typing import Any

import pytz

from config import BROADCAST_TYPES

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

QUALIFYING_KEYWORDS = frozenset({
    "quali", "qualifying", "квали", "pole",
    "hyperpole", "shootout",
})

PRACTICE_KEYWORDS = frozenset({
    "practice", "fp1", "fp2", "fp3",
    "fp4", "warm-up", "warmup", "free practice",
    "test", "testing",
})


# ── Time helpers ──────────────────────────────────────────────────────────────

def to_local(ts: int, tz_name: str) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(pytz.timezone(tz_name))

def fmt_datetime(ts: int, tz_name: str) -> str:
    return to_local(ts, tz_name).strftime("%d %b %Y, %H:%M")

def fmt_time(ts: int, tz_name: str) -> str:
    return to_local(ts, tz_name).strftime("%H:%M")

def fmt_duration(minutes: int) -> str:
    match minutes // 60, minutes % 60:
        case 0, m: return f"{m} мин"
        case h, 0: return f"{h}ч"
        case h, m: return f"{h}ч {m}мин"

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


def _category_label(name: str) -> str:
    return _CATEGORY_LABELS.get(session_category(name), "🏁 Сессия")


def _local_day_label(ts: int, tz_name: str) -> str:
    return to_local(ts, tz_name).strftime("%a, %d %b").capitalize()


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
) -> str | None:
    bc = [b for b in broadcasts if any(l in b.get("langIds", []) for l in user_langs)]

    if not show_no_bc and not bc and not live_timings:
        return None

    name:     str  = session.get("name", "Гонка")
    start_ts: int  = session.get("start", 0)
    duration: int  = session.get("durationMinutes", 0)
    location: dict = session.get("location", {})
    notes:    str  = session.get("notes") or ""
    status:   int  = session.get("status", 0)
    emoji          = class_emojis(session)
    series_names   = " · ".join(s.get("name", "") for s in session.get("series", []))
    category_label = _category_label(name)

    if compact:
        t      = fmt_time(start_ts, user_tz) if start_ts else "?"
        bc_str = ""
        if bc:
            b0    = bc[0]
            desc  = b0.get("description") or "Трансляция"
            bc_str = f" · 📺 {desc}" + (" [$]" if b0.get("isPaid") else "")
        elif live_timings:
            bc_str = " · 📊 Live Timing"
        status_str = f" {_STATUS_LABELS[status]}" if status else ""
        series_str = f" · {series_names}" if series_names else ""
        return f"{t} · {category_label}\n{emoji} <b>{name}</b>{series_str}{status_str}{bc_str}"

    lines = [f"{emoji} <b>{name}</b>"]

    # Status (only show non-default)
    if status_label := _STATUS_LABELS.get(status, ""):
        lines.append(status_label)
    lines.append(category_label)

    if series_names:
        lines.append(f"📋 {series_names}")
    if start_ts and duration:
        lines.append(f"🕐 {fmt_datetime(start_ts, user_tz)} · {fmt_duration(duration)}")
    elif start_ts:
        lines.append(f"🕐 {fmt_datetime(start_ts, user_tz)}")
    elif duration:
        lines.append(f"⏱ {fmt_duration(duration)}")

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
                year_s = f" (с {year_opened})"
                if year_closed:
                    year_s = f" ({year_opened}–{year_closed})"
            lines.append(f"📍 {loc_str}{year_s}")

        if (lat := location.get("lat")) and (lon := location.get("lon")):
            lines.append(
                f"🗺 <a href='https://maps.google.com/?q={lat},{lon}'>Открыть на карте</a>"
            )

    if notes:
        lines.append(f"📝 {notes}")

    # Broadcasts
    if bc:
        lines.append("")
        lines.append("📺 <b>Трансляции</b>")
        for b in bc[:5]:
            desc   = b.get("description") or "Трансляция"
            url    = b.get("url", "")
            btype  = BROADCAST_TYPES.get(b.get("type"), "")
            paid   = " <b>[$]</b>" if b.get("isPaid") else ""
            geo    = " 🌍" if b.get("isGeoblocked") else ""
            langs  = f" [{' · '.join(b.get('langIds', []))}]" if b.get("langIds") else ""
            body   = f"<a href='{url}'>{desc}</a>" if url else desc
            lines.append(f"• {btype} {body}{paid}{geo}{langs}".strip())
    elif show_no_bc:
        lines.append("")
        lines.append("📺 Для выбранных языков трансляция пока не найдена")

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
            (header + "\n\n" if header else "") + "😴 Нет гонок по вашим подпискам."
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
) -> str:
    labels = {
        "3days": "🔔 Через 3 дня",
        "1day":  "🔔 Завтра",
        "1hour": "🚨 Через час",
        "start": "🏁 Сейчас начинается",
    }
    label = labels.get(notif_type, "🔔 Напоминание")
    card  = session_card(session, broadcasts, live_timings, user_tz, user_langs) or ""
    return f"{label}\n\n{card}"
