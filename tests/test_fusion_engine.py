from __future__ import annotations

import unittest

from app.agent.fusion.engine import FusionEngine
from app.routes import agent as agent_routes


class FusionEngineTests(unittest.TestCase):
    def test_fast_for_simple_chat(self) -> None:
        decision = FusionEngine().choose_mode(intent="greeting", tools=[], online_available=True)
        self.assertEqual(decision.mode, "FAST")

    def test_expert_for_tools(self) -> None:
        decision = FusionEngine().choose_mode(intent="pc_diagnostic", tools=["analyze_pc"], online_available=True)
        self.assertEqual(decision.mode, "EXPERT")
        self.assertTrue(decision.use_verifier)

    def test_mode_logic_does_not_collapse_when_provider_offline(self) -> None:
        greeting = FusionEngine().choose_mode(intent="greeting", tools=[], online_available=False)
        expert = FusionEngine().choose_mode(intent="pc_diagnostic", tools=["analyze_pc"], online_available=False)
        self.assertEqual(greeting.mode, "FAST")
        self.assertEqual(expert.mode, "EXPERT")
        self.assertEqual(expert.max_models, 1)

    def test_fusion_status_endpoint_shape(self) -> None:
        status = agent_routes.agent_fusion_status()
        self.assertTrue(status["enabled"])
        self.assertIn("active_provider", status)


if __name__ == "__main__":
    unittest.main()
