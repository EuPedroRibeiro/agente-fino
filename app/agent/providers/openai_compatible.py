from __future__ import annotations

import json
import urllib.request

from app.agent.providers.base import ModelResponse
from app.agent.providers.provider_status_cache import STATUS_CACHE, classify_provider_error
from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def is_configured(self) -> bool:
        return bool(
            settings.openai_compat_enabled
            and settings.openai_compat_base_url
            and settings.openai_compat_api_key
            and settings.openai_compat_model
        )

    def is_available(self) -> bool:
        return bool(self.status().get("available"))

    def status(self, *, force: bool = False) -> dict:
        configured = self.is_configured()
        if not configured:
            return _compat_status(False, "not_configured", "NEXUSTI_OPENAI_COMPAT_* nao configurado.")
        cached = None if force else STATUS_CACHE.get_status(self.name)
        if cached:
            return cached
        response = self.chat(
            [{"role": "user", "content": "Responda apenas: ok"}],
            temperature=0.0,
            max_tokens=16,
            timeout_seconds=6,
        )
        available = bool(response.used_model and response.text)
        status_name = "online" if available else classify_provider_error(response.text)
        return STATUS_CACHE.set_status(
            self.name,
            _compat_status(available, status_name or "offline", None if available else response.text),
            error=None if available else response.text,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        if not self.is_configured():
            return ModelResponse(text="Provider OpenAI-compatible nao configurado.", provider=self.name, model=settings.openai_compat_model, used_model=False)
        payload = {
            "model": settings.openai_compat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request = urllib.request.Request(
            f"{settings.openai_compat_base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {settings.openai_compat_api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds or 12) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return ModelResponse(text=text, provider=self.name, model=settings.openai_compat_model, used_model=bool(text))
        except Exception as exc:
            return ModelResponse(text=f"Provider compativel indisponivel: {mask_secrets(str(exc))}", provider=self.name, model=settings.openai_compat_model, used_model=False)

    def _legacy_is_available(self) -> bool:
        return bool(
            settings.openai_compat_enabled
            and settings.openai_compat_base_url
            and settings.openai_compat_api_key
            and settings.openai_compat_model
        )


def _compat_status(available: bool, status_name: str, error: str | None) -> dict:
    return {
        "name": "openai-compatible",
        "configured": bool(
            settings.openai_compat_enabled
            and settings.openai_compat_base_url
            and settings.openai_compat_api_key
            and settings.openai_compat_model
        ),
        "available": available,
        "online": available,
        "status": status_name,
        "model": settings.openai_compat_model,
        "base_url_configured": bool(settings.openai_compat_base_url),
        "last_error": None if available else mask_secrets(error or ""),
        "last_error_sanitized": None if available else mask_secrets(error or ""),
    }
