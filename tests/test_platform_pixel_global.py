from __future__ import annotations

import re
import unittest
from pathlib import Path


class PlatformPixelGlobalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.templates = {
            name: Path(f"app/templates/{name}.html").read_text(encoding="utf-8")
            for name in ("login", "agent", "sherlock")
        }
        self.css_path = Path("app/static/css/themes/platform-pixel-global.css")
        self.css = self.css_path.read_text(encoding="utf-8")

    def test_global_theme_is_loaded_by_product_pages(self) -> None:
        href = "/static/css/themes/platform-pixel-global.css"
        self.assertTrue(self.css_path.exists())
        for name, html in self.templates.items():
            with self.subTest(template=name):
                self.assertIn(href, html)
                self.assertIn('class="pixel-world-layer"', html)
                self.assertIn('aria-hidden="true"', html)

    def test_old_agent_background_is_removed(self) -> None:
        self.assertFalse(Path("app/static/css/themes/agent-retro-bg.css").exists())
        self.assertNotIn("agent-retro-bg.css", self.templates["agent"])
        self.assertNotIn("retro-bg-layer", self.templates["agent"])

    def test_theme_is_scoped_and_decorations_are_inert(self) -> None:
        dangerous_selector = re.compile(r"(?m)^\s*(html|\*)\s*(?:,|\{)")
        self.assertIsNone(dangerous_selector.search(self.css))
        self.assertIn("body.login-page,", self.css)
        self.assertIn("body.agent-page,", self.css)
        self.assertIn("body.sherlock-page {", self.css)
        self.assertIn("pointer-events: none;", self.css)
        self.assertIn("overflow: clip;", self.css)

    def test_theme_uses_no_external_assets_audio_or_autoplay(self) -> None:
        content = "\n".join([*self.templates.values(), self.css]).lower()
        self.assertNotIn("<audio", content)
        self.assertNotIn("autoplay", content)
        self.assertNotIn("http://", self.css.lower())
        self.assertNotIn("https://", self.css.lower())
        self.assertNotIn("url(", self.css.lower())

    def test_theme_is_responsive_and_reduced_motion_safe(self) -> None:
        self.assertIn("@media (max-width: 1040px)", self.css)
        self.assertIn("@media (max-width: 820px)", self.css)
        self.assertIn("@media (max-width: 620px)", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn("animation: none !important;", self.css)

    def test_isolated_samples_are_not_in_primary_agent_navigation(self) -> None:
        self.assertNotIn("Amostras Visuais", self.templates["agent"])
        self.assertNotIn('id="samplesBtn"', self.templates["agent"])


if __name__ == "__main__":
    unittest.main()
