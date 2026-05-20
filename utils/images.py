"""
Banner generation with Pillow.

Optimizations vs naive approach:
  - Fonts loaded once at module import (not per call)
  - Session banners cached to disk by content hash
  - Digest banners cached in memory (keyed by label string)
  - Gradient drawing vectorized per-column (unchanged, fast enough)
  - Cache directory created at import time
"""
import hashlib
import io
import logging
import textwrap
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False
    log.warning("Pillow not installed — banners disabled")

_W, _H         = 1200, 400
_BANNER_DIR    = Path("data/banners")
_BANNER_DIR.mkdir(parents=True, exist_ok=True)

# ── Palette by vehicle class ──────────────────────────────────────────────────

_PALETTES: dict[str, tuple[tuple[int,int,int], tuple[int,int,int]]] = {
    "Single-Seaters": ((15, 10, 50),  (180, 0,   60)),
    "GT3":            ((10, 40, 10),  (0,   160, 60)),
    "Endurance":      ((40, 20,  5),  (200, 100,  0)),
    "Rally":          (( 5, 30, 50),  (0,   80,  180)),
    "Motorcycles":    ((50,  5,  5),  (220, 50,   0)),
    "Electric":       (( 5,  5, 50),  (0,   200, 255)),
    "Oval Racing":    ((50, 40,  5),  (220, 180,  0)),
    "TCR":            ((30, 10, 40),  (150, 0,   200)),
    "Touring Cars":   ((10, 20, 40),  (0,   60,  180)),
    "Stock Cars":     ((40, 15,  5),  (200, 80,   0)),
    "Prototypes":     ((5,  40, 40),  (0,   180, 180)),
}
_DEFAULT_PALETTE = ((20, 20, 30), (80, 0, 120))


def _palette(session: dict[str, Any]):
    for sr in session.get("series", []):
        for vc in sr.get("vehicleClasses", []):
            if p := _PALETTES.get(vc.get("name", "")):
                return p
    return _DEFAULT_PALETTE


# ── Font cache — loaded once at import ───────────────────────────────────────

_FONT_CACHE: dict[tuple[int, bool], Any] = {}

def _font(size: int, bold: bool = False) -> Any:
    key = (size, bold)
    if key not in _FONT_CACHE:
        if PIL_OK:
            name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            try:
                _FONT_CACHE[key] = ImageFont.truetype(
                    f"/usr/share/fonts/truetype/dejavu/{name}", size
                )
            except Exception:
                _FONT_CACHE[key] = ImageFont.load_default()
        else:
            _FONT_CACHE[key] = None
    return _FONT_CACHE[key]


# Pre-load common sizes at import time
def _preload_fonts() -> None:
    if not PIL_OK:
        return
    for size in (28, 32, 60, 64):
        for bold in (False, True):
            _font(size, bold)

_preload_fonts()


# ── Gradient helper ───────────────────────────────────────────────────────────

def _gradient(img: "Image.Image", c1: tuple, c2: tuple) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for x in range(w):
        r = int(c1[0] + (c2[0] - c1[0]) * x / w)
        g = int(c1[1] + (c2[1] - c1[1]) * x / w)
        b = int(c1[2] + (c2[2] - c1[2]) * x / w)
        draw.line([(x, 0), (x, h)], fill=(r, g, b))


# ── Content hash for cache key ────────────────────────────────────────────────

