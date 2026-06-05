from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth import token_from_request
from app.core.config import settings
from app.security.access import is_public_path
from app.security.audit import audit_event
from app.security.config import security_settings


@dataclass
class RateLimitBucket:
    count: int
    reset_at: float


_BUCKETS: dict[str, RateLimitBucket] = {}


def clear_rate_limits() -> None:
    _BUCKETS.clear()


def allow_request(key: str, *, limit: int, window_seconds: int = 60, now: float | None = None) -> bool:
    if _use_postgres_rate_limit():
        from app.db.postgres import allow_postgres_rate_limit

        return allow_postgres_rate_limit(key, limit=limit, window_seconds=window_seconds, now=now)
    now = now or time.time()
    bucket = _BUCKETS.get(key)
    if not bucket or now >= bucket.reset_at:
        _BUCKETS[key] = RateLimitBucket(count=1, reset_at=now + window_seconds)
        return True
    if bucket.count >= limit:
        return False
    bucket.count += 1
    return True


def rate_group_for_path(path: str) -> tuple[str, int]:
    if path == "/api/auth/login":
        return "login", security_settings.rate_limit_login_per_minute
    if path in {"/api/agent/chat", "/api/agent/runs"}:
        return "chat", security_settings.rate_limit_chat_per_minute
    if "deep-research" in path or "/api/agent/search/deep" in path:
        return "deep_search", security_settings.rate_limit_deep_search_per_minute
    if path.startswith("/api/actions/") or path.startswith("/api/agent/tools/"):
        return "tools", security_settings.rate_limit_tools_per_minute
    return "global", security_settings.rate_limit_global_per_minute


def rate_identity(request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    session = token_from_request(request) or ""
    session_hash = hashlib.sha256(session.encode("utf-8")).hexdigest()[:16] if session else "anon"
    return f"{client}:{session_hash}"


def rate_limit_storage_mode() -> str:
    return "postgres" if _use_postgres_rate_limit() else "memory_preview"


def _use_postgres_rate_limit() -> bool:
    return settings.db_engine == "postgres" and bool(settings.database_url)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not security_settings.enabled or not security_settings.rate_limit_enabled:
            return await call_next(request)
        path = request.url.path
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"} and is_public_path(path):
            return await call_next(request)
        group, limit = rate_group_for_path(path)
        key = f"{group}:{rate_identity(request)}"
        if allow_request(key, limit=limit):
            return await call_next(request)
        audit_event("rate_limit_hit", request=request, details={"group": group, "limit": limit}, severity="warning")
        return JSONResponse({"detail": "Muitas requisicoes. Tente novamente em instantes."}, status_code=429)
