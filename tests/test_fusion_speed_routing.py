from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent.orchestrator import AgentOrchestrator
from app.agent.providers.local_rules import LocalRulesProvider
from app.agent.providers.model_router import ModelRouter, load_fusion_settings
from app.agent.schemas.messages import AgentChatRequest


class FusionSpeedRoutingTests(unittest.TestCase):
    def test_fast_provider_order_contains_openai_first(self) -> None:
        settings = load_fusion_settings()
        self.assertEqual(settings["fast_provider_order"][0], "openai")

    def test_router_has_fast_chain_with_local_fallback(self) -> None:
        chain = ModelRouter().provider_chain_for_mode("FAST", direct=True)
        self.assertEqual(chain[-1].name, "local-rules")

    def test_analyze_pc_stays_expert(self) -> None:
        state = self._run_without_real_io(AgentChatRequest(message="Analise este PC", use_web=False))
        self.assertEqual(state.mode, "EXPERT")
        self.assertIn("analyze_pc", state.selected_tools)

    def test_disk_usage_stays_expert(self) -> None:
        state = self._run_without_real_io(AgentChatRequest(message="Quais pastas ocupam espaco?", use_web=False))
        self.assertEqual(state.mode, "EXPERT")
        self.assertIn("disk_usage", state.selected_tools)

    def test_web_search_does_not_use_fast(self) -> None:
        state = self._run_without_real_io(AgentChatRequest(message="Pesquise noticia atual sobre IA", use_web=True))
        self.assertNotEqual(state.mode, "FAST")
        self.assertIn("web_search", state.selected_tools)

    def _run_without_real_io(self, request: AgentChatRequest):
        provider_status = {
            "selected_provider": "local-rules",
            "selected_model": "deterministic-rules",
            "real_llm_enabled": False,
            "fallback_reason": "teste offline",
        }
        local_rules = LocalRulesProvider()
        with (
            patch("app.agent.orchestrator.rag.status", return_value={"enabled": True, "honest_status": "test"}),
            patch("app.agent.orchestrator.ModelRouter.status", return_value=provider_status),
            patch("app.agent.orchestrator.ModelRouter.provider_chain", return_value=[local_rules]),
            patch("app.agent.orchestrator.ModelRouter.provider_chain_for_mode", return_value=[local_rules]),
            patch("app.agent.orchestrator.AgentOrchestrator._run_tool", return_value={"name": "mock_tool", "status": "success", "result": {}}),
            patch("app.agent.orchestrator.is_cloud", return_value=False),
        ):
            return AgentOrchestrator().run(request)


if __name__ == "__main__":
    unittest.main()
