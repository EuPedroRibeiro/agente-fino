from __future__ import annotations

from app.agent.memory_stores.sqlite_memory import get_cached_web_result, save_cached_web_result
from app.core.config import settings


class WebResearchCache:
    def get(self, query: str) -> dict | None:
        if not settings.web_cache_enabled:
            return None
        return get_cached_web_result(query)

    def set(self, query: str, results: list[dict], sources: list[dict]) -> None:
        if not settings.web_cache_enabled:
            return
        save_cached_web_result(query, results, sources, settings.web_cache_ttl_minutes)
