from __future__ import annotations

import time
from typing import Any

from app.agent.fusion.engine import FusionEngine
from app.agent.intelligence.model_selector import IntelligenceModelSelector
from app.agent.intelligence.state import IntelligenceState
from app.agent.intelligence.tool_router import tools_for_intent
from app.agent.intelligence.verifier import verify_answer
from app.agent.router import classify_message


class NexusKernel:
    def __init__(self, *, orchestrator: Any | None = None, model_selector: IntelligenceModelSelector | None = None) -> None:
        self.orchestrator = orchestrator
        self.model_selector = model_selector or IntelligenceModelSelector()
        self.fusion = FusionEngine()

    def run(self, message: str) -> IntelligenceState:
        started = time.perf_counter()
        classification = classify_message(message)
        intent = classification.get("intent", "general_question")
        tools = tools_for_intent(intent, message)
        provider, model, fallback_reason = self.model_selector.selected()
        decision = self.fusion.choose_mode(
            intent=intent,
            tools=tools,
            web_needed="web_search" in tools,
            online_available=self.model_selector.online_available(),
        )
        answer = self._answer(message, intent, tools)
        verifier_result = verify_answer(answer, intent=intent, tools=tools)
        return IntelligenceState(
            user_message=message,
            intent=intent,
            mode=decision.mode,
            selected_provider=provider,
            selected_model=model,
            tools_used=tools,
            web_used="web_search" in tools,
            verifier_result=verifier_result,
            final_answer=answer,
            confidence=0.9 if verifier_result["approved"] else 0.55,
            latency_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason=fallback_reason,
        )

    def _answer(self, message: str, intent: str, tools: list[str]) -> str:
        if self.orchestrator:
            try:
                response = self.orchestrator.chat(message=message, intent=intent, tools=tools)
                if isinstance(response, str):
                    return response
                if isinstance(response, dict):
                    return response.get("answer") or response.get("final_answer") or ""
            except Exception:
                pass
        if "disk_usage" in tools:
            return "Vou listar as pastas que mais ocupam espaço usando a ferramenta disk_usage."
        if "analyze_pc" in tools:
            return "Vou analisar o PC com ferramentas locais de leitura e retornar gargalos e proximos passos."
        if intent == "greeting":
            return "Oi! Estou por aqui. Pode mandar a proxima."
        return "Entendi. Vou responder de forma direta e usar ferramentas ou web quando isso realmente ajudar."
