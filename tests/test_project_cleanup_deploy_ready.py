from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.check_project_root import REQUIRED_PATHS, validate_project_root


ROOT = Path(__file__).resolve().parents[1]


class ProjectCleanupDeployReadyTests(unittest.TestCase):
    def test_project_root_has_required_production_files(self) -> None:
        self.assertEqual(validate_project_root(ROOT), [])
        for relative in REQUIRED_PATHS:
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_vercel_routes_to_api_index(self) -> None:
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["builds"][0]["src"], "api/index.py")
        api_index = (ROOT / "api/index.py").read_text(encoding="utf-8")
        self.assertNotIn("uvicorn.run", api_index)

    def test_cloud_requirements_exclude_desktop_dependencies(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        self.assertNotIn("pywebview", requirements)
        self.assertNotIn("pyinstaller", requirements)
        local = (ROOT / "requirements-local.txt").read_text(encoding="utf-8").lower()
        self.assertIn("pywebview", local)
        self.assertIn("pyinstaller", local)

    def test_ignore_files_cover_sensitive_artifacts(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        vercelignore = (ROOT / ".vercelignore").read_text(encoding="utf-8")
        for pattern in ("data/*.db", "data/*.log", "data/**/*.jsonl", "backup_*/", "*.zip", "tools/mcp-brasil/"):
            self.assertIn(pattern, gitignore)
            self.assertIn(pattern, vercelignore)

    def test_repository_has_no_release_artifacts_outside_ignored_runtime_data(self) -> None:
        forbidden_dirs = {"__pycache__", "build", "dist", "uploads", "reports", ".vercel"}
        forbidden_suffixes = {".pyc", ".pyo", ".log", ".db", ".zip", ".rar", ".spec"}
        failures: list[str] = []
        for path in ROOT.rglob("*"):
            if path.is_relative_to(ROOT / "data"):
                continue
            if path.is_dir() and path.name in forbidden_dirs:
                failures.append(str(path.relative_to(ROOT)))
            elif path.is_file() and path.suffix.lower() in forbidden_suffixes:
                failures.append(str(path.relative_to(ROOT)))
        self.assertEqual(failures, [])

    def test_experimental_repositories_are_not_in_production_tree(self) -> None:
        self.assertFalse((ROOT / "tools/mcp-brasil").exists())
        self.assertFalse((ROOT / "tools/DarkForest-Hunter-OpenAI").exists())


if __name__ == "__main__":
    unittest.main()
