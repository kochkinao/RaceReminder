from pathlib import Path

import pytest

from utils import backups


def test_split_file_returns_original_when_under_limit(tmp_path: Path) -> None:
    path = tmp_path / "backup.zip"
    path.write_bytes(b"x" * 16)

    parts = backups.split_file(path, 32)

    assert parts == [path]


def test_split_file_creates_numbered_parts(tmp_path: Path) -> None:
    path = tmp_path / "backup.zip"
    payload = bytes(range(256)) * 2
    path.write_bytes(payload)

    parts = backups.split_file(path, 200)

    assert [part.name for part in parts] == [
        "backup.zip.part001",
        "backup.zip.part002",
        "backup.zip.part003",
    ]
    assert b"".join(part.read_bytes() for part in parts) == payload


@pytest.mark.asyncio
async def test_send_db_backup_sends_multipart_archive(monkeypatch, tmp_path: Path) -> None:
    class FakeDb:
        async def export_backup(self, target_path: str) -> None:
            Path(target_path).write_bytes(bytes(range(256)) * 4)

    class FakeBot:
        def __init__(self) -> None:
            self.messages: list[str] = []
            self.documents: list[tuple[int, str, str]] = []

        async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None) -> None:
            self.messages.append(text)

        async def send_document(self, chat_id: int, document, caption: str) -> None:
            self.documents.append((chat_id, document.filename, caption))

    monkeypatch.setattr(backups, "DATABASE_PATH", str(tmp_path / "raceday.db"))
    monkeypatch.setattr(backups, "TELEGRAM_DOCUMENT_MAX_BYTES", 180)
    monkeypatch.setattr(backups, "TELEGRAM_SEND_DELAY", 0)

    bot = FakeBot()
    parts_sent = await backups.send_db_backup(
        bot,
        {42},
        FakeDb(),
        caption_prefix="DB backup ZIP",
    )

    assert parts_sent > 1
    assert len(bot.messages) == 1
    assert "too large for a single Telegram upload" in bot.messages[0]
    assert len(bot.documents) == parts_sent
    assert bot.documents[0][0] == 42
    assert bot.documents[0][1].endswith(".part001")
    assert "part 1/" in bot.documents[0][2]
    assert list((tmp_path / "backups").glob("*")) == []


@pytest.mark.asyncio
async def test_send_db_backup_retries_with_smaller_parts_on_entity_too_large(monkeypatch, tmp_path: Path) -> None:
    class FakeDb:
        async def export_backup(self, target_path: str) -> None:
            Path(target_path).write_bytes(bytes(range(160)))

    class FakeBot:
        def __init__(self) -> None:
            self.documents: list[tuple[int, str, str]] = []

        async def send_document(self, chat_id: int, document, caption: str) -> None:
            if document.filename.endswith(".zip"):
                raise Exception("Request Entity Too Large")
            self.documents.append((chat_id, document.filename, caption))

    monkeypatch.setattr(backups, "DATABASE_PATH", str(tmp_path / "raceday.db"))
    monkeypatch.setattr(backups, "TELEGRAM_DOCUMENT_MAX_BYTES", 1024)
    monkeypatch.setattr(backups, "TELEGRAM_SEND_DELAY", 0)
    monkeypatch.setattr(backups, "_UPLOAD_HEADROOM_BYTES", 0)
    monkeypatch.setattr(backups, "_MIN_PART_SIZE_BYTES", 32)

    bot = FakeBot()
    parts_sent = await backups.send_db_backup(
        bot,
        {42},
        FakeDb(),
        caption_prefix="DB backup ZIP",
    )

    assert parts_sent > 1
    assert len(bot.documents) == parts_sent
    assert all(".part" in filename for _, filename, _ in bot.documents)
    assert list((tmp_path / "backups").glob("*")) == []
