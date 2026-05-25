from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from html import escape

from utils.i18n import DEFAULT_UI_LANG
from utils.formatters import display_series_name

_CLUSTER_GAP_SECONDS = 5 * 24 * 3600


@dataclass(slots=True)
class EventIdentity:
    key: str
    title: str
    sort_ts: int


def _slug(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _series_signature(session: dict, ui_lang: str = DEFAULT_UI_LANG) -> tuple[str, str]:
    series = session.get("series", [])
    series_label = " · ".join(display_series_name(item.get("name", "")) for item in series if item.get("name")) or (
        "Unknown Series" if ui_lang == "en" else "Неизвестная серия"
    )
    series_ids = sorted({
        item.get("id") or _slug(item.get("name", ""))
        for item in series
        if item.get("id") or item.get("name")
    })
    return ",".join(series_ids) or "series", series_label


def _location_signature(session: dict, ui_lang: str = DEFAULT_UI_LANG) -> tuple[str, str]:
    location = session.get("location", {}) or {}
    location_name = (
        location.get("alternateName")
        or location.get("name")
        or location.get("regionName")
        or ("Unknown Track" if ui_lang == "en" else "Неизвестная трасса")
    )
    location_slug = _slug(location.get("id") or location_name)
    return location_slug or "track", location_name


def build_event_identity(session: dict, ui_lang: str = DEFAULT_UI_LANG) -> EventIdentity:
    series_signature, series_label = _series_signature(session)
    location_slug, location_name = _location_signature(session, ui_lang)

    start_ts = int(session.get("start", 0) or 0)
    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else None
    day_code = start_dt.strftime("%Y-%m-%d") if start_dt else "unknown-date"
    raw_key = "|".join([series_signature, location_slug, day_code])
    key = sha1(raw_key.encode("utf-8")).hexdigest()[:16]

    if start_dt:
        date_label = start_dt.strftime("%d.%m.%Y")
        title = f"{series_label} · {location_name} · {date_label}"
    else:
        title = f"{series_label} · {location_name}"
    return EventIdentity(key=key, title=title[:180], sort_ts=start_ts)


def group_sessions_by_event(
    sessions: list[dict],
    ui_lang: str = DEFAULT_UI_LANG,
) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    by_signature: dict[tuple[str, str], list[dict]] = {}
    for session in sessions:
        series_signature, _ = _series_signature(session)
        location_signature, _ = _location_signature(session, ui_lang)
        by_signature.setdefault((series_signature, location_signature), []).append(session)

    for (series_signature, location_signature), items in by_signature.items():
        ordered = sorted(items, key=lambda item: int(item.get("start", 0) or 0))
        clusters: list[list[dict]] = []
        for session in ordered:
            start_ts = int(session.get("start", 0) or 0)
            if not clusters:
                clusters.append([session])
                continue
            prev = clusters[-1][-1]
            prev_ts = int(prev.get("start", 0) or 0)
            if start_ts and prev_ts and start_ts - prev_ts <= _CLUSTER_GAP_SECONDS:
                clusters[-1].append(session)
            else:
                clusters.append([session])

        for cluster in clusters:
            first = cluster[0]
            series_label = " · ".join(
                display_series_name(item.get("name", ""))
                for item in first.get("series", [])
                if item.get("name")
            ) or (
                "Unknown Series" if ui_lang == "en" else "Неизвестная серия"
            )
            _, location_name = _location_signature(first, ui_lang)
            starts = [int(item.get("start", 0) or 0) for item in cluster if item.get("start")]
            sort_ts = min(starts) if starts else 0
            day_code = datetime.fromtimestamp(sort_ts, tz=timezone.utc).strftime("%Y-%m-%d") if sort_ts else "unknown-date"
            raw_key = "|".join([series_signature, location_signature, day_code, str(len(cluster))])
            key = sha1(raw_key.encode("utf-8")).hexdigest()[:16]

            if sort_ts:
                date_label = datetime.fromtimestamp(sort_ts, tz=timezone.utc).strftime("%d.%m.%Y")
                title = f"{series_label} · {location_name} · {date_label}"
            else:
                title = f"{series_label} · {location_name}"
            grouped[key] = {
                "event_key": key,
                "title": title[:180],
                "sort_ts": sort_ts,
                "sessions": cluster,
            }

    for bucket in grouped.values():
        bucket["sessions"].sort(key=lambda item: int(item.get("start", 0) or 0))
    return grouped


def map_sessions_to_events(
    sessions: list[dict],
    ui_lang: str = DEFAULT_UI_LANG,
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for event in group_sessions_by_event(sessions, ui_lang).values():
        for session in event["sessions"]:
            session_id = session.get("id", "")
            if session_id:
                result[session_id] = event
    return result


def render_event_summary(
    event: dict,
    user_tz: str,
    ui_lang: str,
    fmt_time,
    session_category,
) -> str:
    title = escape(event.get("title", "Event"))
    sessions = event.get("sessions", [])
    lines = [f"🏁 <b>{title}</b>"]
    for session in sessions[:8]:
        start_ts = int(session.get("start", 0) or 0)
        time_label = fmt_time(start_ts, user_tz, ui_lang) if start_ts else "--:--"
        category = session_category(session.get("name", ""))
        category_label = {
            "race": "гонка" if ui_lang == "ru" else "race",
            "qualifying": "квал" if ui_lang == "ru" else "qualifying",
            "practice": "практика" if ui_lang == "ru" else "practice",
        }.get(category, "session")
        lines.append(f"• {time_label} · {escape(session.get('name', 'Session'))} · {category_label}")
    return "\n".join(lines)
