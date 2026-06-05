from __future__ import annotations

import json
import time
from typing import Any, ClassVar
import urllib.error
import urllib.request

from app.agent.providers.base import ModelResponse
from app.core.config import settings


class GeminiProvider:
    name = "gemini"
    _last_status: ClassVar[dict | None] = None
    _last_checked: ClassVar[float] = 0.0

    def is_configured(self) -> bool:
        return bool(settings.gemini_api_key and settings.gemini_model)

    def is_available(self) -> bool:
        return bool(self.status().get("available"))

    def status(self, *, force: bool = False) -> dict:
        now = time.perf_counter()
        if not force and self.__class__._last_status and now - self.__class__._last_checked < settings.gemini_status_cache_seconds:
            return dict(self.__class__._last_status)

        configured = self.is_configured()
        available = False
        error = None
        if configured:
            response = self.chat(
                [
                    {"role": "user", "content": "Responda apenas: ok"},
                ],
                temperature=0.0,
                max_tokens=16,
                timeout_seconds=min(settings.gemini_timeout_seconds, 6),
            )
            available = response.used_model
            error = None if available else response.text
        else:
            error = "Chave Gemini nao configurada."

        status_name = "online" if available else ("offline" if configured else "not_configured")
        if error and "quota" in error.lower():
            status_name = "quota_exceeded"

        status = {
            "name": self.name,
            "configured": configured,
            "available": available,
            "online": available,
            "gemini_status": status_name,
            "real_llm_enabled": available,
            "model": settings.gemini_model,
            "selected_model": settings.gemini_model if available else None,
            "api_key_configured": configured,
            "base_url_configured": bool(settings.gemini_base_url),
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
        if not self.is_configured():
            return ModelResponse(text="Gemini nao configurado: chave ausente.", provider=self.name, model=settings.gemini_model, used_model=False)

        payload = _to_gemini_payload(messages, temperature=temperature, max_tokens=max_tokens)
        request = urllib.request.Request(
            _generate_content_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": settings.gemini_api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds or settings.gemini_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            text = _extract_text(data)
            if not text:
                return ModelResponse(
                    text=f"Gemini retornou resposta vazia. JSON bruto: {_sanitize_error(json.dumps(data, ensure_ascii=False)[:1500])}",
                    provider=self.name,
                    model=settings.gemini_model,
                    used_model=False,
                    error_type="empty_response",
                )
            return ModelResponse(text=text, provider=self.name, model=settings.gemini_model, used_model=True)
        except urllib.error.HTTPError as exc:
            error_text = _read_http_error(exc)
            return ModelResponse(text=f"Gemini indisponivel: {error_text}", provider=self.name, model=settings.gemini_model, used_model=False, error_type="error")
        except Exception as exc:
            return ModelResponse(text=f"Gemini indisponivel: {_sanitize_error(str(exc))}", provider=self.name, model=settings.gemini_model, used_model=False, error_type="error")


def _generate_content_url() -> str:
    return f"{settings.gemini_base_url.rstrip('/')}/models/{settings.gemini_model}:generateContent"


def _to_gemini_payload(messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> dict[str, Any]:
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": _merge_messages(messages),
                    }
                ],
            }
        ]
    }


def _extract_text(data: dict[str, Any]) -> str:
    try:
        return str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _merge_messages(messages: list[dict[str, str]]) -> str:
    sections: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role in {"system", "developer"}:
            label = "SYSTEM PROMPT"
        elif role in {"assistant", "model"}:
            label = "HISTORICO DO ASSISTENTE"
        else:
            label = "USUARIO"
        sections.append(f"{label}:\n{content}")
    return "\n\n".join(sections)


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
        payload = json.loads(body)
        message = payload.get("error", {}).get("message") or body
    except Exception:
        message = str(exc)
    finally:
        try:
            exc.close()
        except Exception:
            pass
    return _sanitize_error(message)


def _sanitize_error(text: str) -> str:
    sanitized = text
    if settings.gemini_api_key:
        sanitized = sanitized.replace(settings.gemini_api_key, "[GEMINI_API_KEY]")
    return sanitized
