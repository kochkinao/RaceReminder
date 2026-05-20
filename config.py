import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Core ──────────────────────────────────────────────────────────────────────
BOT_TOKEN: str       = os.getenv("BOT_TOKEN", "")
DATABASE_PATH: str   = os.getenv("DATABASE_PATH", "data/raceday.db")
API_BASE_URL: str    = os.getenv("API_BASE_URL", "https://api.raceday.watch")
LOG_LEVEL: str       = os.getenv("LOG_LEVEL", "INFO")

# ── Channel gate (optional) ───────────────────────────────────────────────────
CHANNEL_ID: str | None   = os.getenv("CHANNEL_ID") or None
CHANNEL_LINK: str | None = os.getenv("CHANNEL_LINK") or None

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SERIES_NAMES: list[str] = [
    "Formula 1",
    "FIA World Endurance Championship",
    "IMSA SportsCar Championship",
    "FIA World Rally Championship",
    "NASCAR Cup Series",
    "IndyCar Series",
    "Formula E",
    "DTM",
    "Supercars Championship",
    "MotoGP",
]

DEFAULT_VEHICLE_CLASS_NAMES: list[str] = [
    "GT3",
    "Single-Seaters",
    "Endurance",
    "Rally",
    "Motorcycles",
]

# ── Notifications ─────────────────────────────────────────────────────────────
NOTIFICATION_OFFSETS: dict[str, int] = {
    "3days": 3 * 86_400,
    "1day":  86_400,
    "1hour": 3_600,
    "start": 0,
}
NOTIFICATION_WINDOW: int = 1_800   # ±30 min tolerance

DEFAULT_QUIET_START: int  = 23
DEFAULT_QUIET_END: int    = 7
DEFAULT_DIGEST_TIME: str  = "08:00"
DEFAULT_TIMEZONE: str     = "Europe/Moscow"
DEFAULT_LANG: str         = "English"

THROTTLE_RATE: float = 1.0   # seconds between messages

# ── UI ────────────────────────────────────────────────────────────────────────
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

# ── Ensure DB directory exists ────────────────────────────────────────────────
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
