from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.security.config import security_settings


def content_security_policy() -> str:
    script_src = "'self'"
    if not security_settings.public_mode:
        script_src = "'self' 'unsafe-inline'"
        if security_settings.csp_allow_blob_script:
            script_src = f"{script_src} blob:"
    return "; ".join(
        [
            "default-src 'self'",
            f"script-src {script_src}",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self' data:",
            "connect-src 'self' http://127.0.0.1:8765 http://localhost:8765",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
    )


def apply_security_headers(response: Response, *, https: bool = False) -> Response:
    if not security_settings.security_headers_enabled:
        return response
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", content_security_policy())
    if https or security_settings.secure_cookies:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        return apply_security_headers(response, https=request.url.scheme == "https")
