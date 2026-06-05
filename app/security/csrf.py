from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth import token_from_request, validate_csrf_token, validate_token
from app.security.access import is_public_path, is_protected_path
from app.security.audit import audit_event
from app.security.config import security_settings


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {"/api/auth/login", "/api/auth/csrf"}


class CsrfProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not security_settings.enabled or not security_settings.csrf_enabled:
            return await call_next(request)
        path = request.url.path
        if request.method.upper() not in UNSAFE_METHODS or path in CSRF_EXEMPT_PATHS or is_public_path(path):
            return await call_next(request)
        token = token_from_request(request)
        if not token or not validate_token(token) or not is_protected_path(path):
            return await call_next(request)
        csrf_token = request.headers.get("X-CSRF-Token")
        if validate_csrf_token(token, csrf_token):
            return await call_next(request)
        audit_event("csrf_failed", request=request, details={"path": path}, severity="warning")
        return JSONResponse({"detail": "CSRF token ausente ou invalido."}, status_code=403)

