from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Request

from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.core.production import is_production_cloud
from app.security.config import security_settings


AUDIT_LOG_PATH = Path("data/security/audit.log")
_LOCK = threading.Lock()


def audit_event(event_type: str, *, request: Request | None = None, details: dict[str, Any] | None = None, severity: str = "info") -> dict[str, Any]:
    event = {
        "id": f"AF-AUD-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event_type": event_type,
        "severity": severity,
        "path": request.url.path if request else None,
        "method": request.method if request else None,
        "client": request.client.host if request and request.client else None,
        "details": mask_secrets(details or {}),
    }
    if security_settings.audit_log_enabled and _use_postgres_audit():
        from app.db.postgres import insert_audit_event

        insert_audit_event(mask_secrets(event))
    elif security_settings.audit_log_enabled and not is_production_cloud():
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with AUDIT_LOG_PATH.open("a", encoding="utf-8") as file:
                file.write(json.dumps(mask_secrets(event), ensure_ascii=False, default=str) + "\n")
    return event


def read_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    if _use_postgres_audit():
        from app.db.postgres import list_audit_events

        return list_audit_events(limit)
    if not AUDIT_LOG_PATH.exists():
        return []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def audit_storage_mode() -> str:
    return "postgres" if _use_postgres_audit() else "file"


def _use_postgres_audit() -> bool:
    return settings.db_engine == "postgres" and bool(settings.database_url)
