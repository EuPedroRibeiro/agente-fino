import tempfile
import unittest
from pathlib import Path

from app.agent.schemas.messages import AgentChatRequest
from app.routes.agent import _darkforest_redirect_response, _is_darkforest_command
from modules.darkforest.parser import find_secrets, mask_secret
from modules.darkforest.service import DarkForestService
from modules.darkforest.safety import DarkForestConfig


RAW_OPENAI_KEY = "sk-proj-" + "A" * 32 + "xP9z"
RAW_DEEPSEEK_KEY = "sk-" + "D" * 36
RAW_OPENROUTER_KEY = "sk-or-v1-" + "R" * 36


class DarkForestModuleTests(unittest.TestCase):
    def test_mask_secret_keeps_only_safe_edges(self):
        masked = mask_secret(RAW_OPENAI_KEY)
        self.assertTrue(masked.startswith("sk-proj-"))
        self.assertTrue(masked.endswith("xP9z"))
        self.assertNotIn("A" * 20, masked)

    def test_scan_requires_sensitive_authorization(self):
        service = DarkForestService(DarkForestConfig(True, "./tools/DarkForest-Hunter-OpenAI", 10, True, False))
        with self.assertRaises(PermissionError):
            service.scan(target="API_KEY=" + RAW_OPENAI_KEY, accepted_notice=False, confirmed_authorization=True)

    def test_scan_text_masks_findings_and_does_not_return_raw_secret(self):
        service = DarkForestService(DarkForestConfig(True, "./tools/DarkForest-Hunter-OpenAI", 10, True, False))
        report = service.scan(
            target="OPENAI_API_KEY=" + RAW_OPENAI_KEY,
            accepted_notice=True,
            confirmed_authorization=True,
        )
        rendered = str(report)
        self.assertEqual(report["findings_count"], 1)
        self.assertEqual(report["risk_level"], "critical")
        self.assertIn("OpenAI API Key", rendered)
        self.assertNotIn(RAW_OPENAI_KEY, rendered)

    def test_provider_specific_patterns_are_classified_and_masked(self):
        text = "\n".join(
            [
                "OPENAI_API_KEY=" + RAW_OPENAI_KEY,
                "DEEPSEEK_API_KEY=" + RAW_DEEPSEEK_KEY,
                "OPENROUTER_API_KEY=" + RAW_OPENROUTER_KEY,
            ]
        )
        findings = find_secrets(text, source="inline")
        rendered = str(findings)
        types = {finding["type"] for finding in findings}
        self.assertIn("OpenAI API Key", types)
        self.assertIn("DeepSeek API Key", types)
        self.assertIn("OpenRouter API Key", types)
        self.assertNotIn(RAW_OPENAI_KEY, rendered)
        self.assertNotIn(RAW_DEEPSEEK_KEY, rendered)
        self.assertNotIn(RAW_OPENROUTER_KEY, rendered)

    def test_scan_local_folder_finds_secret_without_saving_raw_value(self):
        service = DarkForestService(DarkForestConfig(True, "./tools/DarkForest-Hunter-OpenAI", 10, True, False))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("OPENAI_API_KEY=" + RAW_OPENAI_KEY, encoding="utf-8")
            report = service.scan(target=tmp, accepted_notice=True, confirmed_authorization=True)
        self.assertEqual(report["findings_count"], 1)
        self.assertNotIn(RAW_OPENAI_KEY, str(report))

    def test_darkforest_page_and_static_assets_exist(self):
        html = Path("app/templates/darkforest.html").read_text(encoding="utf-8")
        css = Path("app/static/css/darkforest.css").read_text(encoding="utf-8")
        js = Path("app/static/js/darkforest.js").read_text(encoding="utf-8")
        self.assertIn("Conteudo sensivel", html)
        self.assertIn("Confirmo que tenho autorizacao", html)
        self.assertIn("/api/security/darkforest/scan", js)
        self.assertIn("sensitive-overlay", css)
        self.assertNotIn(RAW_OPENAI_KEY, html + css + js)

    def test_agent_has_darkforest_button_and_local_redirect_command(self):
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        self.assertIn("darkforestBtn", html)
        self.assertIn("securityShortcutBtn", html)
        self.assertIn("Segurança", html)
        self.assertIn("Scanner de chaves", html)
        self.assertIn("isDarkForestCommand", js)
        self.assertIn("securityShortcutBtn", js)
        self.assertIn('window.location.href = "/security"', js)

    def test_env_example_has_darkforest_flags(self):
        env = Path(".env.example").read_text(encoding="utf-8")
        self.assertIn("DARKFOREST_ENABLED=true", env)
        self.assertIn("DARKFOREST_MASK_SECRETS=true", env)
        self.assertIn("DARKFOREST_SAVE_HISTORY=true", env)

    def test_external_darkforest_repository_is_isolated_from_production(self):
        self.assertFalse(Path("tools/DarkForest-Hunter-OpenAI").exists())
        self.assertTrue(Path("modules/darkforest").exists())

    def test_security_page_is_protected_by_auth_middleware(self):
        from app.security.access import is_protected_path

        self.assertTrue(is_protected_path("/security"))
        self.assertTrue(is_protected_path("/darkforest"))
        self.assertTrue(is_protected_path("/scanner"))

    def test_chat_command_returns_safe_redirect_payload(self):
        request = AgentChatRequest(message="Agente Fino, abrir scanner de vazamento")
        self.assertTrue(_is_darkforest_command(request.message))
        response = _darkforest_redirect_response(request)
        self.assertEqual(response.intent, "darkforest_scanner")
        self.assertEqual(response.mode, "SAFE_REDIRECT")
        self.assertEqual(response.model_used["redirect_url"], "/security")


if __name__ == "__main__":
    unittest.main()
