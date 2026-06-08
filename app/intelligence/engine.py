from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.intelligence.confidence import adjusted_confidence
from app.intelligence.fallback import casual_reply, fallback_answer, greeting_reply
from app.intelligence.intent_router import FinoIntentRouter
from app.intelligence.memory_context import memory_requirement
from app.intelligence.observability import record_decision
from app.intelligence.planner import build_safe_plan
from app.intelligence.safety_router import assess_safety
from app.intelligence.tool_registry import ToolRegistry


class IntelligenceDecision(BaseModel):
    intent: str
    execution_intent: str
    category: str
    mode: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: str
    router: str
    reason: str
    selected_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    web_needed: bool = False
    rag_needed: bool = False
    memory_needed: bool = False
    requires_confirmation: bool = False
    answer_directly: bool = False
    direct_answer: str | None = None
    fallback_answer: str
    plan: Any = None
    route: dict[str, Any] = Field(default_factory=dict)


class FinoIntelligenceEngine:
    def __init__(self, *, router: FinoIntentRouter | None = None, tools: ToolRegistry | None = None) -> None:
        self.router = router or FinoIntentRouter()
        self.tools = tools or ToolRegistry()

    def decide(self, message: str, conversation_context: dict[str, Any] | None = None) -> IntelligenceDecision:
        try:
            return self._decide(message, conversation_context)
        except Exception:
            decision = IntelligenceDecision(
                intent="unknown",
                execution_intent="unknown",
                category="system",
                mode="SAFE_ERROR",
                confidence=0.2,
                risk_level="low",
                router="fino-rule-router-fallback",
                reason="O roteador deterministico encontrou uma falha interna e aplicou fallback seguro.",
                selected_tools=[],
                blocked_tools=[],
                web_needed=False,
                rag_needed=False,
                memory_needed=False,
                requires_confirmation=False,
                answer_directly=False,
                direct_answer=None,
                fallback_answer=fallback_answer("unknown", message),
                plan=None,
                route={"intent": "unknown", "category": "system"},
            )
            record_decision(decision)
            return decision

    def _decide(self, message: str, conversation_context: dict[str, Any] | None = None) -> IntelligenceDecision:
        intent_route = self.router.route(message)
        candidates = self.tools.select(intent_route.execution_intent, intent_route.route)
        allowed, blocked = self.tools.authorize(candidates, intent_route.confidence)
        safety = assess_safety(intent_route.execution_intent, allowed)
        confidence = adjusted_confidence(
            intent_route.confidence,
            blocked_tools=blocked,
            needs_clarification=intent_route.execution_intent in {"clarification_needed", "unknown"},
        )
        selected_tools = [tool.name for tool in allowed]
        web_needed = bool(intent_route.route.get("web_needed")) or intent_route.execution_intent in {
            "web_research",
            "deep_web_research",
        }
        rag_needed = intent_route.execution_intent == "rag_search"
        memory = memory_requirement(intent_route.execution_intent)
        direct_answer = self._direct_answer(intent_route.execution_intent, message)
        mode = self._mode_for(intent_route.execution_intent, selected_tools, web_needed)
        decision = IntelligenceDecision(
            intent=intent_route.intent,
            execution_intent=intent_route.execution_intent,
            category=intent_route.category,
            mode=mode,
            confidence=confidence,
            risk_level=safety["risk_level"],
            router=intent_route.router,
            reason=intent_route.reason,
            selected_tools=selected_tools,
            blocked_tools=blocked,
            web_needed=web_needed,
            rag_needed=rag_needed,
            memory_needed=memory["needed"],
            requires_confirmation=safety["requires_confirmation"],
            answer_directly=direct_answer is not None,
            direct_answer=direct_answer,
            fallback_answer=fallback_answer(intent_route.intent, message),
            plan=build_safe_plan(
                intent_route.intent,
                selected_tools,
                web_needed=web_needed,
                requires_confirmation=safety["requires_confirmation"],
            ),
            route=intent_route.route,
        )
        record_decision(decision)
        return decision

    @staticmethod
    def _direct_answer(intent: str, message: str) -> str | None:
        if intent == "greeting":
            return greeting_reply(message)
        if intent == "casual_chat":
            return casual_reply(message)
        if intent == "identity_query":
            return "Sou o Agente Fino, sua IA para pensar, organizar e resolver."
        return None

    @staticmethod
    def _mode_for(intent: str, selected_tools: list[str], web_needed: bool) -> str:
        if intent in {"greeting", "casual_chat", "identity_query", "time_query", "date_query"} and not selected_tools:
            return "FAST"
        if intent in {
            "disk_space",
            "storage_status",
            "ram_status",
            "cpu_status",
            "local_ip_status",
            "uptime_status",
            "spooler_status",
            "simple_pc_metric",
            "folder_size",
            "file_count",
            "folder_usage_top",
            "language_correction",
        }:
            return "LOCAL_TOOL_FAST"
        if intent in {"pc_diagnostic", "deep_web_research"}:
            return "EXPERT"
        if web_needed or selected_tools:
            return "BALANCED"
        return "BALANCED"
