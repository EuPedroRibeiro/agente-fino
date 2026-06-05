from __future__ import annotations

import unittest

from app.agent.intelligence.kernel import NexusKernel
from app.agent.intelligence.model_selector import IntelligenceModelSelector


class OfflineSelector(IntelligenceModelSelector):
    def status(self) -> dict:
        return {"selected_provider": "local-rules", "selected_model": "deterministic-rules", "real_llm_enabled": False, "fallback_reason": "offline"}

    def online_available(self) -> bool:
        return False


class IntelligenceKernelTests(unittest.TestCase):
    def test_greeting_uses_fast_mode_without_tool(self) -> None:
        state = NexusKernel(model_selector=OfflineSelector()).run("Oi")
        self.assertEqual(state.mode, "FAST")
        self.assertEqual(state.tools_used, [])

    def test_analyze_pc_uses_expert_mode_and_tool(self) -> None:
        state = NexusKernel(model_selector=OfflineSelector()).run("Analise este PC")
        self.assertEqual(state.mode, "EXPERT")
        self.assertIn("analyze_pc", state.tools_used)

    def test_disk_usage_routes_to_disk_tool(self) -> None:
        state = NexusKernel(model_selector=OfflineSelector()).run("Quais pastas ocupam mais espaço?")
        self.assertEqual(state.mode, "EXPERT")
        self.assertIn("disk_usage", state.tools_used)


if __name__ == "__main__":
    unittest.main()
