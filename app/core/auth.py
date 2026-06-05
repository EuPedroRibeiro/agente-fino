from __future__ import annotations

import hmac
import base64
import hashlib
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings
from app.core.runtime import is_cloud
from app.security.config import security_settings


AUTH_ENABLED = security_settings.enabled and security_settings.require_login
SESSION_COOKIE_NAME = security_settings.session_cookie_name
SESSION_TTL_SECONDS = security_settings.session_ttl_minutes * 60
_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSION_SECRET_WARNING = "AGENTE_FINO_SESSION_SECRET nao configurado; usando segredo efemero de preview."
_EPHEMERAL_SESSION_SECRET = secrets.token_urlsafe(48)


def generate_local_token() -> dict[str, Any]:
    token = _new_session_token()
    return {
        "enabled": AUTH_ENABLED,
        "token": token,
        "message": "Sessao local pronta.",
    }


def validate_token(token: str | None) -> bool:
    if not AUTH_ENABLED:
        return True
    if not token:
        return False
    if _use_postgres_sessions():
        try:
            from app.db.postgres import get_session_record

            return get_session_record(token) is not None
        except Exception:
            return False
    if _use_signed_cookie():
        return _decode_signed_session(token) is not None
    _cleanup_sessions()
    for stored_token, session in list(_SESSIONS.items()):
        if session.get("expires_at", 0) < time.time():
            _SESSIONS.pop(stored_token, None)
            continue
        if hmac.compare_digest(stored_token, token):
            return True
    return False


def create_local_session(response: Response) -> dict[str, Any]:
    if _use_postgres_sessions():
        return _create_postgres_session(response)
    if _use_signed_cookie():
        return _create_signed_session(response)
    token = _new_session_token()
    csrf_token = _new_session_token()
    expires_at = time.time() + SESSION_TTL_SECONDS
    _SESSIONS[token] = {"created_at": time.time(), "expires_at": expires_at, "csrf_token": csrf_token}
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=security_settings.secure_cookies,
        path="/",
    )
    return {
        "authenticated": True,
        "mode": "local-cookie",
        "expires_in_seconds": SESSION_TTL_SECONDS,
    }


def clear_local_session(request: Request, response: Response) -> dict[str, Any]:
    token = token_from_request(request)
    if token:
        if _use_postgres_sessions():
            try:
                from app.db.postgres import revoke_session_record

                revoke_session_record(token)
            except Exception:
                pass
        else:
            _SESSIONS.pop(token, None)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"authenticated": False}


def csrf_payload(request: Request) -> dict[str, Any]:
    token = token_from_request(request)
    if not validate_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao local invalida ou ausente.")
    if _use_postgres_sessions():
        from app.db.postgres import get_session_record

        session = get_session_record(token)
        csrf_token = session.get("csrf_token") if session else None
        if not csrf_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao sem CSRF.")
        return {"csrf_token": csrf_token, "header": "X-CSRF-Token"}
    if _use_signed_cookie():
        payload = _decode_signed_session(token or "") or {}
        csrf_token = payload.get("csrf_token")
        if not csrf_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao sem CSRF.")
        return {"csrf_token": csrf_token, "header": "X-CSRF-Token"}
    session = _SESSIONS.get(token or "")
    csrf_token = session.get("csrf_token") if session else None
    if not csrf_token:
        csrf_token = _new_session_token()
        if session is not None:
            session["csrf_token"] = csrf_token
    return {"csrf_token": csrf_token, "header": "X-CSRF-Token"}


def validate_csrf_token(session_token: str | None, csrf_token: str | None) -> bool:
    if not security_settings.csrf_enabled:
        return True
    if not session_token or not csrf_token:
        return False
    if _use_postgres_sessions():
        try:
            from app.db.postgres import get_session_record

            session = get_session_record(session_token)
            expected = session.get("csrf_token") if session else None
            return bool(expected and hmac.compare_digest(str(expected), str(csrf_token)))
        except Exception:
            return False
    if _use_signed_cookie():
        payload = _decode_signed_session(session_token)
        expected = payload.get("csrf_token") if payload else None
        return bool(expected and hmac.compare_digest(str(expected), str(csrf_token)))
    session = _SESSIONS.get(session_token)
    expected = session.get("csrf_token") if session else None
    return bool(expected and hmac.compare_digest(str(expected), str(csrf_token)))


