from __future__ import annotations

import pytz


_TIMEZONE_ALIASES = {
    "samara": "Europe/Samara",
    "moscow": "Europe/Moscow",
    "saint petersburg": "Europe/Moscow",
    "st petersburg": "Europe/Moscow",
    "new york": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "london": "Europe/London",
    "berlin": "Europe/Berlin",
    "paris": "Europe/Paris",
    "tokyo": "Asia/Tokyo",
    "dubai": "Asia/Dubai",
    "kolkata": "Asia/Kolkata",
}


def resolve_timezone_input(value: str) -> list[str]:
    raw = " ".join((value or "").strip().split())
    if not raw:
        return []

    lowered = raw.lower()
    direct = _TIMEZONE_ALIASES.get(lowered)
    if direct:
        return [direct]

    if raw in pytz.all_timezones_set:
        return [raw]

    normalized = lowered.replace("\\", "/")
    candidates = [
        tz for tz in pytz.all_timezones
        if tz.lower() == normalized
        or tz.lower().endswith(f"/{normalized}")
        or tz.lower().replace("_", " ") == lowered
        or tz.lower().endswith(f"/{lowered.replace(' ', '_')}")
    ]
    seen: set[str] = set()
    result: list[str] = []
    for tz in candidates:
        if tz not in seen:
            seen.add(tz)
            result.append(tz)
    return result[:6]
