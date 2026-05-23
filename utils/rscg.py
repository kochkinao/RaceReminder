from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date

import aiohttp

from config import API_FALLBACK_STALE_SECONDS
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)

_RSCG_CALENDAR_URL = "https://rskg.smpracing.ru/calendar"
_RSCG_BASE_URL = "https://rskg.smpracing.ru"
_L1_TTL_SECONDS = 6 * 3_600
_L2_TTL_SECONDS = 24 * 3_600
_L1_KEY = "rscg_stages"

_MONTHS_RU: dict[str, int] = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


@dataclass(slots=True)
class RscgStage:
    id: int
    round: int
    date_start: date
    date_end: date
    track: str
    location: str
    description: str
    sprint: str | None
    endurance: str | None
    additional: str | None
    note: str | None
    image_url: str | None
    ticket_url: str | None
    info_url: str | None


def parse_dates(dates_str: str, year: int) -> tuple[date, date]:
    cleaned = " ".join((dates_str or "").replace("–", "-").replace("—", "-").split())
    if not cleaned:
        raise ValueError("empty RSCG date string")

    try:
        days_part, month_name = cleaned.rsplit(" ", 1)
    except ValueError as exc:
        raise ValueError(f"unsupported RSCG date format: {dates_str}") from exc

    month = _MONTHS_RU.get(month_name.lower())
    if month is None:
        raise ValueError(f"unknown RSCG month: {month_name}")

    if "-" in days_part:
        start_raw, end_raw = days_part.split("-", 1)
    else:
        start_raw = end_raw = days_part

    start_day = int(start_raw.strip())
    end_day = int(end_raw.strip())
    return date(year, month, start_day), date(year, month, end_day)


def _extract_stages_payload(html: str) -> list[dict]:
    marker = '\\"stages\\":[{'
    start = html.find(marker)
    if start < 0:
        raise ValueError("RSCG stages marker not found")

    array_start = html.find("[", start)
    if array_start < 0:
        raise ValueError("RSCG stages array start not found")

    depth = 0
    in_string = False
    escaped = False
    for idx in range(array_start, len(html)):
        char = html[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "[":
            depth += 1
            continue
        if char == "]":
            depth -= 1
            if depth == 0:
                raw = html[array_start:idx + 1]
                decoded = (
                    raw.replace('\\"', '"')
                    .replace("\\/", "/")
                    .replace("\\n", "\n")
                    .replace("\\t", "\t")
                )
                payload, _ = json.JSONDecoder().raw_decode(decoded)
                return payload

    raise ValueError("RSCG stages array end not found")


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_url(value: object) -> str | None:
    text = _clean_optional(value)
    if not text:
        return None
    if text.startswith("/"):
        return f"{_RSCG_BASE_URL}{text}"
    return text


def _stage_from_payload(payload: dict, year: int) -> RscgStage:
    date_start, date_end = parse_dates(str(payload.get("dates", "")), year)
    return RscgStage(
        id=int(payload.get("id", 0)),
        round=int(payload.get("round", 0)),
        date_start=date_start,
        date_end=date_end,
        track=str(payload.get("track", "")).strip(),
        location=str(payload.get("location", "")).strip(),
        description=str(payload.get("description", "")).strip(),
        sprint=_clean_optional(payload.get("sprint")),
        endurance=_clean_optional(payload.get("endurance")),
        additional=_clean_optional(payload.get("additional")),
        note=_clean_optional(payload.get("note")),
        image_url=_normalize_url(payload.get("image")),
        ticket_url=_normalize_url(payload.get("ticketUrl")),
        info_url=_normalize_url(payload.get("infoUrl")),
    )


def _cache_key(year: int) -> str:
    return f"rscg_calendar_{year}"


def _serialize_stages(stages: list[RscgStage]) -> str:
    payload = []
    for stage in stages:
        item = asdict(stage)
        item["date_start"] = stage.date_start.isoformat()
        item["date_end"] = stage.date_end.isoformat()
        payload.append(item)
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_stages(raw: str) -> list[RscgStage]:
    payload = json.loads(raw)
    return [
        RscgStage(
            id=int(item["id"]),
            round=int(item["round"]),
            date_start=date.fromisoformat(item["date_start"]),
            date_end=date.fromisoformat(item["date_end"]),
            track=str(item.get("track", "")),
            location=str(item.get("location", "")),
            description=str(item.get("description", "")),
            sprint=_clean_optional(item.get("sprint")),
            endurance=_clean_optional(item.get("endurance")),
            additional=_clean_optional(item.get("additional")),
            note=_clean_optional(item.get("note")),
            image_url=_clean_optional(item.get("image_url")),
            ticket_url=_clean_optional(item.get("ticket_url")),
            info_url=_clean_optional(item.get("info_url")),
        )
        for item in payload
    ]


async def fetch_rscg_stages(session: aiohttp.ClientSession) -> list[RscgStage]:
    year = date.today().year
    try:
        async with session.get(
            _RSCG_CALENDAR_URL,
            headers={"User-Agent": "RaceDayBot/1.0"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            response.raise_for_status()
            html = await response.text()
        payload = _extract_stages_payload(html)
        stages = [_stage_from_payload(item, year) for item in payload]
        return sorted(stages, key=lambda stage: (stage.date_start, stage.round, stage.id))
    except Exception:
        log.exception("Failed to fetch or parse RSCG calendar")
        return []


async def get_rscg_stages(
    mem: MemoryCache,
    db: Database,
    http_session: aiohttp.ClientSession,
) -> list[RscgStage]:
    year = date.today().year
    l2_key = _cache_key(year)

    cached = mem.get(_L1_KEY)
    if cached is not None:
        return cached

    cached_l2 = await db.get_cache(l2_key, _L2_TTL_SECONDS)
    if cached_l2:
        try:
            stages = _deserialize_stages(cached_l2)
            mem.set(_L1_KEY, stages, _L1_TTL_SECONDS)
            return stages
        except Exception:
            log.exception("Failed to deserialize cached RSCG stages")

    stages = await fetch_rscg_stages(http_session)

    if stages:
        raw = _serialize_stages(stages)
        await db.set_cache(l2_key, raw)
        mem.set(_L1_KEY, stages, _L1_TTL_SECONDS)
        return stages

    stale = await db.get_cache_stale(l2_key, API_FALLBACK_STALE_SECONDS)
    if stale:
        try:
            stages = _deserialize_stages(stale)
            mem.set(_L1_KEY, stages, _L1_TTL_SECONDS)
            log.warning("Using stale cached RSCG calendar for %s", year)
            return stages
        except Exception:
            log.exception("Failed to deserialize stale RSCG cache")

    return []
