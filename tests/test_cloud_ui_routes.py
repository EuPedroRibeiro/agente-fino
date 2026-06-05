from __future__ import annotations

import unittest
from pathlib import Path

from app.security.access import is_protected_path, is_public_path


class CloudUiRoutesTests(unittest.TestCase):
    def test_login_and_static_are_public_agent_is_protected(self) -> None:
        self.assertTrue(is_public_path("/login"))
        self.assertTrue(is_public_path("/static/css/agent.css"))
        self.assertTrue(is_protected_path("/agent"))
        self.assertTrue(is_protected_path("/api/admin/health"))

    def test_ui_does_not_show_local_diagnostic_nav(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        visible_sidebar = html.split('id="detailsDrawer"', 1)[0]
        self.assertNotIn("Diagnostico", visible_sidebar)
        self.assertNotIn("Analisar PC", visible_sidebar)

