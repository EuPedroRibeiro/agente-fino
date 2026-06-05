from __future__ import annotations

import functools
import hashlib
import json
import threading
import time
from typing import Any, Callable

from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.security.documents import sanitize_document_payload


_MEMORY_CACHE: dict[str, tuple[float, Any]] = {}
_MEMORY_LOCK = threading.Lock()


def hashed_cache_key(namespace: str, identifier: str) -> str:
    digest = hashlib.sha256(f"{namespace}:{identifier}".encode("utf-8")).hexdigest()
    return f"consulta:{namespace}:{digest}"


class ConsultaCache:
    def __init__(self, *, enabled: bool | None = None, redis_url: str | None = None) -> None:
        self.enabled = settings.consulta_cache_enabled if enabled is None else enabled
        self.redis_url = settings.redis_url if redis_url is None else redis_url
        self._redis = self._connect_redis()

    def _connect_redis(self):
        if not self.enabled or not self.redis_url:
            return None
        try:
            import redis

            client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
            )
            client.ping()
            return client
        except Exception:
            return None

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "backend": "redis" if self._redis is not None else "memory",
            "redis_configured": bool(self.redis_url),
            "redis_available": self._redis is not None,
            "raw_documents_in_keys": False,
        }

    def get(self, namespace: str, identifier: str) -> tuple[Any | None, bool]:
        if not self.enabled:
            return None, False
        key = hashed_cache_key(namespace, identifier)
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                return (json.loads(raw), True) if raw else (None, False)
            except Exception:
                pass
        now = time.time()
        with _MEMORY_LOCK:
            item = _MEMORY_CACHE.get(key)
            if not item:
                return None, False
            expires_at, value = item
            if expires_at <= now:
                _MEMORY_CACHE.pop(key, None)
                return None, False
            return value, True

    def set(self, namespace: str, identifier: str, value: Any, *, ttl_seconds: int) -> None:
        if not self.enabled:
            return
        key = hashed_cache_key(namespace, identifier)
        safe_value = mask_secrets(sanitize_document_payload(value))
        if self._redis is not None:
            try:
                self._redis.setex(key, max(1, ttl_seconds), json.dumps(safe_value, ensure_ascii=False, default=str))
                return
            except Exception:
                pass
        with _MEMORY_LOCK:
            _MEMORY_CACHE[key] = (time.time() + max(1, ttl_seconds), safe_value)


consulta_cache = ConsultaCache()


def cached_consulta(*, namespace: str, ttl_seconds: int) -> Callable:
    def decorator(function: Callable) -> Callable:
        @functools.wraps(function)
        def wrapper(identifier: str, *args, **kwargs):
            cached, hit = consulta_cache.get(namespace, identifier)
            if hit:
                return cached
            value = function(identifier, *args, **kwargs)
            consulta_cache.set(namespace, identifier, value, ttl_seconds=ttl_seconds)
            return value

        return wrapper

    return decorator
