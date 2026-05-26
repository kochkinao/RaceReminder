import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

from utils.cache import MemoryCache
from database import Database
from utils.metrics import Metrics
from utils.api import fallback_stats


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@dataclass
class JobHealth:
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error: str = ""
    last_duration_ms: int = 0

    def success(self, duration_ms: int = 0) -> None:
        self.last_success_at = time.time()
        self.last_duration_ms = duration_ms
        self.last_error = ""

    def failure(self, error: str, duration_ms: int = 0) -> None:
        self.last_failure_at = time.time()
        self.last_duration_ms = duration_ms
        self.last_error = error[:200]

    def as_dict(self) -> dict[str, Any]:
        return {
            "last_success_at": _iso(self.last_success_at),
            "last_failure_at": _iso(self.last_failure_at),
            "last_error": self.last_error,
            "last_duration_ms": self.last_duration_ms,
        }


@dataclass
class RuntimeState:
    started_at: float = field(default_factory=time.time)
    db_connected: bool = False
    scheduler_started: bool = False
    bot_started: bool = False
    last_warmup_ok: bool = False
    http_session: aiohttp.ClientSession | None = None
    scheduler_jobs: dict[str, str] = field(default_factory=dict)
    jobs: dict[str, JobHealth] = field(default_factory=lambda: {
        "cache_warmup": JobHealth(),
        "notifications": JobHealth(),
        "weekly_digest": JobHealth(),
        "retry_delivery": JobHealth(),
        "session_reminders": JobHealth(),
        "db_cleanup": JobHealth(),
        "rscg_notifications": JobHealth(),
        "admin_backup": JobHealth(),
    })

    def mark_db_connected(self) -> None:
        self.db_connected = True

    def mark_scheduler_started(self) -> None:
        self.scheduler_started = True

    def mark_bot_started(self) -> None:
        self.bot_started = True

    def mark_job_success(self, job_name: str, duration_ms: int = 0) -> None:
        self.jobs.setdefault(job_name, JobHealth()).success(duration_ms)
        if job_name == "cache_warmup":
            self.last_warmup_ok = True

    def mark_job_failure(self, job_name: str, error: str, duration_ms: int = 0) -> None:
        self.jobs.setdefault(job_name, JobHealth()).failure(error, duration_ms)
        if job_name == "cache_warmup":
            self.last_warmup_ok = False

    def is_ready(self) -> bool:
        return self.db_connected and self.scheduler_started and self.bot_started and self.last_warmup_ok

    async def snapshot(self, db: Database, mem: MemoryCache, metrics: Metrics) -> dict[str, Any]:
        return {
            "status": "ready" if self.is_ready() else "starting",
            "started_at": _iso(self.started_at),
            "uptime_seconds": int(time.time() - self.started_at),
            "db_connected": self.db_connected,
            "scheduler_started": self.scheduler_started,
            "bot_started": self.bot_started,
            "last_warmup_ok": self.last_warmup_ok,
            "retry_queue_size": await db.count_pending_deliveries(),
            "api_fallback": fallback_stats(),
            "cache_l1_size": mem.size(),
            "metrics": metrics.summary(),
            "jobs": {name: job.as_dict() for name, job in self.jobs.items()},
        }
