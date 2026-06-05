from __future__ import annotations

import json
from pathlib import Path

from app.agent.providers.gemini import GeminiProvider
from app.agent.providers.local_rules import LocalRulesProvider
from app.agent.providers.litellm import LiteLLMProvider
from app.agent.providers.ollama import OllamaProvider
from app.agent.providers.openai_responses import OpenAIResponsesProvider
from app.agent.providers.openai_compatible import OpenAICompatibleProvider
from app.agent.providers.provider_status_cache import STATUS_CACHE
from app.core.config import settings
from app.core.runtime import is_cloud


DEFAULT_FUSION_SETTINGS = {
    "fast_provider_order": ["openai", "gemini", "local_rules"],
    "balanced_provider_order": ["gemini", "openai", "local_rules"],
    "expert_provider_order": ["openai", "gemini", "local_rules"],
    "fast_path_enabled": True,
}


class ModelRouter:
    def __init__(self) -> None:
        self.gemini = GeminiProvider()
        self.ollama = OllamaProvider()
        self.openai_responses = OpenAIResponsesProvider()
        self.openai_compatible = OpenAICompatibleProvider()
        self.litellm = LiteLLMProvider()
        self.local_rules = LocalRulesProvider()

    def selected_provider(self):
        availability = self.availability()
        return self._select_provider(availability)

    def availability(self) -> dict:
        statuses = self.providers_status()
        return {
            "gemini_available": bool(statuses["gemini"].get("available")),
            "openai_responses_available": bool(statuses["openai_responses"].get("available")),
            "openai_compatible_available": bool(statuses["openai_compatible"].get("available")) and not is_cloud(),
            "ollama_available": bool(statuses["ollama"].get("available")) and not is_cloud(),
            "litellm_available": bool(statuses["litellm"].get("available")) and not is_cloud(),
            "local_rules_available": self.local_rules.is_available(),
        }

    def _select_provider(self, availability: dict):
        provider = settings.model_provider.lower()
        if provider == "gemini":
            if availability["gemini_available"]:
                return self.gemini
            if availability["openai_responses_available"]:
                return self.openai_responses
            if availability["ollama_available"] and not is_cloud():
                return self.ollama
            return self.local_rules
        if provider in {"openai", "openai-responses", "responses"}:
            if availability["openai_responses_available"]:
                return self.openai_responses
            if availability["gemini_available"]:
                return self.gemini
            return self.local_rules
        if provider in {"openai-compatible", "openrouter", "groq", "compat"}:
            return self.openai_compatible if availability["openai_compatible_available"] else self.local_rules
        if provider == "ollama":
            return self.ollama if availability["ollama_available"] else self.local_rules
        if provider in {"litellm", "litellm-proxy"}:
            return self.litellm if availability["litellm_available"] else self.local_rules
        if availability["gemini_available"]:
            return self.gemini
        if availability["openai_responses_available"]:
            return self.openai_responses
        if availability["openai_compatible_available"]:
            return self.openai_compatible
        if availability["ollama_available"] and not is_cloud():
            return self.ollama
        if availability["litellm_available"]:
            return self.litellm
        return self.local_rules

    def provider_chain(self, availability: dict | None = None) -> list:
        availability = availability or self.availability()
        provider = settings.model_provider.lower()
        chain = []
        if provider == "gemini":
            chain = [
                self.gemini if availability["gemini_available"] else None,
                self.openai_responses if availability["openai_responses_available"] else None,
                self.ollama if availability["ollama_available"] and not is_cloud() else None,
                self.local_rules,
            ]
        elif provider == "ollama":
            chain = [
                self.ollama if availability["ollama_available"] and not is_cloud() else None,
                self.local_rules,
            ]
        elif provider in {"openai", "openai-responses", "responses"}:
            chain = [
                self.openai_responses if availability["openai_responses_available"] else None,
                self.gemini if availability["gemini_available"] else None,
                self.ollama if availability["ollama_available"] and not is_cloud() else None,
                self.local_rules,
            ]
        elif provider in {"openai-compatible", "openrouter", "groq", "compat"}:
            chain = [
                self.openai_compatible if availability["openai_compatible_available"] else None,
                self.ollama if availability["ollama_available"] and not is_cloud() else None,
                self.local_rules,
            ]
        elif provider in {"litellm", "litellm-proxy"}:
            chain = [
                self.litellm if availability["litellm_available"] else None,
                self.ollama if availability["ollama_available"] and not is_cloud() else None,
                self.local_rules,
            ]
        else:
            chain = [
                self.gemini if availability["gemini_available"] else None,
                self.openai_responses if availability["openai_responses_available"] else None,
                self.openai_compatible if availability["openai_compatible_available"] else None,
                self.ollama if availability["ollama_available"] and not is_cloud() else None,
                self.litellm if availability["litellm_available"] else None,
                self.local_rules,
            ]
        return [item for index, item in enumerate(chain) if item and item not in chain[:index]]

    def provider_chain_for_mode(self, mode: str, *, direct: bool = False) -> list:
        mode_key = mode.lower()
        fusion_settings = load_fusion_settings()
        if mode_key == "fast":
            order = fusion_settings.get("fast_provider_order", DEFAULT_FUSION_SETTINGS["fast_provider_order"])
        elif mode_key == "expert":
            order = fusion_settings.get("expert_provider_order", DEFAULT_FUSION_SETTINGS["expert_provider_order"])
        else:
            order = fusion_settings.get("balanced_provider_order", DEFAULT_FUSION_SETTINGS["balanced_provider_order"])

        providers = []
        for name in order:
            provider = self._provider_by_name(name)
            if provider is None:
                continue
            if provider.name == "openai-responses" and mode_key == "fast" and not settings.openai_fast_enabled:
                continue
            if provider.name != "local-rules":
                configured = getattr(provider, "is_configured", lambda: True)()
                if not configured:
                    continue
                if direct and STATUS_CACHE.is_cooling_down(provider.name):
                    continue
                if direct and mode_key == "fast" and provider.name == "gemini":
                    cached = STATUS_CACHE.get_status(provider.name)
                    if not cached or not cached.get("available"):
                        continue
                if not direct and not provider.is_available():
                    continue
            if provider not in providers:
                providers.append(provider)
        if self.local_rules not in providers:
            providers.append(self.local_rules)
        return providers

    def _provider_by_name(self, name: str):
        normalized = name.replace("_", "-").lower()
        if is_cloud() and normalized in {"ollama", "litellm", "litellm-proxy", "openai-compatible", "openrouter", "groq", "compat"}:
            return None
        mapping = {
            "gemini": self.gemini,
            "openai": self.openai_responses,
            "openai-responses": self.openai_responses,
            "responses": self.openai_responses,
            "openai-compatible": self.openai_compatible,
            "ollama": self.ollama,
            "litellm": self.litellm,
            "litellm-proxy": self.litellm,
            "local-rules": self.local_rules,
            "local": self.local_rules,
        }
        return mapping.get(normalized)

    def status(self) -> dict:
        availability = self.availability()
        selected = self._select_provider(availability)
        provider_statuses = self.providers_status()
        selected_model = _selected_model(selected.name, provider_statuses)
        fallback_reason = _fallback_reason(selected.name, provider_statuses, availability)
        return {
            "selected": selected.name,
            "selected_provider": selected.name,
            "selected_model": selected_model,
            "real_llm_enabled": selected.name != "local-rules",
            "fallback_reason": fallback_reason,
            "runtime": "cloud" if is_cloud() else "local_legacy",
            "selection_order": ["gemini", "openai-responses", "local-rules"] if is_cloud() else ["gemini", "ollama", "openai-responses", "openai-compatible", "litellm", "local-rules"],
            "gemini_configured": provider_statuses["gemini"].get("configured", False),
            "gemini_status": provider_statuses["gemini"].get("gemini_status"),
            "gemini_model": provider_statuses["gemini"].get("model"),
            "ollama_status": provider_statuses["ollama"].get("ollama_status"),
            "ollama_model": provider_statuses["ollama"].get("model"),
            "openai_configured": provider_statuses["openai_responses"].get("configured", False),
            "openai_status": provider_statuses["openai_responses"].get("openai_status", "not_configured"),
            "openai_model": provider_statuses["openai_responses"].get("model", ""),
            "openai_available": provider_statuses["openai_responses"].get("available", False),
            "openai_last_error_sanitized": provider_statuses["openai_responses"].get("last_error"),
            **availability,
            "providers": provider_statuses,
        }

    def providers_status(self) -> dict:
        if is_cloud():
            ollama_status = {
                "name": "ollama",
                "configured": False,
                "available": False,
                "online": False,
                "ollama_status": "disabled_in_cloud",
                "model": None,
                "last_error": "Provider local bloqueado no runtime cloud.",
            }
            litellm_status = {
                "name": "litellm",
                "configured": False,
                "available": False,
                "status": "disabled_in_cloud",
                "model": None,
                "last_error": "Provider local/proxy bloqueado no runtime cloud preview.",
            }
        else:
            ollama_status = self._cached_status(self.ollama)
            litellm_status = self.litellm.status()
        return {
            "gemini": self._cached_status(self.gemini),
            "openai_responses": self._cached_status(self.openai_responses),
            "openai_compatible": {"name": "openai-compatible", "configured": False, "available": False, "status": "disabled_in_cloud", "last_error": "Compat providers bloqueados no cloud preview."} if is_cloud() else self.openai_compatible.status(),
            "ollama": ollama_status,
            "litellm": litellm_status,
            "local_rules": {
                "name": "local-rules",
                "configured": True,
                "available": self.local_rules.is_available(),
                "model": "deterministic-rules",
                "last_error": None,
            },
        }

    def _cached_status(self, provider) -> dict:
        cached = STATUS_CACHE.get_status(provider.name)
        if cached:
            return cached
        status = provider.status()
        if provider.name in {"gemini", "ollama", "openai-responses"}:
            return STATUS_CACHE.set_status(provider.name, status, error=status.get("last_error"))
        return status

    def retest_gemini(self) -> dict:
        gemini_status = self.gemini.status(force=True)
        provider_statuses = self.providers_status()
        provider_statuses["gemini"] = gemini_status
        availability = self.availability()
        availability["gemini_available"] = bool(gemini_status.get("available"))
        selected = self._select_provider(availability)
        fallback_reason = None if selected.name == "gemini" else (gemini_status.get("last_error") or "Gemini indisponivel.")
        return {
            "gemini_status": gemini_status.get("gemini_status"),
            "gemini_available": bool(gemini_status.get("available")),
            "gemini_model": gemini_status.get("model"),
            "selected_provider": selected.name,
            "selected_model": _selected_model(selected.name, provider_statuses),
            "real_llm_enabled": selected.name != "local-rules",
            "fallback_reason": fallback_reason,
            "ollama_status": provider_statuses["ollama"].get("ollama_status"),
            "ollama_model": provider_statuses["ollama"].get("model"),
        }

    def retest_openai(self) -> dict:
        STATUS_CACHE.clear(self.openai_responses.name)
        openai_status = self.openai_responses.status(force=True)
        provider_statuses = self.providers_status()
        provider_statuses["openai_responses"] = openai_status
        availability = self.availability()
        availability["openai_responses_available"] = bool(openai_status.get("available"))
        selected = self._select_provider(availability)
        return {
            "openai_status": openai_status.get("openai_status"),
            "openai_available": bool(openai_status.get("available")),
            "openai_model": openai_status.get("model"),
            "selected_provider": selected.name,
            "selected_model": _selected_model(selected.name, provider_statuses),
            "real_llm_enabled": selected.name != "local-rules",
            "fallback_reason": None if selected.name == "openai-responses" else openai_status.get("last_error_sanitized"),
        }


def _selected_model(provider_name: str, provider_statuses: dict) -> str:
    if provider_name == "local-rules":
        return "deterministic-rules"
    status = provider_statuses.get(provider_name.replace("-", "_"), {})
    return status.get("selected_model") or status.get("model") or ""


def _fallback_reason(provider_name: str, provider_statuses: dict, availability: dict) -> str | None:
    if provider_name == "gemini":
        return None
    gemini_status = provider_statuses.get("gemini", {})
    gemini_configured = bool(gemini_status.get("configured", False))
    if gemini_configured and not availability.get("gemini_available"):
        return gemini_status.get("last_error") or gemini_status.get("last_error_sanitized") or "Gemini indisponivel."
    if not gemini_configured and provider_name != "gemini":
        return "Chave Gemini nao configurada."
    return None


def load_fusion_settings() -> dict:
    path = Path("data/fusion_settings.json")
    if not path.exists():
        return dict(DEFAULT_FUSION_SETTINGS)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_FUSION_SETTINGS)
    merged = dict(DEFAULT_FUSION_SETTINGS)
    merged.update({key: value for key, value in loaded.items() if value is not None})
    return merged
