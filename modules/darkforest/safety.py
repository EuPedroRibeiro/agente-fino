from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


WINDOWS_DRIVE = re.compile(r"^[a-zA-Z]:[\\/]")


@dataclass(frozen=True)
class DarkForestConfig:
    enabled: bool
    external_path: str
    max_runtime_seconds: int
    mask_secrets: bool
    save_history: bool
    allow_remote_targets: bool = False

    @classmethod
    def from_env(cls) -> "DarkForestConfig":
        return cls(
            enabled=os.getenv("DARKFOREST_ENABLED", "true").strip().lower() == "true",
            external_path=os.getenv("DARKFOREST_PATH", "./tools/DarkForest-Hunter-OpenAI"),
            max_runtime_seconds=max(3, int(os.getenv("DARKFOREST_MAX_RUNTIME", "120"))),
            mask_secrets=os.getenv("DARKFOREST_MASK_SECRETS", "true").strip().lower() == "true",
            save_history=os.getenv("DARKFOREST_SAVE_HISTORY", "true").strip().lower() == "true",
            allow_remote_targets=os.getenv("DARKFOREST_ALLOW_REMOTE_TARGETS", "false").strip().lower() == "true",
        )


def ensure_authorized(*, accepted_notice: bool, confirmed_authorization: bool) -> None:
    if not accepted_notice or not confirmed_authorization:
        raise PermissionError("Confirme o aviso sensivel e a autorizacao antes de iniciar a analise.")


def classify_target(target: str) -> str:
    clean = (target or "").strip().strip("\"'")
    if not clean:
        return "empty"
    parsed = urlparse(clean)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return "remote_url"
    if WINDOWS_DRIVE.search(clean) or clean.startswith((".", "/", "\\")) or Path(clean).exists():
        return "path"
    return "text"


def safe_target_label(target: str) -> str:
    clean = (target or "").strip().replace("\r", " ").replace("\n", " ")
    if len(clean) <= 180:
        return clean
    return f"{clean[:90]}...{clean[-60:]}"

