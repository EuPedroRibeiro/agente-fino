from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.security.audit import audit_event
from app.security.input_validation import validate_text_field
from app.services.sherlock import SherlockService


router = APIRouter(tags=["sherlock"])
templates = Jinja2Templates(directory="app/templates")
service = SherlockService()
UTF8_HTML = "text/html; charset=utf-8"


@router.get("/sherlock", response_class=HTMLResponse)
def sherlock_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "sherlock.html",
        {"app_name": settings.app_name, "app_version": settings.app_version},
        media_type=UTF8_HTML,
    )


@router.get("/api/sherlock/status")
def sherlock_status() -> dict[str, Any]:
    return service.status()


@router.post("/api/sherlock/query")
def sherlock_query(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _safe_operation(request, payload, service.query, "sherlock_query_failed")


@router.post("/api/sherlock/validate-cpf")
def sherlock_validate_cpf(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _safe_operation(request, payload, service.validate_cpf_local, "cpf_validate_failed")


@router.post("/api/sherlock/simulate-cpf")
def sherlock_simulate_cpf(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return _safe_operation(request, payload, service.simulate_cpf, "cpf_lab_failed")


def _safe_operation(
    request: Request,
    payload: dict[str, Any],
    operation: Callable[[str], dict[str, Any]],
    failure_event: str,
) -> dict[str, Any]:
    try:
        document = validate_text_field(
            str(payload.get("document") or payload.get("cpf_cnpj") or payload.get("query") or ""),
            field_name="document",
            max_chars=80,
        )
        return operation(document)
    except Exception as exc:
        audit_event(failure_event, request=request, details={"error": mask_secrets(str(exc))}, severity="error")
        return {
            "status": "error",
            "intent": "sherlock_query",
            "document": "***",
            "answer": "Nao consegui concluir a consulta agora. Tente novamente em instantes.",
            "data": {},
        }
