from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.redlab.engine import RedLabEngine
from app.security.audit import audit_event
from app.security.input_validation import validate_text_field


router = APIRouter(tags=["redlab"])
templates = Jinja2Templates(directory="app/templates")
engine = RedLabEngine()
UTF8_HTML = "text/html; charset=utf-8"


def _user() -> str:
    return settings.admin_user or "local"


def _safe(request: Request, operation: str, callback: Callable[[], Any]) -> Any:
    try:
        return callback()
    except PermissionError as exc:
        audit_event(f"redlab_{operation}_blocked", request=request, details={"reason": str(exc)}, severity="warning")
        return JSONResponse({"status": "blocked", "message": str(exc)}, status_code=403)
    except (ValueError, KeyError) as exc:
        audit_event(f"redlab_{operation}_invalid", request=request, details={"reason": str(exc)}, severity="warning")
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
    except Exception:
        audit_event(f"redlab_{operation}_failed", request=request, details={"reason": "internal_error"}, severity="error")
        return JSONResponse({"status": "error", "message": "Nao foi possivel concluir esta operacao agora."}, status_code=503)


@router.get("/redlab", response_class=HTMLResponse)
@router.get("/agent/redlab", response_class=HTMLResponse)
def redlab_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "redlab.html", {"app_name": settings.app_name, "app_version": settings.app_version}, media_type=UTF8_HTML)


@router.get("/api/redlab/status")
def redlab_status() -> dict:
    return engine.status()


@router.get("/api/redlab/labs")
def redlab_labs() -> dict:
    return {"status": "success", "labs": engine.list_labs()}


@router.post("/api/redlab/start")
def redlab_start(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    return _safe(request, "start", lambda: engine.start(_user(), str(payload.get("lab_id") or ""), str(payload.get("mode") or "sandbox"), payload.get("target_url")))


@router.post("/api/redlab/validate")
def redlab_validate(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    lab_payload = validate_text_field(str(payload.get("payload") or ""), field_name="payload", max_chars=4000)
    return _safe(request, "validate", lambda: engine.validate_lab(_user(), str(payload.get("run_id") or ""), str(payload.get("lab_id") or ""), lab_payload))


@router.post("/api/redlab/patch")
def redlab_patch(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    return _safe(request, "patch", lambda: engine.patch(_user(), str(payload.get("run_id") or ""), str(payload.get("lab_id") or "")))


@router.get("/api/redlab/report")
def redlab_report(request: Request, run_id: str = Query(..., min_length=3, max_length=80)) -> Any:
    return _safe(request, "report", lambda: engine.report(_user(), run_id))


@router.get("/api/redlab/history")
def redlab_history(limit: int = Query(default=30, ge=1, le=100)) -> dict:
    return {"history": engine.history(_user(), limit)}


@router.get("/api/redlab/progress")
def redlab_progress() -> dict:
    return engine.progress(_user())


@router.get("/api/redlab/leaderboard")
def redlab_leaderboard(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"leaderboard": engine.leaderboard(limit)}


@router.post("/api/redlab/target/set")
def redlab_target_set(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    url = validate_text_field(str(payload.get("url") or ""), field_name="url", max_chars=1000)
    def validate() -> dict[str, Any]:
        valid, message, host = engine.target_engine.validate_target(url, bool(payload.get("confirmed")))
        return {"valid": valid, "message": message, "host": host}

    return _safe(request, "target_set", validate)


@router.post("/api/redlab/target/scan")
def redlab_target_scan(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    url = validate_text_field(str(payload.get("url") or ""), field_name="url", max_chars=1000)
    techniques = [str(item) for item in payload.get("techniques") or []]
    audit_event("redlab_target_preflight_requested", request=request, details={"url": url, "techniques": techniques}, severity="warning")
    return _safe(request, "target_scan", lambda: engine.target_scan(_user(), url, techniques, bool(payload.get("confirmed"))))
