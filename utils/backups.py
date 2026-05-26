import asyncio
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
import zipfile

from aiogram import Bot
from aiogram.types import FSInputFile

from config import DATABASE_PATH, TELEGRAM_DOCUMENT_MAX_BYTES, TELEGRAM_SEND_DELAY
from database import Database

log = logging.getLogger(__name__)
_UPLOAD_HEADROOM_BYTES = 512 * 1024
_MIN_PART_SIZE_BYTES = 512 * 1024


def _human_size(size_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB")
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            precision = 0 if unit == "B" else 1
            return f"{size:.{precision}f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def split_file(path: Path, part_size_bytes: int) -> list[Path]:
    if part_size_bytes <= 0:
        raise ValueError("part_size_bytes must be positive")

    if path.stat().st_size <= part_size_bytes:
        return [path]

    part_count = math.ceil(path.stat().st_size / part_size_bytes)
    width = max(3, len(str(part_count)))
    parts: list[Path] = []
    with path.open("rb") as source:
        for index in range(1, part_count + 1):
            part_path = path.with_name(f"{path.name}.part{index:0{width}d}")
            chunk = source.read(part_size_bytes)
            with part_path.open("wb") as target:
                target.write(chunk)
            parts.append(part_path)
    return parts


def _split_target_size(limit_bytes: int) -> int:
    if limit_bytes <= _UPLOAD_HEADROOM_BYTES:
        return max(1, limit_bytes)
    return min(limit_bytes, max(_MIN_PART_SIZE_BYTES, limit_bytes - _UPLOAD_HEADROOM_BYTES))


def _is_entity_too_large(exc: Exception) -> bool:
    return "request entity too large" in str(exc).lower()


async def _send_document_with_resizing(
    bot: Bot,
    admin_id: int,
    file_path: Path,
    caption: str,
) -> list[Path]:
    queue = [file_path]
    sent_parts: list[Path] = []

    while queue:
        current = queue.pop(0)
        document = FSInputFile(str(current), filename=current.name)
        try:
            await bot.send_document(admin_id, document=document, caption=caption)
            sent_parts.append(current)
            continue
        except Exception as exc:
            if not _is_entity_too_large(exc):
                raise
            current_size = current.stat().st_size
            if current_size <= _MIN_PART_SIZE_BYTES:
                raise
            next_size = max(_MIN_PART_SIZE_BYTES, current_size // 2)
            replacement_parts = split_file(current, next_size)
            if replacement_parts == [current]:
                raise
            if current != file_path and current.exists():
                current.unlink()
            queue = replacement_parts + queue

    return sent_parts


async def send_db_backup(
    bot: Bot,
    admin_ids: set[int],
    db: Database,
    *,
    caption_prefix: str,
) -> int:
    backup_dir = Path(DATABASE_PATH).parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"raceday-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.db"
    archive_path = backup_path.with_suffix(".zip")
    generated_files: list[Path] = []

    try:
        await db.export_backup(str(backup_path))
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(backup_path, arcname=backup_path.name)

        generated_files = split_file(archive_path, _split_target_size(TELEGRAM_DOCUMENT_MAX_BYTES))
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        archive_size = archive_path.stat().st_size
        is_multipart = len(generated_files) > 1

        for admin_index, admin_id in enumerate(admin_ids):
            if is_multipart:
                await bot.send_message(
                    admin_id,
                    (
                        "Backup archive is too large for a single Telegram upload.\n"
                        f"Archive size: {_human_size(archive_size)}.\n"
                        f"Sending {len(generated_files)} parts up to {_human_size(TELEGRAM_DOCUMENT_MAX_BYTES)} each.\n"
                        f"Reassemble with <code>copy /b {archive_path.name}.part001+... {archive_path.name}</code>."
                    ),
                    parse_mode="HTML",
                )
                await asyncio.sleep(TELEGRAM_SEND_DELAY)

            actual_files: list[Path] = []
            for index, file_path in enumerate(generated_files, start=1):
                suffix = f" part {index}/{len(generated_files)}" if is_multipart else ""
                caption = f"{caption_prefix}{suffix} · {timestamp}"
                actual_files.extend(await _send_document_with_resizing(bot, admin_id, file_path, caption))
                await asyncio.sleep(TELEGRAM_SEND_DELAY)
            if admin_index == 0 and actual_files:
                generated_files = actual_files
                is_multipart = len(generated_files) > 1

        return len(generated_files)
    finally:
        for path in (backup_path, archive_path, *generated_files):
            try:
                if path.exists():
                    path.unlink()
            except Exception as cleanup_exc:
                log.warning("Backup cleanup failed for %s: %s", path, cleanup_exc)
