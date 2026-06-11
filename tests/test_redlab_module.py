from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.redlab.engine import RedLabEngine
from app.redlab.labs import LABS, LABS_BY_ID
from app.redlab.models import RankName
from app.redlab.scoring import xp_to_rank
from app.redlab.store import RedLabStore
from app.redlab.target_engine import RedLabTargetEngine, TargetConfig
from app.security.access import is_protected_path


class RedLabModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RedLabEngine(run_store=RedLabStore(), target_engine=RedLabTargetEngine(TargetConfig(False, (), False)))

    def test_six_isolated_labs_exist(self) -> None:
        self.assertEqual(len(LABS), 6)
        self.assertEqual(
            set(LABS_BY_ID),
            {"login_weak", "idor_panel", "upload_guard", "xss_comments", "sql_training", "exposed_admin"},
        )

    def test_lab_run_validation_patch_report_and_progress(self) -> None:
        started = self.engine.start("pedro", "sql_training")
        run_id = started["run"]["id"]
        result = self.engine.validate_lab("pedro", run_id, "sql_training", "' OR 1=1--")
        self.assertTrue(result["result"]["vulnerability_found"])
        self.assertGreater(result["progress"]["total_xp"], 0)
        patched = self.engine.patch("pedro", run_id, "sql_training")
        self.assertTrue(patched["patch"]["patch_applied"])
        self.assertEqual(patched["patch"]["tests_passed"], patched["patch"]["tests_total"])
        report = self.engine.report("pedro", run_id)
        self.assertEqual(report["run"]["id"], run_id)

    def test_payload_is_only_matched_inside_simulation(self) -> None:
        started = self.engine.start("pedro", "xss_comments")
        result = self.engine.validate_lab("pedro", started["run"]["id"], "xss_comments", "<script>alert(1)</script>")
        self.assertTrue(result["result"]["vulnerability_found"])
        self.assertIn("simulacao", result["result"]["response_summary"].lower())

    def test_rank_progression(self) -> None:
        self.assertEqual(xp_to_rank(0), RankName.RECRUTA)
        self.assertEqual(xp_to_rank(100), RankName.ANALISTA)
        self.assertEqual(xp_to_rank(3000), RankName.FINO_SPECTER)

    def test_target_mode_is_disabled_by_default_and_requires_allowlist(self) -> None:
        target = RedLabTargetEngine(TargetConfig(False, (), False))
        valid, message, _host = target.validate_target("https://example.com", True)
        self.assertFalse(valid)
        self.assertIn("desativado", message)
        target = RedLabTargetEngine(TargetConfig(True, ("example.com",), False))
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            valid, _message, host = target.validate_target("https://example.com/test", True)
        self.assertTrue(valid)
        self.assertEqual(host, "example.com")

    def test_target_preflight_never_contains_exploit_payloads(self) -> None:
        target = RedLabTargetEngine(TargetConfig(True, ("example.com",), False))
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            results = target.scan("https://example.com", ["sqli", "xss"], True)
        rendered = str([item.model_dump() for item in results]).lower()
        self.assertIn("nenhum payload foi disparado", rendered)
        self.assertNotIn("union select", rendered)
        self.assertNotIn("<script", rendered)

    def test_page_assets_routes_and_auth_protection_exist(self) -> None:
        html = Path("app/templates/redlab.html").read_text(encoding="utf-8")
        css = Path("app/static/css/redlab.css").read_text(encoding="utf-8")
        js = Path("app/static/js/redlab.js").read_text(encoding="utf-8")
        application = Path("app/application.py").read_text(encoding="utf-8")
        agent = Path("app/templates/agent.html").read_text(encoding="utf-8")
        self.assertIn("Fino RedLab", html)
        self.assertIn("/api/redlab/target/scan", js)
        self.assertIn("redlab_router", application)
        self.assertIn("redlabShortcut", agent)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn(".redlab-page [hidden]", css)
        self.assertIn("Private Security Suite", html)
        self.assertNotIn("platform-pixel-global.css", agent)
        self.assertTrue(is_protected_path("/redlab"))
        self.assertTrue(is_protected_path("/api/redlab/validate"))

    def test_no_hardcoded_secret_or_external_asset(self) -> None:
        files = [
            Path("app/redlab/engine.py"),
            Path("app/redlab/target_engine.py"),
            Path("app/templates/redlab.html"),
            Path("app/static/js/redlab.js"),
            Path("app/static/css/redlab.css"),
        ]
        content = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotIn("sk-proj-", content)
        self.assertNotIn('<script src="http', content)
        self.assertNotIn('<link href="http', content)

    def test_env_flags_exist(self) -> None:
        env = Path(".env.example").read_text(encoding="utf-8")
        self.assertIn("REDLAB_TARGET_MODE_ENABLED=", env)
        self.assertIn("REDLAB_TARGET_ALLOWLIST=", env)
        self.assertIn("REDLAB_TARGET_ALLOW_PRIVATE=", env)


if __name__ == "__main__":
    unittest.main()
