from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.agent.providers.base import ModelResponse
from app.agent.providers.provider_status_cache import STATUS_CACHE, classify_provider_error
from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings


class OpenAIResponsesProvider:
    name = "openai-responses"

    def is_configured(self) -> bool:
        return bool(settings.openai_enabled and settings.openai_api_key and settings.openai_model)

    def is_available(self) -> bool:
        return bool(self.status().get("available"))

    def status(self, *, force: bool = False) -> dict:
        configured = self.is_configured()
        if not configured:
            return {
                "name": self.name,
                "configured": False,
                "available": False,
                "online": False,
                "openai_status": "not_configured",
                "model": settings.openai_model,
                "selected_model": None,
                "base_url_configured": bool(settings.openai_base_url),
                "last_error": "OPENAI_API_KEY/OPENAI_MODEL nao configurado.",
                "last_error_sanitized": "OPENAI_API_KEY/OPENAI_MODEL nao configurado.",
            }
        cached = None if force else STATUS_CACHE.get_status(self.name)
        if cached:
            return cached
        response = self.chat(
            [{"role": "user", "content": "Responda apenas: ok"}],
            temperature=0.0,
            max_tokens=16,
            timeout_seconds=min(settings.openai_timeout_seconds, 6),
        )
        available = bool(response.used_model and response.text)
        status_name = "online" if available else classify_provider_error(response.text)
        status = {
            "name": self.name,
            "configured": configured,
            "available": available,
            "online": available,
            "openai_status": status_name or "offline",
            "model": settings.openai_model,
            "selected_model": response.model if available else None,
            "base_url_configured": bool(settings.openai_base_url),
            "last_error": None if available else response.text,
            "last_error_sanitized": None if available else mask_secrets(response.text),
        }
        return STATUS_CACHE.set_status(self.name, status, error=response.text if not available else None)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        if not self.is_configured():
            return ModelResponse(
                text="OpenAI Responses API nao configurada.",
                provider=self.name,
                model=settings.openai_model,
                used_model=False,
                error_type="not_configured",
            )

        instructions, input_text = _split_messages(messages)
        max_output_tokens = _normalize_max_output_tokens(max_tokens)
        timeout = float(timeout_seconds or settings.openai_timeout_seconds)
        last_error = ""
        last_error_type = "error"
        for model in _candidate_models():
            payload: dict[str, Any] = {
                "model": model,
                "input": input_text,
                "max_output_tokens": max_output_tokens,
                "store": False,
            }
            if instructions:
                payload["instructions"] = instructions
            if temperature is not None:
                payload["temperature"] = temperature

            request = urllib.request.Request(
                f"{settings.openai_base_url.rstrip('/')}/responses",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {settings.openai_api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    data = json.loads(response.read().decode("utf-8", errors="replace"))
                text = _extract_response_text(data)
                if not text:
                    error = f"OpenAI retornou resposta vazia. JSON bruto sanitizado: {mask_secrets(json.dumps(data, ensure_ascii=False)[:1200])}"
                    STATUS_CACHE.set_status(self.name, _status(False, "error", error), error=error)
                    return ModelResponse(text=error, provider=self.name, model=model, used_model=False, error_type="empty_response")
                STATUS_CACHE.set_status(self.name, _status(True, "online", None, selected_model=model))
                return ModelResponse(text=text, provider=self.name, model=model, used_model=True)
            except urllib.error.HTTPError as exc:
                error = _read_http_error(exc)
                error_type = classify_provider_error(error)
                last_error = error
                last_error_type = error_type
                if _is_model_not_found_error(error) and model != _candidate_models()[-1]:
                    continue
                STATUS_CACHE.set_status(self.name, _status(False, error_type, error), error=error)
                return ModelResponse(text=f"OpenAI Responses API indisponivel: {error}", provider=self.name, model=model, used_model=False, error_type=error_type)
            except Exception as exc:
                error = mask_secrets(str(exc))
                error_type = classify_provider_error(error)
                STATUS_CACHE.set_status(self.name, _status(False, error_type, error), error=error)
                return ModelResponse(text=f"OpenAI Responses API indisponivel: {error}", provider=self.name, model=model, used_model=False, error_type=error_type)

        STATUS_CACHE.set_status(self.name, _status(False, last_error_type, last_error), error=last_error)
        return ModelResponse(text=f"OpenAI Responses API indisponivel: {last_error}", provider=self.name, model=settings.openai_model, used_model=False, error_type=last_error_type)


def _status(available: bool, status_name: str, error: str | None, *, selected_model: str | None = None) -> dict:
    return {
        "name": "openai-responses",
        "configured": bool(settings.openai_enabled and settings.openai_api_key and settings.openai_model),
        "available": available,
        "online": available,
        "openai_status": status_name,
        "model": settings.openai_model,
        "selected_model": selected_model or (settings.openai_model if available else None),
        "base_url_configured": bool(settings.openai_base_url),
        "last_error": None if available else mask_secrets(error or ""),
        "last_error_sanitized": None if available else mask_secrets(error or ""),
    }


def _candidate_models() -> list[str]:
    candidates = [
        settings.openai_model,
        settings.openai_fallback_model,
        settings.openai_verifier_model,
        "gpt-5.4-mini",
        "gpt-4.1-mini",
        "gpt-4o-mini",
    ]
    unique: list[str] = []
    for model in candidates:
        model = (model or "").strip()
        if model and model not in unique:
            unique.append(model)
    return unique or [settings.openai_model]


def _is_model_not_found_error(error: str) -> bool:
    text = (error or "").lower()
    return "model" in text and ("does not exist" in text or "not found" in text)


def _normalize_max_output_tokens(max_tokens: int | None) -> int:
    try:
        configured = int(max_tokens or 0)
    except (TypeError, ValueError):
        configured = 0
    return max(16, configured)


def _split_messages(messages: list[dict[str, str]]) -> tuple[str, str]:
    instructions: list[str] = []
    turns: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role in {"system", "developer"}:
            instructions.append(content)
        else:
            turns.append(f"{role}: {content}")
    return "\n\n".join(instructions).strip(), "\n".join(turns).strip()


def _extract_response_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"]).strip()

    parts: list[str] = []
    for item in data.get("output", []) or []:
        if item.get("type") != "message" and "content" not in item:
            continue
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                text = content["text"]
                if isinstance(text, dict):
                    text = text.get("value", "")
                parts.append(str(text))
    return "\n".join(parts).strip()


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
    return mask_secrets(message)
