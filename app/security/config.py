from __future__ import annotations

import os
from functools import lru_cache
from pydantic import BaseModel, Field


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return list(default)
    cleaned = raw.strip().strip("[]")
    return [item.strip() for item in cleaned.split(",") if item.strip()]


class SecuritySettings(BaseModel):
    enabled: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_SECURITY_ENABLED", True))
    environment: str = Field(default_factory=lambda: os.getenv("AGENTE_FINO_ENV", "local").strip().lower())
    public_mode: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_PUBLIC_MODE", False))
    require_login: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_REQUIRE_LOGIN", True))
    session_secret: str = Field(default_factory=lambda: os.getenv("AGENTE_FINO_SESSION_SECRET", ""))
    session_cookie_name: str = Field(default_factory=lambda: os.getenv("AGENTE_FINO_SESSION_COOKIE_NAME", "agente_fino_session"))
    session_ttl_minutes: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_SESSION_TTL_MINUTES", 720))
    csrf_enabled: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_CSRF_ENABLED", True))
    rate_limit_enabled: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_RATE_LIMIT_ENABLED", True))
    csp_allow_blob_script: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_CSP_ALLOW_BLOB_SCRIPT", False))
    rate_limit_chat_per_minute: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_RATE_LIMIT_CHAT_PER_MINUTE", 30))
    rate_limit_login_per_minute: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_RATE_LIMIT_LOGIN_PER_MINUTE", 10))
    rate_limit_global_per_minute: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_RATE_LIMIT_GLOBAL_PER_MINUTE", 120))
    rate_limit_tools_per_minute: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_RATE_LIMIT_TOOLS_PER_MINUTE", 10))
    rate_limit_deep_search_per_minute: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_RATE_LIMIT_DEEP_SEARCH_PER_MINUTE", 5))
    security_headers_enabled: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_SECURITY_HEADERS_ENABLED", True))
    audit_log_enabled: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_AUDIT_LOG_ENABLED", True))
    uploads_enabled: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_UPLOADS_ENABLED", True))
    max_upload_mb: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_MAX_UPLOAD_MB", 25))
    block_dangerous_tools: bool = Field(default_factory=lambda: _env_bool("AGENTE_FINO_BLOCK_DANGEROUS_TOOLS", True))
    require_confirmation_for_system_actions: bool = Field(
        default_factory=lambda: _env_bool("AGENTE_FINO_REQUIRE_CONFIRMATION_FOR_SYSTEM_ACTIONS", True)
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: _env_list(
            "AGENTE_FINO_ALLOWED_ORIGINS",
            ["http://127.0.0.1:8765", "http://localhost:8765"],
        )
    )
    max_chat_message_chars: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_MAX_CHAT_MESSAGE_CHARS", 16000))
    max_title_chars: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_MAX_TITLE_CHARS", 200))
    max_path_chars: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_MAX_PATH_CHARS", 1000))
    max_filename_chars: int = Field(default_factory=lambda: _env_int("AGENTE_FINO_MAX_FILENAME_CHARS", 255))

    @property
    def secure_cookies(self) -> bool:
        return self.public_mode or self.environment in {"production", "public", "prod"}

    @property
    def release_name(self) -> str:
        return "Agente Fino 2.1.1 / Production Repository Cleanup"


@lru_cache
def get_security_settings() -> SecuritySettings:
    return SecuritySettings()


security_settings = get_security_settings()
