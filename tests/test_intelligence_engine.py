from __future__ import annotations

import time
import unittest
from unittest.mock import Mock, patch

from app.agent.core import NexusCore
from app.agent.schemas.messages import AgentChatRequest
from app.intelligence import FinoIntelligenceEngine
from app.intelligence.intent_router import IntentRoute
from app.intelligence.tool_registry import ToolRegistry


class LowConfidenceRiskyRouter:
    def route(self, _message: str) -> IntentRoute:
        return IntentRoute(
            intent="restart_spooler",
            execution_intent="restart_spooler",
            category="printer",
            confidence=0.4,
            reason="Teste de baixa confianca.",
            route={},
        )


class FinoIntelligenceEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = FinoIntelligenceEngine()

    def test_greeting_is_local_fast_and_deterministic(self) -> None:
        started = time.perf_counter()
        decision = self.engine.decide("Oi")
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.assertEqual(decision.intent, "greeting")
        self.assertEqual(decision.mode, "FAST")
        self.assertTrue(decision.answer_directly)
        self.assertEqual(decision.selected_tools, [])
        self.assertFalse(decision.web_needed)
        self.assertFalse(decision.rag_needed)
        self.assertNotIn("erro registrado", decision.direct_answer.lower())
        self.assertLess(elapsed_ms, 300)

    def test_document_tools_require_document_and_clear_intent(self) -> None:
        ordinary = self.engine.decide("Meu protocolo e 20345568796")
        self.assertNotIn(ordinary.execution_intent, {"cpf_lookup", "cpf_validate", "cnpj_lookup"})
        self.assertNotIn("document_lookup", ordinary.selected_tools)

        explicit = self.engine.decide("Consulte o CPF 20345568796")
        self.assertEqual(explicit.execution_intent, "cpf_lookup")
        self.assertEqual(explicit.selected_tools, ["document_lookup"])

    def test_web_is_only_selected_when_needed(self) -> None:
        casual = self.engine.decide("Sem pesquisar, o que acha do Neymar?")
        self.assertFalse(casual.web_needed)
        self.assertNotIn("web_search", casual.selected_tools)

        research = self.engine.decide("Pesquise na web noticias atuais sobre IA")
        self.assertEqual(research.execution_intent, "web_research")
        self.assertTrue(research.web_needed)
        self.assertIn("web_search", research.selected_tools)

    def test_pc_analysis_selects_read_only_tool_in_local_runtime(self) -> None:
        with patch("app.intelligence.tool_registry.is_cloud", return_value=False):
            decision = self.engine.decide("Analise este PC")
        self.assertEqual(decision.intent, "pc_analysis")
        self.assertEqual(decision.mode, "EXPERT")
        self.assertEqual(decision.selected_tools, ["analyze_pc"])

    def test_low_confidence_cannot_authorize_risky_tool(self) -> None:
        with patch("app.intelligence.tool_registry.is_cloud", return_value=False):
            decision = FinoIntelligenceEngine(router=LowConfidenceRiskyRouter()).decide("reiniciar")
        self.assertNotIn("restart_spooler", decision.selected_tools)
        self.assertIn("restart_spooler:confianca_baixa", decision.blocked_tools)

    def test_tool_registry_exposes_operational_contract(self) -> None:
        document_tool = ToolRegistry().get("document_lookup")
        self.assertIsNotNone(document_tool)
        self.assertEqual(document_tool.risk, "low")
        self.assertGreater(document_tool.timeout_seconds, 0)
        self.assertIn("DOCUMENT_LOOKUP_ENABLED", document_tool.required_env)

    def test_core_greeting_never_calls_specialized_services_or_orchestrator(self) -> None:
        core = NexusCore()
        core.document_lookup = Mock()
        core.public_data = Mock()
        core.mcp_brasil = Mock()
        core.orchestrator = Mock()
        with patch("app.agent.core.production_config_errors", return_value=[]):
            response = core.chat(AgentChatRequest(message="oi"))
        core.document_lookup.handle.assert_not_called()
        core.public_data.ask.assert_not_called()
        core.mcp_brasil.ask.assert_not_called()
        core.orchestrator.run.assert_not_called()
        self.assertEqual(response.mode, "FAST")
        self.assertEqual(response.intent, "greeting")
        self.assertFalse(response.model_used["llm_used"])
        self.assertIn("router", response.intelligence)

    def test_response_keeps_structured_intelligence_contract(self) -> None:
        core = NexusCore()
        with patch("app.agent.core.production_config_errors", return_value=[]):
            response = core.chat(AgentChatRequest(message="oi"))
        payload = response.model_dump()
        for field in (
            "final_answer",
            "conversation_id",
            "intent",
            "mode",
            "model_used",
            "timings_ms",
            "selected_tools",
            "sources",
            "plan",
            "risk_level",
            "confidence",
            "intelligence",
        ):
            self.assertIn(field, payload)


if __name__ == "__main__":
    unittest.main()
