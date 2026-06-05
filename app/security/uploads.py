from __future__ import annotations

import secrets
from pathlib import Path

from app.security.config import security_settings
from app.security.input_validation import validate_filename


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".txt", ".md"}
BLOCKED_EXTENSIONS = {".bat", ".cmd", ".ps1", ".exe", ".dll", ".scr", ".msi", ".vbs", ".js", ".jar", ".com", ".reg"}
ALLOWED_MIME_PREFIXES = {"image/", "text/"}
ALLOWED_MIME_TYPES = {"application/pdf", "text/markdown", "application/octet-stream"}


class UploadRejected(ValueError):
    pass


def validate_upload_metadata(filename: str, size_bytes: int, content_type: str | None = None) -> dict:
    if not security_settings.uploads_enabled:
        raise UploadRejected("Uploads estao desativados.")
    safe_name = Path(validate_filename(filename)).name
    extension = Path(safe_name).suffix.lower()
    if not extension or extension in BLOCKED_EXTENSIONS:
        raise UploadRejected("Tipo de arquivo bloqueado por seguranca.")
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadRejected("Tipo de arquivo nao permitido.")
    max_bytes = security_settings.max_upload_mb * 1024 * 1024
    if size_bytes < 0 or size_bytes > max_bytes:
        raise UploadRejected(f"Arquivo excede o limite de {security_settings.max_upload_mb} MB.")
    mime = (content_type or "").lower().strip()
    if mime and not (mime in ALLOWED_MIME_TYPES or any(mime.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES)):
        raise UploadRejected("MIME type nao permitido.")
    random_name = f"{secrets.token_urlsafe(16)}{extension}"
    return {
        "original_filename": safe_name,
        "safe_filename": random_name,
        "extension": extension,
        "size_bytes": size_bytes,
        "content_type": mime or "application/octet-stream",
    }

