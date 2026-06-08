from __future__ import annotations

from typing import Any

from app.agent.state import AgentState


def decision_metadata(decision: Any) -> dict[str, Any]:
    return {
        "router": decision.router,
        "reason": decision.reason,
        "intent": decision.intent,
        "execution_intent": decision.execution_intent,
        "mode": decision.mode,
        "confidence": decision.confidence,
        "risk_level": decision.risk_level,
        "selected_tools": decision.selected_tools,
        "blocked_tools": decision.blocked_tools,
        "web_needed": decision.web_needed,
        "rag_needed": decision.rag_needed,
        "memory_needed": decision.memory_needed,
        "requires_confirmation": decision.requires_confirmation,
    }


def apply_decision(state: AgentState, decision: Any) -> AgentState:
    state.system_context["intelligence"] = decision_metadata(decision)
    return state
