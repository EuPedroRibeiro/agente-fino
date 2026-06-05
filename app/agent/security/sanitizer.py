from __future__ import annotations

import re
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(api[_-]?key|token|senha|password|authorization)\s*[:=]\s*([^\s\"']+)", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
]


def mask_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: mask_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    if not isinstance(value, str):
        return value
    text = value
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}=***" if match.lastindex and match.lastindex >= 2 else "***", text)
    return text


def contains_secret(value: str) -> bool:
    return any(pattern.search(value or "") for pattern in SECRET_PATTERNS)
