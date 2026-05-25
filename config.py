import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Core ──────────────────────────────────────────────────────────────────────
BOT_TOKEN: str     = os.getenv("BOT_TOKEN", "")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/raceday.db")
API_BASE_URL: str  = os.getenv("API_BASE_URL", "https://api.raceday.watch")
LOG_LEVEL: str     = os.getenv("LOG_LEVEL", "INFO")
API_FALLBACK_STALE_SECONDS: int = int(os.getenv("API_FALLBACK_STALE_SECONDS", str(7 * 24 * 3600)))

# ── Admin ─────────────────────────────────────────────────────────────────────
ADMIN_IDS: set[int] = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

# ── Channel gate (optional) ───────────────────────────────────────────────────
CHANNEL_ID: str | None   = os.getenv("CHANNEL_ID") or None
CHANNEL_LINK: str | None = os.getenv("CHANNEL_LINK") or None

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SERIES_NAMES: list[str] = [
    "Formula 1",
    "FIA World Endurance Championship",
    "IMSA",
    "FIA World Rally Championship",
    "NASCAR Cup Series",
    "IndyCar Series",
    "Formula E",
    "DTM",
    "Supercars Championship",
    "MotoGP",
]

DEFAULT_ONBOARDING_SERIES_NAMES: list[str] = [
    "Formula 1",
    "FIA World Endurance Championship",
    "IMSA",
]

DEFAULT_VEHICLE_CLASS_NAMES: list[str] = [
    "GT3",
    "Single-Seaters",
    "Endurance",
    "Rally",
    "Motorcycles",
]

# ── Search aliases — short names map to full series names ─────────────────────
SEARCH_ALIASES: dict[str, str] = {
    "f1":       "Formula 1",
    "formula1": "Formula 1",
    "wec":      "FIA World Endurance Championship",
    "imsa":     "IMSA",
    "wrc":      "FIA World Rally Championship",
    "nascar":   "NASCAR Cup Series",
    "indycar":  "IndyCar Series",
    "fe":       "Formula E",
    "motogp":   "MotoGP",
    "gtwce":    "GT World Challenge Europe",
    "f2":       "Formula 2",
    "f3":       "Formula 3",
    "dtm":      "DTM",
}

# ── Notifications ─────────────────────────────────────────────────────────────
NOTIFICATION_OFFSETS: dict[str, int] = {
    "3days": 3 * 86_400,
    "1day":  86_400,
    "1hour": 3_600,
    "start": 0,
}
NOTIFICATION_WINDOW: int   = 1_800
TELEGRAM_SEND_DELAY: float = 0.05   # 50 ms between sends → max 20 msg/sec (limit 30)

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_MISFIRE_GRACE: int = 600  # 10 min — job still runs if delayed

# ── User safety ───────────────────────────────────────────────────────────────
SENT_NOTIFICATIONS_TTL_DAYS: int = 30
THROTTLE_RATE: float             = 1.0

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_QUIET_START: int  = 23
DEFAULT_QUIET_END: int    = 7
DEFAULT_DIGEST_TIME: str  = "08:00"
DEFAULT_TIMEZONE: str     = "Europe/Moscow"
DEFAULT_LANG: str         = "English"

POPULAR_TIMEZONES: list[str] = [
    "Europe/Moscow", "Europe/London",  "Europe/Berlin",
    "Europe/Paris",  "America/New_York", "America/Los_Angeles",
    "America/Chicago", "Asia/Tokyo",   "Asia/Shanghai",
    "Australia/Sydney", "Pacific/Auckland", "America/Sao_Paulo",
    "Asia/Dubai",    "Asia/Kolkata",
]

BROADCAST_TYPES: dict[int, str] = {
    1: "📺 TV",
    2: "📻 Radio",
    3: "🌐 Stream",
    4: "📡 Pay-TV",
    5: "▶️ Online",
    6: "🎙 Podcast",
}

# ── Allowed DB fields for update_user (whitelist against injection) ───────────
ALLOWED_USER_FIELDS: frozenset[str] = frozenset({
    "username", "timezone", "preferred_langs", "ui_lang",
    "digest_enabled", "digest_time",
    "quiet_enabled", "quiet_start", "quiet_end",
    "show_no_broadcast", "show_qualifying", "show_practice",
    "notify_3days", "notify_1day", "notify_1hour", "notify_start",
})

# ── Ensure DB directory exists ─────────────────────────────────────────────────
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