def _session_hash(session: dict[str, Any], time_str: str, location_str: str) -> str:
    parts = [
        session.get("id", ""),
        session.get("name", ""),
        time_str,
        location_str,
        str(sorted(
            vc.get("name", "")
            for sr in session.get("series", [])
            for vc in sr.get("vehicleClasses", [])
        )),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ── In-memory digest banner cache ─────────────────────────────────────────────

_digest_cache: dict[str, bytes] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def session_banner(
    session:      dict[str, Any],
    time_str:     str = "",
    location_str: str = "",
) -> bytes | None:
    if not PIL_OK:
        return None

    # Check disk cache first
    h         = _session_hash(session, time_str, location_str)
    cache_path = _BANNER_DIR / f"{h}.jpg"

    if cache_path.exists():
        log.debug("Banner cache hit: %s", h)
        return cache_path.read_bytes()

    # Generate
    log.debug("Generating banner: %s", session.get("name", ""))
    c1, c2 = _palette(session)
    img    = Image.new("RGB", (_W, _H), c1)
    _gradient(img, c1, c2)
    draw   = ImageDraw.Draw(img)

    # Accent stripes
    draw.rectangle([(0, 0),       (_W, 10)], fill=(255, 255, 255, 50))
    draw.rectangle([(0, _H - 10), (_W, _H)], fill=(255, 255, 255, 50))

    # Checkered flag corner
    tile, ox, oy = 20, _W - 160, 0
    for row in range(8):
        for col in range(8):
            if (row + col) % 2 == 0:
                x0, y0 = ox + col * tile, oy + row * tile
                draw.rectangle([x0, y0, x0 + tile, y0 + tile], fill=(255, 255, 255, 70))

    series_names = " · ".join(s.get("name", "") for s in session.get("series", []))[:80]
    draw.text((50, 40),  series_names,
              font=_font(28), fill=(200, 200, 200))
    draw.text((50, 100), textwrap.fill(session.get("name", ""), 30),
              font=_font(64, True), fill=(255, 255, 255))

    if time_str:
        draw.text((50, _H - 90), f"🕐 {time_str}",
                  font=_font(32), fill=(220, 220, 220))
    if location_str:
        draw.text((50, _H - 50), f"📍 {location_str}",
                  font=_font(28), fill=(180, 180, 180))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    data = buf.getvalue()

    # Save to disk cache
    cache_path.write_bytes(data)
    log.debug("Banner saved: %s (%d bytes)", h, len(data))
    return data


def digest_banner(label: str = "") -> bytes | None:
    if not PIL_OK:
        return None

    if label in _digest_cache:
        return _digest_cache[label]

    img  = Image.new("RGB", (_W, 220), (10, 10, 20))
    _gradient(img, (10, 10, 20), (60, 10, 100))
    draw = ImageDraw.Draw(img)

    draw.text((50, 30),  "🏁 Гонки недели", font=_font(60, True), fill=(255, 255, 255))
    if label:
        draw.text((50, 130), label, font=_font(32), fill=(180, 180, 180))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    data = buf.getvalue()

    _digest_cache[label] = data
    return data


def prewarm_banners(sessions: list[dict[str, Any]], user_tz: str = "UTC") -> int:
    """
    Pre-generate banners for a list of sessions.
    Called from warm_up() after sessions are fetched.
    Returns count of newly generated banners.
    """
    if not PIL_OK:
        return 0

    from utils.formatters import fmt_time

    generated = 0
    for s in sessions:
        start_ts  = s.get("start", 0)
        loc       = s.get("location", {})
        loc_name  = loc.get("alternateName") or loc.get("name", "")
        country   = loc.get("country", "")
        loc_str   = ", ".join(p for p in (loc_name, country) if p)
        time_str  = fmt_time(start_ts, user_tz) if start_ts else ""

        h          = _session_hash(s, time_str, loc_str)
        cache_path = _BANNER_DIR / f"{h}.jpg"

        if not cache_path.exists():
            session_banner(s, time_str=time_str, location_str=loc_str)
            generated += 1

    return generated


def clear_old_banners(keep_days: int = 7) -> int:
    """Remove cached banners older than keep_days. Call weekly."""
    import time
    cutoff  = time.time() - keep_days * 86_400
    removed = 0
    for p in _BANNER_DIR.glob("*.jpg"):
        if p.stat().st_mtime < cutoff:
            p.unlink()
            removed += 1
    if removed:
        log.info("Cleared %d old banners", removed)
    return removed
