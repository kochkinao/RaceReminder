import logging

import utils
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)
_SESSION_CONTEXT_TTL_SECONDS = 300


async def load_session_context(
    db: Database,
    mem: MemoryCache,
    http_session=None,
    session_id: str = "",
) -> tuple[dict | None, list[dict], list[dict]]:
    if session_id == "":
        session_id = http_session
        http_session = None
    cache_key = f"session_context:{session_id}"
    if mem is not None and (cached := mem.get(cache_key)):
        return cached

    windows = [
        utils.history_window(),
        utils.today_window(),
        utils.week_window(),
        utils.notify_window(),
    ]

    sessions_by_id: dict[str, dict] = {}
    broadcasts_map: dict[str, list[dict]] = {}

    for start, end in windows:
        if http_session is None:
            sessions = await utils.get_sessions(mem, db, start, end)
            broadcasts = await utils.get_broadcasts(mem, db, start)
        else:
            sessions = await utils.get_sessions(mem, db, http_session, start, end)
            broadcasts = await utils.get_broadcasts(mem, db, http_session, start)

        for session in sessions:
            sid = session.get("id", "")
            if sid and sid not in sessions_by_id:
                sessions_by_id[sid] = session

        for sid, items in utils.broadcasts_by_session(broadcasts).items():
            broadcasts_map.setdefault(sid, []).extend(items)

    session = sessions_by_id.get(session_id)
    if not session:
        result = (None, [], [])
        if mem is not None:
            mem.set(cache_key, result, 60)
        return result

    seen_bc: set[str] = set()
    broadcasts: list[dict] = []
    for item in broadcasts_map.get(session_id, []):
        bid = item.get("id")
        if bid and bid in seen_bc:
            continue
        if bid:
            seen_bc.add(bid)
        broadcasts.append(item)

    try:
        if http_session is None:
            live_timings = await utils.get_live_timings(session_id)
        else:
            live_timings = await utils.get_live_timings(session_id, http_session)
    except Exception as exc:
        log.warning("Live timings fetch failed for %s: %s", session_id, exc)
        live_timings = []

    result = (session, broadcasts, live_timings)
    if mem is not None:
        mem.set(cache_key, result, _SESSION_CONTEXT_TTL_SECONDS)
    return result
