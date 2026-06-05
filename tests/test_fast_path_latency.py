from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from app.agent.orchestrator import AgentOrchestrator
from app.agent.providers.base import ModelResponse
from app.agent.schemas.messages import AgentChatRequest


class FakeFastProvider:
    name = "openai-responses"
    model = "fake-fast"

    def __init__(self) -> None:
        self.max_tokens_seen: int | None = None

    def chat(self, messages, temperature=0.2, max_tokens=1200, timeout_seconds=None):
        self.max_tokens_seen = max_tokens
        return ModelResponse(text="ok", provider=self.name, model=self.model, used_model=True)


class FastPathLatencyTests(unittest.TestCase):
    def test_oi_uses_fast_without_heavy_context(self) -> None:
        started = time.perf_counter()
        state = AgentOrchestrator().run(AgentChatRequest(message="oi"))
        elapsed = time.perf_counter() - started
        self.assertEqual(state.mode, "FAST")
        self.assertEqual(state.selected_tools, [])
        self.assertFalse(state.web_used)
        self.assertEqual(state.rag_status.get("skipped"), "fast_path")
        self.assertFalse(state.model_used.get("used_verifier", True))
        self.assertLess(elapsed, 8.0)

    def test_sem_pesquisar_opinion_does_not_use_web(self) -> None:
        state = AgentOrchestrator().run(AgentChatRequest(message="Sem pesquisar, o que acha do Neymar?"))
        self.assertIn(state.mode, {"FAST", "BALANCED"})
        self.assertFalse(state.web_used)
        self.assertNotIn("web_search", state.selected_tools)

    def test_fast_mode_sends_32_tokens_to_provider(self) -> None:
        provider = FakeFastProvider()
        with patch("app.agent.orchestrator._instant_fast_reply", return_value=None), patch(
            "app.agent.orchestrator.ModelRouter.provider_chain_for_mode", return_value=[provider]
        ):
            state = AgentOrchestrator().run(AgentChatRequest(message="oi"))
        self.assertEqual(state.mode, "FAST")
        self.assertEqual(provider.max_tokens_seen, 32)


if __name__ == "__main__":
    unittest.main()
