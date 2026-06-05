from __future__ import annotations

import unittest

from app.agent.conversation_policy import BAD_RESPONSE_PATTERNS, contains_bad_response_pattern
from app.agent.orchestrator import _fallback_open_chat, _local_quality_rewrite
from app.agent.router import classify_message, normalize_for_intent
from app.agent.state import AgentState


class ResponseQualityTests(unittest.TestCase):
    def make_state(self, message: str) -> AgentState:
        route = classify_message(message)
        return AgentState(
            user_message=message,
            normalized_message=normalize_for_intent(message),
            intent=route["intent"],
            category=route["category"],
        )

    def test_bad_patterns_are_detected(self) -> None:
        for pattern in BAD_RESPONSE_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertTrue(contains_bad_response_pattern(f"{pattern} em temas comuns."))

    def test_common_fallbacks_do_not_use_bad_patterns(self) -> None:
        messages = [
            "Oi lindo",
            "Tudo bem?",
            "E o Neymar, o que acha da convocação dele na Copa?",
            "Estou perdido na vida, o que eu faço?",
            "Terminei um relacionamento, tô mal",
            "Como falar com uma pessoa que eu gosto?",
            "O que acha de trap?",
            "GTA ou Roblox?",
            "Você é muito robótico",
        ]
        for message in messages:
            answer = _fallback_open_chat(self.make_state(message))
            with self.subTest(message=message):
                self.assertFalse(contains_bad_response_pattern(answer), answer)

    def test_quality_rewrite_replaces_evasive_common_answer(self) -> None:
        state = self.make_state("O que acha de trap?")
        rewritten = _local_quality_rewrite(state, "Não sou especializado nisso.")
        self.assertFalse(contains_bad_response_pattern(rewritten))
        self.assertIn("Trap", rewritten)

    def test_greeting_does_not_mention_technical_context(self) -> None:
        answer = _fallback_open_chat(self.make_state("Oi lindo"))
        forbidden = ["RAG", "web", "processo", "diagnóstico técnico"]
        self.assertFalse(any(word.lower() in answer.lower() for word in forbidden), answer)


if __name__ == "__main__":
    unittest.main()
