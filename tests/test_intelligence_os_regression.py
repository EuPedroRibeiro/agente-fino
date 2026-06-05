from __future__ import annotations

import unittest
from pathlib import Path

from app.agent.fusion.engine import FusionEngine
from app.agent.intelligence.permissions import PermissionLevel, permission_for_tool, requires_confirmation
from app.agent.intelligence.task_manager import list_tasks
from app.agent.providers.model_router import ModelRouter
from app.agent.security.sanitizer import mask_secrets
from app.routes import agent as agent_routes
from app.routes.status import read_health


class IntelligenceOSRegressionTests(unittest.TestCase):
    def test_health_is_security_preview(self) -> None:
        self.assertEqual(read_health()["version"], "2.1.1")

    def test_provider_status_has_selected_provider(self) -> None:
        status = ModelRouter().status()
        self.assertIn("selected_provider", status)

    def test_provider_status_has_openai_fields(self) -> None:
        status = ModelRouter().status()
        self.assertIn("openai_status", status)
        self.assertIn("openai_configured", status)

    def test_fusion_status_endpoint(self) -> None:
        status = agent_routes.agent_fusion_status()
        self.assertTrue(status["enabled"])

    def test_autonomy_status_is_safe(self) -> None:
        status = agent_routes.agent_autonomy_status()
        self.assertFalse(status["dangerous_actions_auto_execute"])

    def test_autonomy_update_clamps_level(self) -> None:
        status = agent_routes.agent_autonomy_update({"enabled": True, "level": 99})
        self.assertEqual(status["level"], 5)

    def test_task_create_and_list(self) -> None:
        created = agent_routes.agent_task_create({"title": "Verificar Gemini"})
        self.assertEqual(created["status"], "planned")
        self.assertTrue(any(task["title"] == "Verificar Gemini" for task in list_tasks()))

    def test_feedback_save_endpoint(self) -> None:
        saved = agent_routes.agent_feedback({"message": "bom", "rating": "up"})
        self.assertTrue(saved["saved"])

    def test_learning_rule_masks_secret(self) -> None:
        saved = agent_routes.agent_learning_rule({"rule": "token: abcdefghijklmnopqrstuvwxyz123"})
        self.assertIn("***", saved["rule"])

    def test_memory_extract_masks_secret(self) -> None:
        result = agent_routes.agent_memory_extract({"text": "api_key=abcdefghijklmnopqrstuvwxyz123"})
        self.assertTrue(result["sensitive"])

    def test_memory_confirm_save_can_store_node(self) -> None:
        result = agent_routes.agent_memory_confirm_save({"confirm": True, "value": "Notebook Acer", "type": "device"})
        self.assertTrue(result["saved"])

    def test_memory_graph_search_endpoint(self) -> None:
        result = agent_routes.agent_memory_graph_search({"query": "Acer"})
        self.assertIn("nodes", result)

    def test_replay_hides_chain_of_thought(self) -> None:
        replay = agent_routes.agent_replay("msg-1")
        self.assertTrue(replay["chain_of_thought_hidden"])

    def test_lens_requires_confirmation(self) -> None:
        result = agent_routes.agent_lens_analyze({})
        self.assertTrue(result["requires_confirmation"])

    def test_lens_confirmed_returns_analysis(self) -> None:
        result = agent_routes.agent_lens_analyze({"confirmed": True})
        self.assertIn("analysis", result)

    def test_training_status_endpoint(self) -> None:
        result = agent_routes.agent_training_status()
        self.assertTrue(result["enabled"])

    def test_training_export_is_sanitized(self) -> None:
        result = agent_routes.agent_training_export({"instruction": "x"})
        self.assertTrue(result["sanitized"])

    def test_read_only_tool_does_not_require_confirmation(self) -> None:
        self.assertEqual(permission_for_tool("disk_usage"), PermissionLevel.READ_ONLY)
        self.assertFalse(requires_confirmation("disk_usage"))

    def test_blocked_tool_is_blocked(self) -> None:
        self.assertEqual(permission_for_tool("cmd"), PermissionLevel.BLOCKED)

    def test_mask_secrets_nested_payload(self) -> None:
        payload = {"token": "token: abcdefghijklmnopqrstuvwxyz123"}
        self.assertIn("***", mask_secrets(payload)["token"])

    def test_web_request_uses_balanced(self) -> None:
        decision = FusionEngine().choose_mode(intent="web_research", tools=["web_search"], web_needed=True)
        self.assertEqual(decision.mode, "BALANCED")

    def test_sensitive_request_uses_self_check(self) -> None:
        decision = FusionEngine().choose_mode(intent="safe_refusal", tools=[])
        self.assertEqual(decision.mode, "SELF_CHECK")

    def test_desktop_app_does_not_use_public_host(self) -> None:
        text = Path("desktop_app.py").read_text(encoding="utf-8")
        self.assertIn('HOST = "127.0.0.1"', text)
        self.assertNotIn('HOST = "0.0.0.0"', text)

    def test_release_script_uses_icon(self) -> None:
        text = Path("build_desktop_release.ps1").read_text(encoding="utf-8")
        self.assertIn('--icon "app/static/favicon.ico"', text)

    def test_gitignore_excludes_release_artifacts(self) -> None:
        text = Path(".gitignore").read_text(encoding="utf-8")
        for token in ["build/", "dist/", "data/*.db", "*.pyc"]:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_requirements_have_desktop_dependencies(self) -> None:
        text = Path("requirements-local.txt").read_text(encoding="utf-8")
        self.assertIn("pywebview", text)
        self.assertIn("pyinstaller", text)

    def test_favicon_ico_exists(self) -> None:
        self.assertTrue(Path("app/static/favicon.ico").exists())


if __name__ == "__main__":
    unittest.main()
