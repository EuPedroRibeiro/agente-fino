from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.security.audit import audit_event
from app.security.input_validation import validate_chat_message
from modules.mcp_brasil import MCPBrasilService


router = APIRouter(tags=["mcp-brasil"])
templates = Jinja2Templates(directory="app/templates")
UTF8_HTML = "text/html; charset=utf-8"
service = MCPBrasilService()


@router.get("/mcp-brasil", response_class=HTMLResponse)
def mcp_brasil_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "mcp_brasil.html",
        {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "mcp_brasil_status": service.status(),
        },
        media_type=UTF8_HTML,
    )


@router.get("/api/mcp-brasil/status")
def mcp_brasil_status() -> dict[str, Any]:
    return service.status()


@router.get("/api/mcp-brasil/features")
def mcp_brasil_features() -> dict[str, Any]:
    return service.list_features()


@router.post("/api/mcp-brasil/start")
def mcp_brasil_start(request: Request) -> dict[str, Any]:
    audit_event("mcp_brasil_start_requested", request=request, details={"module": "mcp-brasil"})
    return service.start_server()


@router.post("/api/mcp-brasil/stop")
def mcp_brasil_stop(request: Request) -> dict[str, Any]:
    audit_event("mcp_brasil_stop_requested", request=request, details={"module": "mcp-brasil"})
    return service.stop_server()


@router.post("/api/mcp-brasil/query")
def mcp_brasil_query(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    message = validate_chat_message(str(payload.get("message") or payload.get("query") or ""))
    result = service.ask(message, user=settings.admin_user)
    audit_event(
        "mcp_brasil_query",
        request=request,
        details={"intent": result.get("intent"), "tool": result.get("tool"), "status": result.get("status")},
    )
    if result.get("status") in {"disabled", "missing"}:
        raise HTTPException(status_code=503, detail=result.get("answer"))
    return result
