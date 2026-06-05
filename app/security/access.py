from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth import validate_token, token_from_request
from app.security.audit import audit_event
from app.security.config import security_settings


PUBLIC_PREFIXES = ("/static/",)
PUBLIC_PATHS = {
    "/",
    "/login",
    "/favicon.ico",
    "/api/auth/login",
    "/api/auth/status",
    "/api/health",
}
PROTECTED_PREFIXES = (
    "/agent",
    "/security",
    "/darkforest",
    "/scanner",
    "/mcp-brasil",
    "/api/auth/csrf",
    "/api/auth/logout",
    "/api/agent/",
    "/api/actions/",
    "/api/logs",
    "/api/report",
    "/api/processes",
    "/api/security/",
    "/api/mcp-brasil/",
    "/api/public-data/",
    "/api/status",
    "/api/admin/",
)


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def is_protected_path(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not security_settings.enabled or not security_settings.require_login:
            return await call_next(request)
        path = request.url.path
        if is_public_path(path) or not is_protected_path(path):
            return await call_next(request)
        if validate_token(token_from_request(request)):
            return await call_next(request)
        audit_event("auth_required_failed", request=request, details={"path": path}, severity="warning")
        if path in {"/agent", "/security", "/darkforest", "/scanner", "/mcp-brasil"}:
            return RedirectResponse("/login", status_code=303)
        return JSONResponse({"detail": "Autenticacao local necessaria."}, status_code=401)
