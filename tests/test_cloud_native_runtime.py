from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.agent.core import NexusCore
from app.agent.schemas.messages import AgentChatRequest
from app.core.runtime import get_runtime, is_cloud
from app.routes.status import read_health


class CloudNativeRuntimeTests(unittest.TestCase):
    def test_runtime_cloud_detected_by_env(self) -> None:
        with patch.dict(os.environ, {"AGENTE_FINO_RUNTIME": "cloud"}, clear=False):
            self.assertEqual(get_runtime(), "cloud")
            self.assertTrue(is_cloud())

    def test_vercel_forces_cloud(self) -> None:
        with patch.dict(os.environ, {"VERCEL": "1", "AGENTE_FINO_RUNTIME": "local_legacy"}, clear=False):
            self.assertEqual(get_runtime(), "cloud")

    def test_health_is_cloud_safe(self) -> None:
        health = read_health()
        self.assertEqual(health["version"], "2.1.1")
        self.assertEqual(health["runtime"], "cloud")
        self.assertFalse(health["local_only"])
        self.assertNotIn("C:\\", str(health))

    def test_cloud_chat_blocks_disk_request(self) -> None:
        response = NexusCore().chat(AgentChatRequest(message="Verifique meu disco C"))
        data = response.model_dump()
        self.assertEqual(data["mode"], "CLOUD")
        self.assertEqual(data["model_used"]["provider"], "cloud-policy")
        self.assertFalse(data["model_used"]["used_model"])
        self.assertIn("versao web/cloud nao tem acesso", data["answer"])
