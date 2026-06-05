from __future__ import annotations

from app.agent.evaluators.hallucination_guard import HallucinationGuard
from app.agent.evaluators.source_checker import SourceChecker


class Critic:
    def __init__(self) -> None:
        self.hallucination_guard = HallucinationGuard()
        self.source_checker = SourceChecker()

    def review(self, state) -> dict:
        hallucination = self.hallucination_guard.check(
            answer=state.draft_answer,
            web_used=state.web_used,
            citations=state.citations,
            evidence=state.evidence,
        )
        sources = self.source_checker.check(state.citations)
        warnings = list(hallucination["warnings"])
        if not sources["ok"]:
            warnings.append("Algumas fontes nao foram lidas; elas nao devem ser tratadas como evidencia forte.")
        confidence = max(0.05, min(0.98, state.confidence + hallucination["confidence_delta"]))
        return {"warnings": warnings, "confidence": confidence}
