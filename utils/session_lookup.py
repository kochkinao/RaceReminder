import logging

import utils
from database import Database
from utils.cache import MemoryCache

log = logging.getLogger(__name__)


async def load_session_context(
    db: Database,
    mem: MemoryCache,
    session_id: str,
) -> tuple[dict | None, list[dict], list[dict]]:
    windows = [
        utils.history_window(),
        utils.today_window(),
        utils.week_window(),
        utils.notify_window(),
    ]

    sessions_by_id: dict[str, dict] = {}
    broadcasts_map: dict[str, list[dict]] = {}

    for start, end in windows:
        for session in await utils.get_sessions(mem, db, start, end):
            sid = session.get("id", "")
            if sid and sid not in sessions_by_id:
                sessions_by_id[sid] = session

        for sid, items in utils.broadcasts_by_session(
            await utils.get_broadcasts(mem, db, start)
        ).items():
            broadcasts_map.setdefault(sid, []).extend(items)

    session = sessions_by_id.get(session_id)
    if not session:
        return None, [], []

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
        live_timings = await utils.get_live_timings(session_id)
    except Exception as exc:
        log.warning("Live timings fetch failed for %s: %s", session_id, exc)
        live_timings = []

    return session, broadcasts, live_timings
