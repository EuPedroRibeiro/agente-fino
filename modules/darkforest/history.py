from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.agent.security.sanitizer import mask_secrets
from modules.darkforest.safety import safe_target_label


HISTORY_PATH = Path("data/darkforest/history.jsonl")
_LOCK = threading.Lock()


def save_scan_history(*, user: str, target: str, findings_count: int, risk_level: str, status: str) -> dict[str, Any]:
    entry = {
        "id": f"DF-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": user or "local",
        "target": safe_target_label(target),
        "findings_count": int(findings_count),
        "risk_level": risk_level,
        "status": status,
    }
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with HISTORY_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(mask_secrets(entry), ensure_ascii=False, default=str) + "\n")
    return entry


def read_scan_history(limit: int = 30) -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            rows.append(mask_secrets(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return rows

