from __future__ import annotations

import json
import time
from typing import ClassVar
import urllib.request

from app.agent.providers.base import ModelResponse
from app.core.config import settings
from app.core.runtime import is_cloud


class OllamaProvider:
    name = "ollama"
    _last_status: ClassVar[dict | None] = None
    _last_checked: ClassVar[float] = 0.0
    _status_cache_seconds: ClassVar[float] = 15.0

    def is_configured(self) -> bool:
        if is_cloud():
            return False
        return bool(settings.ollama_enabled and settings.ollama_url and settings.ollama_model)

    def is_available(self) -> bool:
        if is_cloud():
            return False
        return bool(self.status().get("available"))

    def status(self) -> dict:
        if is_cloud():
            return {
                "name": self.name,
                "configured": False,
                "available": False,
                "online": False,
                "ollama_status": "disabled_in_cloud",
                "real_llm_enabled": False,
                "model": None,
                "selected_model": None,
                "models": [],
                "base_url": None,
                "base_url_configured": False,
                "last_error": "Ollama local bloqueado no runtime cloud.",
            }
        now = time.perf_counter()
        if self.__class__._last_status and now - self.__class__._last_checked < self.__class__._status_cache_seconds:
            return dict(self.__class__._last_status)

        configured = self.is_configured()
        available = False
        models: list[str] = []
        error = None
        if configured:
            try:
                with urllib.request.urlopen(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=settings.ollama_health_timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
                models = [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
                available = response.status == 200 and settings.ollama_model in models
                if not available:
                    error = f"Modelo {settings.ollama_model} nao encontrado em /api/tags."
            except Exception as exc:
                error = f"Ollama nao respondeu em /api/tags: {exc}"
                cached = self.__class__._last_status
                if cached and cached.get("available"):
                    stale_status = dict(cached)
                    stale_status["stale"] = True
                    stale_status["last_error"] = error
                    return stale_status
        else:
            error = "Ollama nao configurado."
        status = {
            "name": self.name,
            "configured": configured,
            "available": available,
            "online": available,
            "ollama_status": "online" if available else "offline",
            "real_llm_enabled": available,
            "model": settings.ollama_model,
            "selected_model": settings.ollama_model if available else None,
            "models": models,
            "base_url": settings.ollama_url,
            "base_url_configured": bool(settings.ollama_url),
            "last_error": None if available else error,
        }
        self.__class__._last_status = status
        self.__class__._last_checked = now
        return status

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        if is_cloud():
            return ModelResponse(
                text="Ollama local esta desativado no runtime cloud.",
                provider=self.name,
                model=settings.ollama_model,
                used_model=False,
                error_type="disabled_in_cloud",
            )
        payload = {
            "model": settings.ollama_model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        request = urllib.request.Request(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds or settings.ollama_chat_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            text = data.get("message", {}).get("content", "")
            return ModelResponse(text=text, provider=self.name, model=settings.ollama_model, used_model=True)
        except Exception as exc:
            return ModelResponse(text=f"Ollama indisponivel durante a chamada: {exc}", provider=self.name, model=settings.ollama_model, used_model=False, error_type="error")
