from __future__ import annotations

import re
import unittest
from pathlib import Path


class AgentRetroBackgroundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Path("app/templates/agent.html").read_text(encoding="utf-8")
        self.login = Path("app/templates/login.html").read_text(encoding="utf-8")
        self.sherlock = Path("app/templates/sherlock.html").read_text(encoding="utf-8")
        self.samples = Path("app/templates/samples.html").read_text(encoding="utf-8")
        self.css_path = Path("app/static/css/themes/agent-retro-bg.css")
        self.css = self.css_path.read_text(encoding="utf-8")

    def test_theme_is_loaded_only_by_agent(self) -> None:
        theme_href = "/static/css/themes/agent-retro-bg.css"
        self.assertTrue(self.css_path.exists())
        self.assertIn(theme_href, self.agent)
        self.assertNotIn(theme_href, self.login)
        self.assertNotIn(theme_href, self.sherlock)
        self.assertNotIn(theme_href, self.samples)

    def test_agent_contains_inert_accessible_background_layer(self) -> None:
        self.assertIn('class="retro-bg-layer"', self.agent)
        self.assertIn('aria-hidden="true"', self.agent)
        self.assertIn("pointer-events: none;", self.css)
        self.assertIn("overflow: clip;", self.css)

    def test_theme_has_no_dangerous_global_selectors(self) -> None:
        dangerous_selector = re.compile(r"(?m)^\s*(body|html|\*)\s*(?:,|\{)")
        self.assertIsNone(dangerous_selector.search(self.css))
        self.assertIn("body.agent-page {", self.css)
        self.assertIn(".agent-page .retro-bg-layer {", self.css)
        self.assertIn(".agent-page .main-stage::before {", self.css)
        self.assertNotIn(".retro-bg-layer {", self.css.replace(".agent-page .retro-bg-layer {", ""))

    def test_theme_uses_no_assets_audio_autoplay_or_javascript(self) -> None:
        content = "\n".join([self.agent, self.css]).lower()
        self.assertNotIn("<audio", content)
        self.assertNotIn("autoplay", content)
        self.assertNotIn("url(", self.css.lower())
        self.assertNotIn("http://", content)
        self.assertNotIn("https://", content)
        self.assertFalse(Path("app/static/js/agent-retro-bg.js").exists())

    def test_theme_is_subtle_responsive_and_reduced_motion_safe(self) -> None:
        self.assertIn("@media (max-width: 900px)", self.css)
        self.assertIn("@media (max-width: 620px)", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn("animation: none !important;", self.css)
        self.assertIn("z-index: 0;", self.css)


if __name__ == "__main__":
    unittest.main()
