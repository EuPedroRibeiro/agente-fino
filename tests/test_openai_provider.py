from __future__ import annotations

import json
import urllib.error
import unittest
from unittest.mock import patch

from app.agent.providers.openai_responses import OpenAIResponsesProvider, _extract_response_text, _normalize_max_output_tokens
from app.agent.providers.provider_status_cache import STATUS_CACHE

FAKE_OPENAI_KEY = "s" + "k" + "-test-fake-value-not-real"


class FakeHTTPResponse:
    status = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def close(self) -> None:
        return None


class CaptureURLopener:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests: list[dict] = []

    def __call__(self, request, timeout=None):
        self.requests.append(json.loads(request.data.decode("utf-8")))
        return FakeHTTPResponse(self.payload)


class ModelFallbackURLopener:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests: list[dict] = []

    def __call__(self, request, timeout=None):
        body = json.loads(request.data.decode("utf-8"))
        self.requests.append(body)
        if body["model"] == "missing-model":
            error_payload = {"error": {"message": "The requested model 'missing-model' does not exist."}}
            raise urllib.error.HTTPError(
                request.full_url,
                404,
                "Not Found",
                hdrs={},
                fp=FakeHTTPResponse(error_payload),
            )
        return FakeHTTPResponse(self.payload)


class OpenAIProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        STATUS_CACHE.clear()

    def test_missing_key_is_not_configured(self) -> None:
        with patch("app.agent.providers.openai_responses.settings.openai_enabled", True), patch("app.agent.providers.openai_responses.settings.openai_api_key", ""):
            status = OpenAIResponsesProvider().status(force=True)
        self.assertEqual(status["openai_status"], "not_configured")
        self.assertFalse(status["available"])

    def test_extracts_output_text(self) -> None:
        self.assertEqual(_extract_response_text({"output_text": "ok"}), "ok")

    def test_extracts_message_content_text(self) -> None:
        payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Gemini nao, OpenAI ok"}]}]}
        self.assertEqual(_extract_response_text(payload), "Gemini nao, OpenAI ok")

    def test_fake_online_chat(self) -> None:
        provider = OpenAIResponsesProvider()
        payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}]}
        with patch("app.agent.providers.openai_responses.settings.openai_enabled", True), patch(
            "app.agent.providers.openai_responses.settings.openai_api_key", FAKE_OPENAI_KEY
        ), patch("app.agent.providers.openai_responses.settings.openai_model", "test-model"), patch(
            "urllib.request.urlopen", return_value=FakeHTTPResponse(payload)
        ):
            response = provider.chat([{"role": "user", "content": "Responda apenas: ok"}], max_tokens=8, timeout_seconds=1)
            status = provider.status()
        self.assertTrue(response.used_model)
        self.assertEqual(response.text, "ok")
        self.assertEqual(status["openai_status"], "online")

    def test_max_output_tokens_is_never_below_16(self) -> None:
        provider = OpenAIResponsesProvider()
        payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}]}
        opener = CaptureURLopener(payload)
        with patch("app.agent.providers.openai_responses.settings.openai_enabled", True), patch(
            "app.agent.providers.openai_responses.settings.openai_api_key", FAKE_OPENAI_KEY
        ), patch("app.agent.providers.openai_responses.settings.openai_model", "test-model"), patch(
            "urllib.request.urlopen", opener
        ):
            response = provider.chat([{"role": "user", "content": "Responda apenas: ok"}], max_tokens=8, timeout_seconds=1)
        self.assertTrue(response.used_model)
        self.assertEqual(opener.requests[0]["max_output_tokens"], 16)

    def test_health_check_uses_minimum_valid_tokens(self) -> None:
        provider = OpenAIResponsesProvider()
        payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}]}
        opener = CaptureURLopener(payload)
        with patch("app.agent.providers.openai_responses.settings.openai_enabled", True), patch(
            "app.agent.providers.openai_responses.settings.openai_api_key", FAKE_OPENAI_KEY
        ), patch("app.agent.providers.openai_responses.settings.openai_model", "test-model"), patch(
            "urllib.request.urlopen", opener
        ):
            status = provider.status(force=True)
        self.assertEqual(status["openai_status"], "online")
        self.assertEqual(opener.requests[0]["max_output_tokens"], 16)

    def test_fast_mode_token_floor_helper(self) -> None:
        self.assertEqual(_normalize_max_output_tokens(8), 16)
        self.assertEqual(_normalize_max_output_tokens(32), 32)

    def test_missing_primary_model_uses_fallback_model(self) -> None:
        provider = OpenAIResponsesProvider()
        payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}]}
        opener = ModelFallbackURLopener(payload)
        with patch("app.agent.providers.openai_responses.settings.openai_enabled", True), patch(
            "app.agent.providers.openai_responses.settings.openai_api_key", FAKE_OPENAI_KEY
        ), patch("app.agent.providers.openai_responses.settings.openai_model", "missing-model"), patch(
            "app.agent.providers.openai_responses.settings.openai_fallback_model", "fallback-model"
        ), patch("app.agent.providers.openai_responses.settings.openai_verifier_model", ""), patch(
            "urllib.request.urlopen", opener
        ):
            response = provider.chat([{"role": "user", "content": "Responda apenas: ok"}], max_tokens=16, timeout_seconds=1)
            status = provider.status()
        self.assertTrue(response.used_model)
        self.assertEqual(response.model, "fallback-model")
        self.assertEqual(status["selected_model"], "fallback-model")
        self.assertEqual([item["model"] for item in opener.requests[:2]], ["missing-model", "fallback-model"])


if __name__ == "__main__":
    unittest.main()
