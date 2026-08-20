from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings


ALLOWED_TYPES: dict[str, tuple[str, bytes]] = {
    "application/pdf": (".pdf", b"%PDF-"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
}


class StorageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StoredFile:
    key: str
    size_bytes: int
    sha256: str
    content_type: str


class LocalReportStorage:
    """Local development storage behind a small boundary that can later be swapped for object storage."""

    def __init__(self) -> None:
        settings = get_settings()
        self.root = Path(settings.storage_root).expanduser().resolve()
        self.max_bytes = settings.max_report_upload_mb * 1024 * 1024
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

    def save_upload(self, upload: UploadFile, *, child_id: str, report_id: str, version_id: str) -> StoredFile:
        content_type = (upload.content_type or "").lower().strip()
        if content_type not in ALLOWED_TYPES:
            raise StorageValidationError("Only PDF, PNG and JPEG files are supported")

        suffix, signature = ALLOWED_TYPES[content_type]
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
                raise StorageValidationError("File content does not match its declared type")

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
