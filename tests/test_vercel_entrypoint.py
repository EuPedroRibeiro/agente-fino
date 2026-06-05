from __future__ import annotations

import ast
import unittest
from pathlib import Path


class VercelEntrypointTests(unittest.TestCase):
    def test_api_index_imports_app_without_uvicorn_run(self) -> None:
        text = Path("api/index.py").read_text(encoding="utf-8")
        self.assertIn("from app.application import app", text)
        self.assertNotIn("uvicorn.run", text)

    def test_main_keeps_uvicorn_for_local_dev(self) -> None:
        text = Path("main.py").read_text(encoding="utf-8")
        self.assertIn("uvicorn.run", text)
        self.assertIn("from app.application import app", text)

    def test_application_exposes_fastapi_app(self) -> None:
        tree = ast.parse(Path("app/application.py").read_text(encoding="utf-8"))
        names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        self.assertIn("create_app", names)

