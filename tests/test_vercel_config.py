from __future__ import annotations

import json
import unittest
from pathlib import Path


class VercelConfigTests(unittest.TestCase):
    def test_vercel_json_exists_and_routes_to_python(self) -> None:
        config = json.loads(Path("vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["version"], 2)
        self.assertEqual(config["builds"][0]["src"], "api/index.py")
        self.assertEqual(config["builds"][0]["use"], "@vercel/python")
        self.assertEqual(config["routes"][0]["dest"], "api/index.py")

    def test_env_example_has_cloud_vars(self) -> None:
        env = Path(".env.example").read_text(encoding="utf-8")
        for token in [
            "AGENTE_FINO_RUNTIME=cloud",
            "AGENTE_FINO_PUBLIC_MODE=true",
            "DATABASE_URL=",
            "AGENTE_FINO_ADMIN_PASSWORD_HASH=",
            "AGENTE_FINO_RAG_ENABLED=false",
            "AGENTE_FINO_UPLOADS_ENABLED=false",
        ]:
            self.assertIn(token, env)

    def test_gitignore_blocks_release_and_secret_artifacts(self) -> None:
        gitignore = Path(".gitignore").read_text(encoding="utf-8")
        for token in [".env", ".env.*", "data/*.db", "backup_*/", ".vercel/", "*.rar", "*.zip"]:
            self.assertIn(token, gitignore)

