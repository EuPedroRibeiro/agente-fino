from __future__ import annotations

import unittest
from pathlib import Path

import desktop_app
from app.core import paths


class DesktopPathsTests(unittest.TestCase):
    def test_desktop_app_exists_and_uses_localhost_only(self) -> None:
        self.assertTrue(Path("desktop_app.py").exists())
        self.assertEqual(desktop_app.HOST, "127.0.0.1")
        self.assertIn("127.0.0.1", desktop_app.LOGIN_URL)

    def test_paths_module_exposes_required_helpers(self) -> None:
        self.assertFalse(paths.is_frozen())
        self.assertTrue(paths.resource_path("app").name, "app")


if __name__ == "__main__":
    unittest.main()
