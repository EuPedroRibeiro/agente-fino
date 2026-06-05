from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.security.audit import audit_event
from app.security.input_validation import validate_text_field
from modules.darkforest import DarkForestService


router = APIRouter(tags=["darkforest"])
templates = Jinja2Templates(directory="app/templates")
UTF8_HTML = "text/html; charset=utf-8"
service = DarkForestService()


@router.get("/security", response_class=HTMLResponse)
@router.get("/darkforest", response_class=HTMLResponse)
@router.get("/scanner", response_class=HTMLResponse)
def darkforest_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "darkforest.html",
        {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "darkforest_enabled": service.config.enabled,
        },
        media_type=UTF8_HTML,
    )


@router.get("/api/security/darkforest/status")
def darkforest_status() -> dict[str, Any]:
    return service.status()


@router.get("/api/security/darkforest/history")
def darkforest_history(limit: int = Query(default=30, ge=1, le=100)) -> dict[str, Any]:
    return {"history": service.history(limit)}


@router.post("/api/security/darkforest/scan")
def darkforest_scan(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    target = validate_text_field(str(payload.get("target") or ""), field_name="target", max_chars=8000)
    accepted_notice = bool(payload.get("accepted_notice"))
    confirmed_authorization = bool(payload.get("confirmed_authorization"))
    audit_event(
        "darkforest_scan_requested",
        request=request,
        details={
            "target_preview": target[:180],
            "accepted_notice": accepted_notice,
            "confirmed_authorization": confirmed_authorization,
        },
        severity="warning",
    )
    try:
        report = service.scan(
            target=target,
            accepted_notice=accepted_notice,
            confirmed_authorization=confirmed_authorization,
            user=settings.admin_user,
        )
    except PermissionError as exc:
        audit_event("darkforest_scan_blocked", request=request, details={"reason": str(exc)}, severity="warning")
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        audit_event("darkforest_scan_failed", request=request, details={"reason": "target_not_found"}, severity="warning")
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        audit_event("darkforest_scan_failed", request=request, details={"reason": str(exc)}, severity="warning")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        audit_event("darkforest_scan_failed", request=request, details={"reason": str(exc)}, severity="warning")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    audit_event(
        "darkforest_scan_completed",
        request=request,
        details={
            "status": report.get("status"),
            "risk_level": report.get("risk_level"),
            "findings_count": report.get("findings_count"),
            "target_type": report.get("target_type"),
        },
        severity="warning" if report.get("findings_count") else "info",
    )
    return report

