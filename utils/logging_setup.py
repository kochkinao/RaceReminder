"""
Logging setup.

Two handlers:
  - StreamHandler (stdout) — all levels per LOG_LEVEL
  - AdminAlertHandler       — ERROR+ goes to admin Telegram chat

AdminAlertHandler is lazy: it holds a queue and flushes
via bot.send_message. The bot instance is injected after startup
via AdminAlertHandler.set_bot().
"""
import asyncio
import logging
import traceback
from collections import deque
from datetime import datetime, timezone

_admin_handler: "AdminAlertHandler | None" = None


class AdminAlertHandler(logging.Handler):
    """Buffers ERROR+ log records and sends them to admin Telegram chats."""

    def __init__(self, admin_ids: set[int], max_queue: int = 50) -> None:
        super().__init__(level=logging.ERROR)
        self._admin_ids = admin_ids
        self._queue: deque[str] = deque(maxlen=max_queue)
        self._bot = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_bot(self, bot, loop: asyncio.AbstractEventLoop) -> None:
        self._bot  = bot
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts  = datetime.now(timezone.utc).strftime("%H:%M:%S")
            lvl = record.levelname
            msg = self.format(record)

            # Trim long tracebacks
            if len(msg) > 800:
                msg = msg[:800] + "…"

            text = f"🚨 <b>[{lvl}]</b> <code>{ts} UTC</code>\n<pre>{msg}</pre>"
            self._queue.append(text)

            if self._bot and self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._flush_queue(), self._loop
                )
        except Exception:
            pass  # never let logging crash the app

    async def _flush_queue(self) -> None:
        if not self._bot:
            return
        while self._queue:
            text = self._queue.popleft()
            for admin_id in self._admin_ids:
                try:
                    await self._bot.send_message(
                        admin_id, text,
                        parse_mode="HTML",
                        disable_notification=True,
                    )
                except Exception:
                    pass


def setup_logging(log_level: str, admin_ids: set[int]) -> "AdminAlertHandler":
    """Configure root logger. Returns AdminAlertHandler for later bot injection."""
    global _admin_handler

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove default handlers
    root.handlers.clear()

    # Console
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # Admin alerts
    _admin_handler = AdminAlertHandler(admin_ids)
    _admin_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root.addHandler(_admin_handler)

    return _admin_handler


def get_admin_handler() -> "AdminAlertHandler | None":
    return _admin_handler
