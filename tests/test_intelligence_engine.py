from __future__ import annotations

import asyncio
import json
import os
import time
import unittest
from unittest.mock import Mock, patch

from app.agent.core import NexusCore
from app.agent.schemas.messages import AgentChatRequest
from app.intelligence import FinoIntelligenceEngine
from app.intelligence.intent_router import IntentRoute
from app.intelligence.local_responses import answer_date, answer_time
from app.intelligence.tool_registry import ToolRegistry
from app.routes import agent as agent_routes


async def _collect_stream(response) -> str:
    parts: list[str] = []
    async for chunk in response.body_iterator:
        parts.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
    return "".join(parts)


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

    def test_basic_identity_time_and_date_are_fast_local(self) -> None:
        cases = {
            "Qual seu nome?": "identity_query",
            "como você se chama?": "identity_query",
            "quem é você?": "identity_query",
            "Que horas são?": "time_query",
            "qual a hora atual?": "time_query",
            "Que dia é hoje?": "date_query",
            "data de hoje": "date_query",
        }
        for message, expected_intent in cases.items():
            with self.subTest(message=message):
                decision = self.engine.decide(message)
                self.assertEqual(decision.intent, expected_intent)
                self.assertEqual(decision.mode, "FAST")
                self.assertTrue(decision.answer_directly)
                self.assertTrue(decision.direct_answer)
                self.assertEqual(decision.selected_tools, [])
                self.assertFalse(decision.web_needed)
                self.assertFalse(decision.rag_needed)
                self.assertNotIn("Nao consegui concluir esse pedido", decision.direct_answer)

    def test_local_time_and_date_answers_have_expected_shape(self) -> None:
        self.assertRegex(answer_time(), r"^Agora são \d{2}:\d{2}\.$")
        self.assertRegex(answer_date(), r"^Hoje é .+, \d{1,2} de .+ de \d{4}\.$")

    def test_time_local_failure_uses_specific_local_fallback(self) -> None:
        with patch("app.intelligence.local_responses.answer_time", side_effect=RuntimeError("clock unavailable")):
            decision = self.engine.decide("Que horas são?")
        self.assertEqual(decision.intent, "time_query")
        self.assertEqual(decision.mode, "FAST")
        self.assertTrue(decision.answer_directly)
        self.assertEqual(decision.direct_answer, "Não consegui ler o relógio local agora.")
        self.assertNotIn("Não consegui concluir esse pedido", decision.direct_answer)

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

    def test_project_improvement_request_is_planning_not_local_casual(self) -> None:
        decision = self.engine.decide("Me ajuda a melhorar esse projeto")
        self.assertEqual(decision.intent, "planning")
        self.assertEqual(decision.execution_intent, "routine_planning")
        self.assertFalse(decision.answer_directly)
        self.assertFalse(decision.web_needed)
        self.assertNotIn("document_lookup", decision.selected_tools)

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

    def test_core_basic_intents_never_call_providers_or_specialized_services(self) -> None:
        for message, expected_intent in (
            ("Qual seu nome?", "identity_query"),
            ("Que horas são?", "time_query"),
            ("Que dia é hoje?", "date_query"),
        ):
            with self.subTest(message=message):
                core = NexusCore()
                core.document_lookup = Mock()
                core.public_data = Mock()
                core.mcp_brasil = Mock()
                core.orchestrator = Mock()
                with patch("app.agent.core.production_config_errors", return_value=[]):
                    response = core.chat(AgentChatRequest(message=message))
                core.document_lookup.handle.assert_not_called()
                core.public_data.ask.assert_not_called()
                core.mcp_brasil.ask.assert_not_called()
                core.orchestrator.run.assert_not_called()
                self.assertEqual(response.intent, expected_intent)
                self.assertEqual(response.mode, "FAST")
                self.assertEqual(response.model_used["provider"], "local-intelligence")
                self.assertFalse(response.model_used["llm_used"])
                self.assertEqual(response.selected_tools, [])
                self.assertFalse(response.web_used)
                self.assertFalse(response.rag_status.get("used"))

    def test_local_identity_survives_history_failure(self) -> None:
        core = NexusCore()
        core.orchestrator = Mock()
        with (
            patch("app.agent.core.production_config_errors", return_value=[]),
            patch("app.agent.core.conversation_logs.add_message", side_effect=RuntimeError("history unavailable")),
        ):
            response = core.chat(AgentChatRequest(message="Qual seu nome?"))
        self.assertEqual(response.intent, "identity_query")
        self.assertEqual(response.mode, "FAST")
        self.assertIn("Agente Fino", response.final_answer)
        self.assertEqual(response.model_used["provider"], "local-intelligence")
        core.orchestrator.run.assert_not_called()

    def test_basic_intents_work_in_simulated_production_without_providers(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AGENTE_FINO_ENV": "production",
                "AGENTE_FINO_PUBLIC_MODE": "true",
                "OPENAI_ENABLED": "false",
                "GEMINI_API_KEY": "",
                "DOCUMENT_LOOKUP_ENABLED": "false",
            },
            clear=False,
        ):
            core = NexusCore()
            core.orchestrator = Mock()
            core.document_lookup = Mock()
            with patch("app.agent.core.production_config_errors", return_value=[]):
                for message in ("Qual seu nome?", "Que horas são?", "Que dia é hoje?"):
                    response = core.chat(AgentChatRequest(message=message))
                    self.assertEqual(response.mode, "FAST")
                    self.assertEqual(response.model_used["provider"], "local-intelligence")
                    self.assertFalse(response.model_used["llm_used"])
            core.orchestrator.run.assert_not_called()
            core.document_lookup.handle.assert_not_called()

    def test_sse_and_chat_deliver_same_fast_local_result(self) -> None:
        payload = AgentChatRequest(message="Qual seu nome?")
        with patch("app.agent.core.production_config_errors", return_value=[]):
            chat_response = agent_routes.core.chat(payload)
            created = agent_routes.agent_run_create(payload)
            stream_response = agent_routes.agent_run_events(created["run_id"])
            body = asyncio.run(_collect_stream(stream_response))
        run_done_line = next(line for line in body.splitlines() if line.startswith("data: ") and '"response"' in line)
        run_payload = json.loads(run_done_line.removeprefix("data: "))
        sse_response = run_payload["response"]
        self.assertEqual(sse_response["final_answer"], chat_response.final_answer)
        self.assertEqual(sse_response["intent"], "identity_query")
        self.assertEqual(sse_response["mode"], "FAST")
        self.assertEqual(sse_response["model_used"]["provider"], "local-intelligence")

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
