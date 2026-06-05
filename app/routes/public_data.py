from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from app.core.config import settings
from app.agent.security.sanitizer import mask_secrets
from app.security.audit import audit_event
from app.security.input_validation import validate_chat_message
from app.services.public_data import PublicDataService


router = APIRouter(tags=["public-data"])
service = PublicDataService()


@router.get("/api/public-data/status")
def public_data_status() -> dict[str, Any]:
    return service.status()


@router.post("/api/public-data/query")
def public_data_query(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        message = validate_chat_message(str(payload.get("message") or payload.get("query") or ""))
        result = service.ask(message, user=settings.admin_user)
        audit_event(
            "public_data_endpoint_query",
            request=request,
            details={"intent": result.get("intent"), "topic": result.get("topic"), "tool": result.get("tool"), "status": result.get("status")},
        )
        return result
    except Exception as exc:
        audit_event(
            "public_data_endpoint_failed",
            request=request,
            details={"error": mask_secrets(str(exc))},
            severity="error",
        )
        return {
            "status": "error",
            "intent": "public_data_query",
            "answer": "Nao consegui consultar a fonte publica agora. Tente novamente em instantes.",
            "web_used": False,
        }
