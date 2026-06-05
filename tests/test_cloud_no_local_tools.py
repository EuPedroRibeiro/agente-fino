from __future__ import annotations

import unittest

from app.agent.providers.model_router import ModelRouter
from app.agent.tools_registry import list_tools
from app.routes import agent as agent_routes
from app.routes.actions import clean_temp, restart_print_spooler
from app.routes.status import read_processes


class CloudNoLocalToolsTests(unittest.TestCase):
    def test_cloud_blocks_disk_usage_endpoint(self) -> None:
        response = agent_routes.agent_disk_usage(agent_routes.DiskUsageRequest(root=r"C:\\"))
        self.assertEqual(response["status"], "disabled_in_cloud")
        self.assertEqual(response["folders"], [])

    def test_cloud_blocks_actions(self) -> None:
        self.assertEqual(clean_temp({"confirm": True})["status"], "disabled_in_cloud")
        self.assertEqual(restart_print_spooler({"confirm": True})["status"], "disabled_in_cloud")

    def test_cloud_blocks_process_list(self) -> None:
        response = read_processes()
        self.assertEqual(response["status"], "disabled_in_cloud")
        self.assertEqual(response["processes"], [])

    def test_cloud_does_not_call_ollama(self) -> None:
        status = ModelRouter().status()
        self.assertEqual(status["ollama_status"], "disabled_in_cloud")
        self.assertFalse(status["ollama_available"])
        self.assertNotIn("ollama", status["selection_order"])

    def test_fusion_status_reports_rag_disabled_in_cloud(self) -> None:
        status = agent_routes.agent_fusion_status()
        self.assertEqual(status["ollama_status"], "disabled_in_cloud")
        self.assertEqual(status["rag_status"], "disabled_in_cloud")

    def test_cloud_tools_are_cloud_safe(self) -> None:
        names = {tool["name"] for tool in list_tools()}
        self.assertIn("chat", names)
        self.assertIn("search_web", names)
        self.assertNotIn("get_system_status", names)
        self.assertNotIn("restart_spooler", names)
