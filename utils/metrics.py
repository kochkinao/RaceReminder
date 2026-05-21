"""
In-memory metrics counters.
Lightweight — no external dependencies, no persistence.
Reset on restart (that's fine for a simple admin view).
"""
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class _Counter:
    total: int = 0
    last_hour: deque = field(default_factory=lambda: deque(maxlen=3600))

    def inc(self, n: int = 1) -> None:
        self.total += n
        now = int(time.time())
        self.last_hour.extend([now] * n)

    def per_hour(self) -> int:
        cutoff = int(time.time()) - 3600
        return sum(1 for t in self.last_hour if t > cutoff)


class Metrics:
    """
    Single shared instance, injected via middleware as data['metrics'].
    """

    def __init__(self) -> None:
        self._started_at  = time.time()

        # API
        self.api_requests     = _Counter()
        self.api_errors       = _Counter()
        self.cache_l1_hits    = _Counter()
        self.cache_l2_hits    = _Counter()
        self.cache_misses     = _Counter()

        # Notifications
        self.notifications_sent   = _Counter()
        self.notifications_failed = _Counter()
        self.digests_sent         = _Counter()

        # Users
        self.messages_received = _Counter()
        self.new_users         = _Counter()
        self.blocked_users     = _Counter()   # TelegramForbiddenError

        # Per-command counters
        self.commands: dict[str, int] = defaultdict(int)

        # Recent errors (last 20)
        self.recent_errors: deque[dict[str, Any]] = deque(maxlen=20)

    def record_error(self, source: str, error: str) -> None:
        self.recent_errors.appendleft({
            "ts":     datetime.now(timezone.utc).isoformat(),
            "source": source,
            "error":  str(error)[:200],
        })

    def uptime_seconds(self) -> int:
        return int(time.time() - self._started_at)

    def uptime_str(self) -> str:
        s = self.uptime_seconds()
        d, s = divmod(s, 86400)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        parts = []
        if d: parts.append(f"{d}д")
        if h: parts.append(f"{h}ч")
        if m: parts.append(f"{m}м")
        parts.append(f"{s}с")
        return " ".join(parts)

    def summary(self) -> dict[str, Any]:
        return {
            "uptime":               self.uptime_str(),
            "messages_received":    self.messages_received.total,
            "messages_per_hour":    self.messages_received.per_hour(),
            "new_users":            self.new_users.total,
            "api_requests":         self.api_requests.total,
            "api_errors":           self.api_errors.total,
            "cache_l1_hits":        self.cache_l1_hits.total,
            "cache_l2_hits":        self.cache_l2_hits.total,
            "cache_misses":         self.cache_misses.total,
            "notifications_sent":   self.notifications_sent.total,
            "notifications_failed": self.notifications_failed.total,
            "digests_sent":         self.digests_sent.total,
            "blocked_users":        self.blocked_users.total,
            "top_commands":         sorted(
                self.commands.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }
