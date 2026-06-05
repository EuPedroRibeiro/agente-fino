from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image


class AgenteFinoBrandAssetsTests(unittest.TestCase):
    def test_brand_assets_exist(self) -> None:
        required = [
            "app/static/brand/agente-fino-logo-full.png",
            "app/static/brand/agente-fino-symbol.png",
            "app/static/brand/agente-fino-symbol-reduced.png",
            "app/static/brand/agente-fino-symbol-mono.png",
            "app/static/brand/agente-fino-og.png",
            "app/static/favicon.svg",
            "app/static/favicon.ico",
            "app/static/apple-touch-icon.png",
        ]
        for path in required:
            with self.subTest(path=path):
                file_path = Path(path)
                self.assertTrue(file_path.exists())
                self.assertGreater(file_path.stat().st_size, 500)

    def test_static_brand_paths_are_mounted(self) -> None:
        application_py = Path("app/application.py").read_text(encoding="utf-8")
        self.assertIn('app.mount("/static"', application_py)
        self.assertIn('FileResponse("app/static/favicon.ico"', application_py)

    def test_brand_asset_dimensions(self) -> None:
        expected = {
            "app/static/brand/agente-fino-logo-full.png": (980, 320),
            "app/static/brand/agente-fino-symbol.png": (512, 512),
            "app/static/brand/agente-fino-symbol-reduced.png": (512, 512),
            "app/static/apple-touch-icon.png": (180, 180),
        }
        for path, size in expected.items():
            with self.subTest(path=path):
                with Image.open(path) as image:
                    self.assertEqual(image.size, size)

    def test_templates_use_official_brand_assets(self) -> None:
        login = Path("app/templates/login.html").read_text(encoding="utf-8")
        agent = Path("app/templates/agent.html").read_text(encoding="utf-8")
        index = Path("app/templates/index.html").read_text(encoding="utf-8")
        for html in [login, agent, index]:
            with self.subTest(template=html[:30]):
                self.assertIn("/static/favicon.svg", html)
                self.assertIn("/static/favicon.ico", html)
                self.assertIn("/static/apple-touch-icon.png", html)
                self.assertIn("Agente Fino", html)
                self.assertNotIn("Nexus Core", html)
                self.assertNotIn("Black Gold", html)
        self.assertIn("/static/brand/agente-fino-logo-full.png", login)
        self.assertIn("/static/brand/agente-fino-symbol-reduced.png", login)
        self.assertIn("/static/brand/agente-fino-symbol-reduced.png", agent)
        self.assertIn("/static/brand/agente-fino-symbol.png", agent)

    def test_no_api_keys_in_frontend_assets(self) -> None:
        paths = [
            Path("app/templates/login.html"),
            Path("app/templates/agent.html"),
            Path("app/templates/index.html"),
            Path("app/static/css/agent.css"),
            Path("app/static/js/agent.js"),
        ]
        forbidden = ["sk-", "OPENAI_API_KEY", "GEMINI_API_KEY", "Authorization", "Bearer "]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(path=str(path), token=token):
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
