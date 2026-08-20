from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings


REPORT_ALLOWED_TYPES: dict[str, tuple[str, bytes]] = {
    "application/pdf": (".pdf", b"%PDF-"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
}

VOICE_ALLOWED_TYPES: dict[str, str] = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
}


class StorageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StoredFile:
    key: str
    size_bytes: int
    sha256: str
    content_type: str


class _LocalStorageBase:
    def __init__(self) -> None:
        settings = get_settings()
        self.root = Path(settings.storage_root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise StorageValidationError("Invalid storage key")
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StorageValidationError("Invalid storage key") from exc
        return candidate

    def resolve(self, key: str) -> Path:
        path = self._safe_path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path

    def delete(self, key: str) -> None:
        try:
            path = self._safe_path(key)
        except StorageValidationError:
            return
        if path.exists():
            path.unlink()


class LocalReportStorage(_LocalStorageBase):
    """Local development report storage behind an object-storage boundary."""

    def __init__(self) -> None:
        super().__init__()
        self.max_bytes = get_settings().max_report_upload_mb * 1024 * 1024

    def save_upload(
        self,
        upload: UploadFile,
        *,
        child_id: str,
        report_id: str,
        version_id: str,
    ) -> StoredFile:
        content_type = (upload.content_type or "").lower().strip()
        if content_type not in REPORT_ALLOWED_TYPES:
            raise StorageValidationError("Only PDF, PNG and JPEG files are supported")

        suffix, signature = REPORT_ALLOWED_TYPES[content_type]
        key = f"reports/{child_id}/{report_id}/{version_id}{suffix}"
        destination = self._safe_path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")

        size = 0
        digest = hashlib.sha256()
        first_bytes = b""
        try:
            with temporary.open("wb") as handle:
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    if not first_bytes:
                        first_bytes = chunk[:16]
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise StorageValidationError(
                            f"File is too large. Maximum size is {get_settings().max_report_upload_mb} MB"
                        )
                    digest.update(chunk)
                    handle.write(chunk)

            if size == 0:
                raise StorageValidationError("Uploaded file is empty")
            if not first_bytes.startswith(signature):
                raise StorageValidationError(
                    "File content does not match its declared type"
                )

            temporary.replace(destination)
            return StoredFile(
                key=key,
                size_bytes=size,
                sha256=digest.hexdigest(),
                content_type=content_type,
            )
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise


class LocalVoiceStorage(_LocalStorageBase):
    """Local audio storage. Can later be replaced with object storage."""

    def __init__(self) -> None:
        super().__init__()
        self.max_bytes = get_settings().max_voice_upload_mb * 1024 * 1024

    @staticmethod
    def _signature_matches(content_type: str, first_bytes: bytes) -> bool:
        if content_type == "audio/webm":
            return first_bytes.startswith(b"\x1a\x45\xdf\xa3")
        if content_type in {"audio/wav", "audio/x-wav"}:
            return first_bytes.startswith(b"RIFF")
        if content_type == "audio/mpeg":
            return first_bytes.startswith(b"ID3") or (
                len(first_bytes) >= 2
                and first_bytes[0] == 0xFF
                and (first_bytes[1] & 0xE0) == 0xE0
            )
        if content_type in {"audio/mp4", "audio/x-m4a"}:
            return len(first_bytes) >= 12 and b"ftyp" in first_bytes[4:12]
        return False

    def save_upload(
        self,
        upload: UploadFile,
        *,
        child_id: str,
        voice_note_id: str,
    ) -> StoredFile:
        raw_type = (upload.content_type or "").lower().strip()
        content_type = raw_type.split(";", 1)[0].strip()
        if content_type not in VOICE_ALLOWED_TYPES:
            raise StorageValidationError(
                "Only WebM, WAV, MP3 and M4A audio files are supported"
            )

        suffix = VOICE_ALLOWED_TYPES[content_type]
        key = f"voice/{child_id}/{voice_note_id}{suffix}"
        destination = self._safe_path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")

        size = 0
        digest = hashlib.sha256()
        first_bytes = b""
        try:
            with temporary.open("wb") as handle:
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    if not first_bytes:
                        first_bytes = chunk[:32]
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise StorageValidationError(
                            f"Audio is too large. Maximum size is {get_settings().max_voice_upload_mb} MB"
                        )
                    digest.update(chunk)
                    handle.write(chunk)

            if size == 0:
                raise StorageValidationError("Uploaded audio is empty")
            if not self._signature_matches(content_type, first_bytes):
                raise StorageValidationError(
                    "Audio content does not match its declared type"
                )

            temporary.replace(destination)
            return StoredFile(
                key=key,
                size_bytes=size,
                sha256=digest.hexdigest(),
                content_type=content_type,
            )
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
