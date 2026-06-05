from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent.orchestrator import AgentOrchestrator
from app.agent.router import classify_message
from app.agent.schemas.messages import AgentChatRequest


FAKE_STATUS = {
    "hostname": "TEST-PC",
    "uptime": "2 days, 1:02:03",
    "boot_time": "2026-05-27 09:00:00",
    "local_ip": "192.168.0.50",
    "cpu": {"percent": 2.2},
    "memory": {"used_gb": 5.05, "total_gb": 15.88, "available_gb": 10.83, "percent": 31.8},
    "disk": {"path": "C:\\", "free_gb": 131.82, "total_gb": 222.96, "used_gb": 91.14, "percent": 40.9},
}


class LocalToolFastTests(unittest.TestCase):
    def test_disk_space_uses_local_tool_fast(self) -> None:
        with (
            patch("app.agent.orchestrator.get_system_status", return_value=FAKE_STATUS),
            patch("app.agent.orchestrator.ModelRouter.status") as router_status,
            patch("app.agent.orchestrator.AgentOrchestrator._model_answer") as model_answer,
            patch("app.agent.orchestrator.perform_web_research") as web_research,
        ):
            state = AgentOrchestrator().run(AgentChatRequest(message="Olhe quanto de espaco tem meu disco", use_web=True))

        router_status.assert_not_called()
        model_answer.assert_not_called()
        web_research.assert_not_called()
        self.assertEqual(state.intent, "disk_space")
        self.assertEqual(state.mode, "LOCAL_TOOL_FAST")
        self.assertEqual(state.selected_tools, ["disk_space"])
        self.assertEqual(state.model_used["provider"], "local-tool")
        self.assertFalse(state.model_used["used_model"])
        self.assertFalse(state.web_used)
        self.assertEqual(state.rag_status["skipped"], "local_tool_fast")
        self.assertIn("Disco C:", state.final_answer.splitlines()[0])
        self.assertIn("131,82 GB livres de 222,96 GB", state.final_answer)
        self.assertIn("Leitura rapida:", state.final_answer)
        self.assertIn("Bonus tecnico:", state.final_answer)
        self.assertNotIn("Analise real deste PC", state.final_answer)
        self.assertLess(state.timings_ms["total"], 5000)

    def test_ram_status_uses_local_tool_fast(self) -> None:
        with patch("app.agent.orchestrator.get_system_status", return_value=FAKE_STATUS):
            state = AgentOrchestrator().run(AgentChatRequest(message="Quanto de RAM estou usando?", use_web=False))

        self.assertEqual(state.intent, "ram_status")
        self.assertEqual(state.mode, "LOCAL_TOOL_FAST")
        self.assertEqual(state.selected_tools, ["ram_status"])
        self.assertIn("RAM:", state.final_answer.splitlines()[0])
        self.assertIn("5,05 GB em uso de 15,88 GB", state.final_answer)
        self.assertFalse(state.model_used["used_model"])

    def test_folder_usage_stays_detailed_disk_usage(self) -> None:
        route = classify_message("Quais pastas ocupam mais espaco?")
        self.assertEqual(route["intent"], "folder_usage_top")

    def test_analyze_pc_stays_full_diagnostic(self) -> None:
        route = classify_message("Analise este PC")
        self.assertEqual(route["intent"], "pc_diagnostic")

    def test_greeting_does_not_use_local_tool(self) -> None:
        with patch("app.agent.orchestrator.get_system_status") as get_status:
            state = AgentOrchestrator().run(AgentChatRequest(message="oi", use_web=False))

        get_status.assert_not_called()
        self.assertEqual(state.mode, "FAST")
        self.assertEqual(state.selected_tools, [])

    def test_agent_css_reserves_space_for_fixed_composer(self) -> None:
        with open("app/static/css/agent.css", encoding="utf-8") as css_file:
            css = css_file.read()
        with open("app/static/js/agent.js", encoding="utf-8") as js_file:
            js = js_file.read()
        self.assertIn("--composer-height", css)
        self.assertIn("scroll-padding-bottom: calc(var(--composer-height)", css)
        self.assertIn("updateComposerHeight", js)
        self.assertIn("scrollToBottom", js)


if __name__ == "__main__":
    unittest.main()
