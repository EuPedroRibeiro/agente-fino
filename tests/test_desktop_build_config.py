from __future__ import annotations

import unittest
from pathlib import Path


class DesktopBuildConfigTests(unittest.TestCase):
    def test_build_scripts_exist_and_use_onedir(self) -> None:
        release = Path("build_desktop_release.ps1").read_text(encoding="utf-8")
        self.assertIn("--onedir", release)
        self.assertIn('--icon "app/static/favicon.ico"', release)
        self.assertTrue(Path("build_desktop_debug.ps1").exists())

    def test_requirements_include_desktop_dependencies(self) -> None:
        requirements = Path("requirements-local.txt").read_text(encoding="utf-8")
        self.assertIn("pywebview", requirements)
        self.assertIn("pyinstaller", requirements)


if __name__ == "__main__":
    unittest.main()
