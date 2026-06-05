from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.agent.security.sanitizer import mask_secrets


ONLINE_TTL_SECONDS = 60.0
TRANSIENT_ERROR_TTL_SECONDS = 30.0
RATE_LIMIT_TTL_SECONDS = 300.0


@dataclass
class CachedProviderStatus:
    provider: str
    status: dict[str, Any]
    last_checked_at: float
    expires_at: float
    cooldown_until: float = 0.0
    last_error_sanitized: str | None = None

    def valid(self, now: float | None = None) -> bool:
        now = now or time.time()
        return now < self.expires_at or now < self.cooldown_until

    def cooling_down(self, now: float | None = None) -> bool:
        now = now or time.time()
        return now < self.cooldown_until


class ProviderStatusCache:
    def __init__(self) -> None:
        self._items: dict[str, CachedProviderStatus] = {}

    def get(self, provider: str) -> CachedProviderStatus | None:
        item = self._items.get(_key(provider))
        if item and item.valid():
            return item
        return None

    def get_status(self, provider: str) -> dict[str, Any] | None:
        item = self.get(provider)
        if not item:
            return None
        status = dict(item.status)
        status["provider_status_cache_hit"] = True
        if item.cooling_down():
            status["cooldown_until"] = item.cooldown_until
        return status

    def is_cooling_down(self, provider: str) -> bool:
        item = self.get(provider)
        return bool(item and item.cooling_down())

    def set_status(self, provider: str, status: dict[str, Any], *, error: str | None = None) -> dict[str, Any]:
        now = time.time()
        sanitized_error = mask_secrets(error or status.get("last_error") or "")
        available = bool(status.get("available") or status.get("online"))
        status_name = _status_name(provider, status, sanitized_error)
        ttl = ONLINE_TTL_SECONDS if available else _ttl_for_error(sanitized_error, status_name)
        cooldown = _cooldown_for_error(sanitized_error, status_name)
        enriched = dict(status)
        enriched["provider_status_cache_hit"] = False
        enriched["last_error"] = None if available else sanitized_error
        enriched["last_error_sanitized"] = None if available else sanitized_error
        if status_name:
            enriched[f"{_status_field(provider)}"] = status_name
        item = CachedProviderStatus(
            provider=provider,
            status=enriched,
            last_checked_at=now,
            expires_at=now + ttl,
            cooldown_until=now + cooldown if cooldown else 0.0,
            last_error_sanitized=None if available else sanitized_error,
        )
        self._items[_key(provider)] = item
        return dict(enriched)

    def clear(self, provider: str | None = None) -> None:
        if provider:
            self._items.pop(_key(provider), None)
        else:
            self._items.clear()


STATUS_CACHE = ProviderStatusCache()


def classify_provider_error(error: str | None) -> str:
    text = (error or "").lower()
    if "quota" in text or "insufficient_quota" in text:
        return "quota_exceeded"
    if "rate" in text or "429" in text or "too many requests" in text:
        return "rate_limited"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "offline" in text or "refused" in text or "unreachable" in text:
        return "offline"
    return "error" if text else ""


def _key(provider: str) -> str:
    return provider.replace("_", "-")


def _status_field(provider: str) -> str:
    key = _key(provider)
    if key == "openai-responses":
        return "openai_status"
    if key == "gemini":
        return "gemini_status"
    if key == "ollama":
        return "ollama_status"
    if key == "litellm":
        return "litellm_status"
    return "status"


def _status_name(provider: str, status: dict[str, Any], error: str | None) -> str:
    if status.get("available") or status.get("online"):
        return "online"
    existing = status.get(_status_field(provider))
    if existing:
        return str(existing)
    return classify_provider_error(error)


def _ttl_for_error(error: str | None, status_name: str) -> float:
    if status_name in {"quota_exceeded", "rate_limited"}:
        return RATE_LIMIT_TTL_SECONDS
    if status_name in {"timeout", "offline", "error"}:
        return TRANSIENT_ERROR_TTL_SECONDS
    return TRANSIENT_ERROR_TTL_SECONDS


def _cooldown_for_error(error: str | None, status_name: str) -> float:
    if status_name in {"quota_exceeded", "rate_limited"}:
        return RATE_LIMIT_TTL_SECONDS
    if status_name in {"timeout", "offline"}:
        return TRANSIENT_ERROR_TTL_SECONDS
    return 0.0
