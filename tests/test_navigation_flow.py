from __future__ import annotations

import unittest
from pathlib import Path


class NavigationFlowTests(unittest.TestCase):
    def test_login_enters_agent(self) -> None:
        html = Path("app/templates/login.html").read_text(encoding="utf-8")
        js = Path("app/static/js/login.js").read_text(encoding="utf-8")
        self.assertIn("Agente Fino", html)
        self.assertIn("Entrar", html)
        self.assertIn('type="password"', html)
        self.assertIn('/static/js/login.js', html)
        self.assertIn('body: JSON.stringify({ password })', js)
        self.assertIn('localStorage.setItem("agente_fino_authenticated", "true")', js)
        self.assertIn('href="/agent"', html)

    def test_root_redirects_to_agent_or_login(self) -> None:
        html = Path("app/templates/index.html").read_text(encoding="utf-8")
        self.assertIn("agente_fino_authenticated", html)
        self.assertIn("nexus_authenticated", html)
        self.assertIn('"/agent"', html)
        self.assertIn('"/login"', html)
        self.assertNotIn("metrics-grid", html)
        self.assertNotIn("openAgentBtn", html)

    def test_agent_has_logout_without_diagnostic_nav(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        self.assertIn("Agente Fino", html)
        self.assertIn('id="logoutBtn"', html)
        self.assertIn('href="/login"', html)
        self.assertNotIn('id="diagnosticBtn"', html)
        self.assertNotIn('href="/"', html)
        self.assertIn('window.location.href = "/login"', js)
        self.assertIn('localStorage.removeItem(AUTH_KEY)', js)


if __name__ == "__main__":
    unittest.main()
