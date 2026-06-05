from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.system_info import get_health_payload, get_processes, get_system_status
from app.security.config import security_settings
from app.core.config import settings
from app.core.runtime import is_cloud
from app.db import get_database_status
from app.security.audit import audit_storage_mode
from app.security.rate_limit import rate_limit_storage_mode


router = APIRouter()


@router.get("/api/status")
def read_status() -> dict:
    return get_system_status()


@router.get("/api/health")
def read_health() -> dict:
    return get_health_payload()


@router.get("/api/admin/health")
def read_admin_health() -> dict:
    payload = get_health_payload()
    db_status = get_database_status()
    payload["security"] = {
        "enabled": security_settings.enabled,
        "release": security_settings.release_name,
        "csrf_enabled": security_settings.csrf_enabled,
        "rate_limit_enabled": security_settings.rate_limit_enabled,
        "rate_limit_mode": rate_limit_storage_mode(),
        "headers_enabled": security_settings.security_headers_enabled,
        "audit_enabled": security_settings.audit_log_enabled,
        "audit_mode": audit_storage_mode(),
        "session_secret_configured": bool(security_settings.session_secret),
        "admin_password_hash_configured": bool(settings.admin_password_hash),
    }
    payload["database"] = {
        "engine": db_status.engine,
        "configured": db_status.configured,
        "persistent": db_status.persistent,
        "message": db_status.message,
    }
    payload["features"] = {
        "memory_mode": db_status.engine if db_status.persistent else "not_configured",
        "rag_mode": "disabled_in_cloud" if is_cloud() else "local",
        "upload_mode": "disabled" if not security_settings.uploads_enabled else "enabled",
    }
    return payload


@router.get("/api/processes")
def read_processes() -> dict:
    if is_cloud():
        return {"processes": [], "status": "disabled_in_cloud", "message": "Processos locais nao ficam disponiveis no runtime cloud."}
    return {"processes": get_processes()}


@router.websocket("/ws/status")
async def status_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_system_status())
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
