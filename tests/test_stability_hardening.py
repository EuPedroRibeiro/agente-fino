from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Response

from app.core.auth import create_local_session, validate_token
from app.routes import actions as action_routes
from app.agent.providers.openai_compatible import OpenAICompatibleProvider
from app.agent.providers.litellm import LiteLLMProvider

FAKE_OPENAI_COMPAT_KEY = "s" + "k" + "-test-fake-value-not-real"


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class StabilityHardeningTests(unittest.TestCase):
    def test_local_session_token_validates(self) -> None:
        response = Response()
        payload = create_local_session(response)
        cookie_header = response.headers["set-cookie"]
        token = cookie_header.split("agente_fino_session=", 1)[1].split(";", 1)[0]
        self.assertTrue(payload["authenticated"])
        self.assertTrue(validate_token(token))
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=lax", cookie_header)

    def test_clean_temp_requires_confirmation_before_service_call(self) -> None:
        with (
            patch("app.routes.actions.is_cloud", return_value=False),
            patch("app.routes.actions.clean_temp_files") as clean_temp,
        ):
            response = action_routes.clean_temp({"confirm": False})
        clean_temp.assert_not_called()
        self.assertEqual(response["status"], "needs_confirmation")
        self.assertTrue(response["requires_confirmation"])

    def test_clean_temp_runs_after_confirmation(self) -> None:
        expected = {"status": "success", "action": "clean-temp"}
        with (
            patch("app.routes.actions.is_cloud", return_value=False),
            patch("app.routes.actions.clean_temp_files", return_value=expected) as clean_temp,
        ):
            response = action_routes.clean_temp({"confirm": True})
        clean_temp.assert_called_once()
        self.assertEqual(response, expected)

    def test_spooler_requires_confirmation_before_service_call(self) -> None:
        with (
            patch("app.routes.actions.is_cloud", return_value=False),
            patch("app.routes.actions.restart_spooler") as restart,
        ):
            response = action_routes.restart_print_spooler({"confirm": False})
        restart.assert_not_called()
        self.assertEqual(response["status"], "needs_confirmation")
        self.assertEqual(response["risk_level"], "medium")

    def test_openai_compatible_status_uses_health_check(self) -> None:
        payload = {"choices": [{"message": {"content": "ok"}}]}
        with (
            patch("app.agent.providers.openai_compatible.settings.openai_compat_enabled", True),
            patch("app.agent.providers.openai_compatible.settings.openai_compat_base_url", "http://example.test"),
            patch("app.agent.providers.openai_compatible.settings.openai_compat_api_key", FAKE_OPENAI_COMPAT_KEY),
            patch("app.agent.providers.openai_compatible.settings.openai_compat_model", "test-model"),
            patch("urllib.request.urlopen", return_value=FakeHTTPResponse(payload)),
        ):
            status = OpenAICompatibleProvider().status(force=True)
        self.assertTrue(status["available"])
        self.assertEqual(status["status"], "online")

    def test_litellm_status_uses_health_check(self) -> None:
        payload = {"choices": [{"message": {"content": "ok"}}]}
        with (
            patch("app.agent.providers.litellm.settings.litellm_base_url", "http://example.test"),
            patch("app.agent.providers.litellm.settings.litellm_model", "test-model"),
            patch("urllib.request.urlopen", return_value=FakeHTTPResponse(payload)),
        ):
            status = LiteLLMProvider().status(force=True)
        self.assertTrue(status["available"])
        self.assertEqual(status["litellm_status"], "online")

    def test_clean_package_script_targets_release_garbage(self) -> None:
        script = Path("tools/clean_package.ps1").read_text(encoding="utf-8")
        self.assertIn("__pycache__", script)
        self.assertIn("*.pyc", script)
        self.assertIn("data\\*.db", script)
        self.assertIn("StartsWith($ProjectRoot.Path", script)


if __name__ == "__main__":
    unittest.main()
