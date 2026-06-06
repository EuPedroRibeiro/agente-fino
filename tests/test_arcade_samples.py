from __future__ import annotations

import unittest
from pathlib import Path

from starlette.requests import Request

from app.routes.samples import samples_page
from app.security.access import is_protected_path


class ArcadeSamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = Path("app/templates/samples.html").read_text(encoding="utf-8")
        self.css = Path("app/static/css/themes/mario-sample.css").read_text(encoding="utf-8")
        self.js = Path("app/static/js/mario-sample.js").read_text(encoding="utf-8")

    def test_samples_route_and_assets_exist(self) -> None:
        self.assertTrue(Path("app/routes/samples.py").exists())
        self.assertTrue(Path("app/static/css/themes/mario-sample.css").exists())
        self.assertTrue(Path("app/static/js/mario-sample.js").exists())
        self.assertTrue(is_protected_path("/samples"))
        self.assertTrue(is_protected_path("/amostras"))

    def test_samples_page_renders_http_200(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/samples",
                "headers": [],
                "client": ("testclient", 1234),
                "server": ("testserver", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )
        response = samples_page(request)
        self.assertEqual(response.status_code, 200)

    def test_arcade_theme_is_scoped_and_does_not_override_app_globally(self) -> None:
        selectors = [line.strip().lower() for line in self.css.splitlines()]
        self.assertIn(".mario-sample-theme {", selectors)
        self.assertNotIn("body {", selectors)
        self.assertNotIn("html {", selectors)
        self.assertNotIn("* {", selectors)
        self.assertNotIn("#game-container {", selectors)
        self.assertNotIn("#hud {", selectors)
        self.assertNotIn("#overlay {", selectors)

    def test_sample_has_no_audio_autoplay_canvas_or_external_assets(self) -> None:
        content = "\n".join([self.template, self.css, self.js]).lower()
        self.assertNotIn("<audio", content)
        self.assertNotIn("autoplay", content)
        self.assertNotIn("<canvas", content)
        self.assertNotIn("new audio", content)
        self.assertNotIn("http://", content)
        self.assertNotIn("https://", content)

    def test_preview_only_toggles_sample_class(self) -> None:
        self.assertIn('class="mario-sample-theme"', self.template)
        self.assertIn('classList.toggle("is-previewing"', self.js)
        self.assertNotIn("document.body.classList", self.js)
        self.assertNotIn("document.documentElement", self.js)

    def test_agent_links_to_samples_from_hidden_drawer(self) -> None:
        agent_html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        agent_js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        visible_main = agent_html.split('id="detailsDrawer"', 1)[0]
        self.assertNotIn("Amostras Visuais", visible_main)
        self.assertIn('id="samplesBtn"', agent_html)
        self.assertIn('window.location.href = "/samples"', agent_js)


if __name__ == "__main__":
    unittest.main()
