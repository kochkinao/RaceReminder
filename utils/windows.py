"""
Fixed UTC-aligned time windows.

All cache keys are derived from these — every user in any timezone
hits the same key and the same API request.

  today   →  UTC midnight … UTC midnight+1d
  week    →  UTC Monday 00:00 … UTC Sunday 24:00
  notify  →  now (rounded down to hour) … +4 days
"""
from datetime import datetime, timedelta, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def today_window() -> tuple[int, int]:
    """Current UTC day: 00:00 – 24:00."""
    now   = _utc_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def week_window() -> tuple[int, int]:
    """Current UTC week: Monday 00:00 – Sunday 24:00."""
    now        = _utc_now()
    monday     = now - timedelta(days=now.weekday())
    week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end   = week_start + timedelta(days=7)
    return int(week_start.timestamp()), int(week_end.timestamp())


def notify_window() -> tuple[int, int]:
    """
    Sliding 4-day window for notification checks.
    Start is rounded down to the current UTC hour so the cache key
    stays stable for the full hour — one API call covers all users.
    """
    now        = _utc_now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    window_end = hour_start + timedelta(days=4)
    return int(hour_start.timestamp()), int(window_end.timestamp())


def history_window() -> tuple[int, int]:
    """Last 7 UTC days."""
    now   = _utc_now()
    end   = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start = end - timedelta(days=7)
    return int(start.timestamp()), int(end.timestamp())


def cache_key_sessions(start: int, end: int) -> str:
    return f"sessions:{start}:{end}"


def cache_key_broadcasts(start: int) -> str:
    return f"broadcasts:{start}"


def week_label(start_ts: int, end_ts: int) -> str:
    s = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    e = datetime.fromtimestamp(end_ts,   tz=timezone.utc) - timedelta(seconds=1)
    return f"{s.strftime('%d %b')} – {e.strftime('%d %b %Y')}"
