from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agent.conversation_examples import CONVERSATION_EXAMPLES, EXAMPLE_COUNTS
from app.agent.orchestrator import AgentOrchestrator
from app.agent.router import classify_message, normalize_for_intent, web_needed
from app.agent.state import AgentState


class ConversationRouterTests(unittest.TestCase):
    def classify(self, message: str) -> dict:
        return classify_message(message)

    def test_examples_dataset_has_required_size(self) -> None:
        self.assertGreaterEqual(len(CONVERSATION_EXAMPLES), 1000)
        for intent, expected_count in EXAMPLE_COUNTS.items():
            actual = sum(1 for item in CONVERSATION_EXAMPLES if item["intent"] == intent)
            self.assertEqual(actual, expected_count)

    def test_required_intents(self) -> None:
        cases = {
            "Oi lindo": {"greeting"},
            "E o Neymar, o que acha da convocação dele na Copa?": {"football_opinion", "general_opinion"},
            "Sem pesquisar, o que você acha do Neymar?": {"football_opinion", "general_opinion"},
            "Pesquisa web profunda: Neymar convocação": {"deep_web_research"},
            "Estou perdido na vida, o que eu faço?": {"life_advice", "emotional_support"},
            "Terminei um relacionamento, tô mal": {"relationship_advice", "emotional_support"},
            "Como falar com uma pessoa que eu gosto?": {"dating_advice"},
            "Tenho uma dúvida sexual": {"safe_sexual_education"},
            "Me ensina algo explícito": {"safe_refusal", "safe_sexual_education"},
            "Meu PC está lento": {"tech_support"},
            "Analise este PC": {"pc_diagnostic"},
            "Quais pastas ocupam mais espaço?": {"folder_usage_top"},
            "Essa placa de vídeo vale?": {"product_advice"},
            "Me dá um conselho sobre dinheiro": {"money_advice"},
            "Estou triste": {"emotional_support"},
            "Me ajuda a cobrar um serviço": {"career_advice", "money_advice"},
            "O que acha de trap?": {"music_opinion"},
            "GTA ou Roblox?": {"gaming_opinion"},
            "Esse filme é bom?": {"movie_opinion"},
            "Você é muito robótico": {"casual_chat"},
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertIn(self.classify(message)["intent"], expected)

    def test_opinion_without_research_does_not_use_web(self) -> None:
        message = "Sem pesquisar, o que você acha do Neymar?"
        route = self.classify(message)
        self.assertFalse(web_needed(message, route["intent"]))

    def test_deep_web_request_uses_web(self) -> None:
        message = "Pesquisa web profunda: Neymar convocação"
        route = self.classify(message)
        self.assertEqual(route["intent"], "deep_web_research")
        self.assertTrue(web_needed(message, route["intent"]))

    def test_tool_selection_for_read_only_tools(self) -> None:
        orchestrator = object.__new__(AgentOrchestrator)
        cases = [
            ("Analise este PC", "pc_diagnostic", "performance", "analyze_pc"),
            ("Quais pastas ocupam mais espaço?", "folder_usage_top", "storage", "disk_usage"),
        ]
        for message, intent, category, expected_tool in cases:
            state = AgentState(
                user_message=message,
                normalized_message=normalize_for_intent(message),
                intent=intent,
                category=category,
            )
            with self.subTest(message=message):
                with patch("app.agent.orchestrator.is_cloud", return_value=False):
                    self.assertIn(expected_tool, orchestrator._select_tools(state, use_web=True))


if __name__ == "__main__":
    unittest.main()
