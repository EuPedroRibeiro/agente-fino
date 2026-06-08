from __future__ import annotations

from app.intelligence.tool_registry import IntelligenceTool


def assess_safety(intent: str, tools: list[IntelligenceTool]) -> dict:
    risk_order = {"low": 0, "medium": 1, "high": 2, "blocked": 3}
    risk = max((tool.risk for tool in tools), key=lambda item: risk_order[item], default="low")
    requires_confirmation = any(tool.requires_confirmation for tool in tools)
    if intent == "safe_refusal":
        risk = "blocked"
    return {
        "risk_level": risk,
        "requires_confirmation": requires_confirmation,
        "safe_to_execute": risk != "blocked" and not requires_confirmation,
    }
