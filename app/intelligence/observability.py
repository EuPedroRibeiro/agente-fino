from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from app.agent.security.sanitizer import mask_secrets


_RECENT_DECISIONS: deque[dict[str, Any]] = deque(maxlen=200)


def record_decision(decision: Any) -> None:
    payload = decision.model_dump(mode="json") if hasattr(decision, "model_dump") else dict(decision)
    _RECENT_DECISIONS.append(
        mask_secrets(
            {
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "intent": payload.get("intent"),
                "mode": payload.get("mode"),
                "confidence": payload.get("confidence"),
                "risk_level": payload.get("risk_level"),
                "selected_tools": payload.get("selected_tools") or [],
                "router": payload.get("router"),
                "reason": payload.get("reason"),
                "blocked_tools": payload.get("blocked_tools") or [],
            }
        )
    )


def recent_decisions(limit: int = 20) -> list[dict[str, Any]]:
    return list(_RECENT_DECISIONS)[-max(1, min(limit, 100)) :]