def require_local_auth(request: Request) -> None:
    if not AUTH_ENABLED:
        return
    if _is_safe_public_path(request):
        return
    if not validate_token(token_from_request(request)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao local invalida ou ausente.")
    _require_same_origin_for_unsafe_methods(request)


def get_auth_status() -> dict[str, Any]:
    _cleanup_sessions()
    return {
        "enabled": AUTH_ENABLED,
        "mode": "postgres-session" if _use_postgres_sessions() else ("signed-cookie" if _use_signed_cookie() else "local-cookie"),
        "active_sessions": 0 if _use_signed_cookie() else len(_SESSIONS),
        "admin_user": settings.admin_user,
        "password_configured": bool(settings.admin_password_hash),
        "message": _auth_status_message(),
    }


def can_login_with_payload(payload: dict[str, Any] | None) -> bool:
    if not security_settings.public_mode:
        return True
    if not settings.admin_password_hash:
        return False
    password = str((payload or {}).get("password") or "")
    return verify_password(password, settings.admin_password_hash)


def hash_password(password: str, *, salt: str | None = None, iterations: int = 260_000) -> str:
    safe_salt = salt or secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), safe_salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${safe_salt}${base64.urlsafe_b64encode(digest).decode('ascii')}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hash_password(password, salt=salt, iterations=int(iterations)).split("$", 3)[3]
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _new_session_token() -> str:
    return secrets.token_urlsafe(32)


def _cleanup_sessions() -> None:
    now = time.time()
    expired = [token for token, session in _SESSIONS.items() if float(session.get("expires_at", 0)) < now]
    for token in expired:
        _SESSIONS.pop(token, None)


def token_from_request(request: Request) -> str | None:
    header_token = request.headers.get("X-Agente-Fino-Session")
    return header_token or request.cookies.get(SESSION_COOKIE_NAME)


def _is_safe_public_path(request: Request) -> bool:
    return request.url.path in {"/", "/login", "/api/auth/login", "/api/auth/status", "/api/auth/csrf", "/api/health", "/favicon.ico"} or request.url.path.startswith("/static/")


def _require_same_origin_for_unsafe_methods(request: Request) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    expected_host = request.url.netloc
    for header_name in ("origin", "referer"):
        value = request.headers.get(header_name)
        if not value:
            continue
        if expected_host and expected_host not in value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origem da requisicao nao permitida.")


def _use_signed_cookie() -> bool:
    if _use_postgres_sessions():
        return False
    return is_cloud() or security_settings.public_mode


def _use_postgres_sessions() -> bool:
    return is_cloud() and settings.db_engine == "postgres" and bool(settings.database_url)


def _session_secret() -> str:
    return security_settings.session_secret or settings.admin_password_hash or _EPHEMERAL_SESSION_SECRET


def _create_signed_session(response: Response) -> dict[str, Any]:
    expires_at = int(time.time() + SESSION_TTL_SECONDS)
    csrf_token = _new_session_token()
    payload = {
        "sub": settings.admin_user or "admin",
        "csrf_token": csrf_token,
        "iat": int(time.time()),
        "exp": expires_at,
    }
    token = _encode_signed_session(payload)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=security_settings.secure_cookies,
        path="/",
    )
    return {
        "authenticated": True,
        "mode": "signed-cookie",
        "expires_in_seconds": SESSION_TTL_SECONDS,
        "warning": None if security_settings.session_secret or settings.admin_password_hash else _SESSION_SECRET_WARNING,
    }


def _create_postgres_session(response: Response) -> dict[str, Any]:
    token = _new_session_token()
    csrf_token = _new_session_token()
    expires_at = time.time() + SESSION_TTL_SECONDS
    try:
        from app.db.postgres import create_session_record

        create_session_record(
            token=token,
            csrf_token=csrf_token,
            username=settings.admin_user or "admin",
            expires_at=expires_at,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao criar sessao persistente: {str(exc)}") from exc
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=security_settings.secure_cookies,
        path="/",
    )
    return {
        "authenticated": True,
        "mode": "postgres-session",
        "expires_in_seconds": SESSION_TTL_SECONDS,
    }


def _auth_status_message() -> str:
    if _use_postgres_sessions():
        return "Sessoes persistentes em Postgres ativas."
    if _use_signed_cookie():
        return "Autenticacao stateless cloud ativa."
    return "Autenticacao local ativa para endpoints sensiveis."


def _encode_signed_session(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(_session_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}"


def _decode_signed_session(token: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(_session_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(_pad_b64(signature))
        if not hmac.compare_digest(actual, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(_pad_b64(body)).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def _pad_b64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")
