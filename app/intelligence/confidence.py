from __future__ import annotations


def adjusted_confidence(base: float, *, blocked_tools: list[str], needs_clarification: bool = False) -> float:
    value = float(base)
    if blocked_tools:
        value -= min(0.25, len(blocked_tools) * 0.08)
    if needs_clarification:
        value = min(value, 0.6)
    return max(0.0, min(1.0, round(value, 3)))
