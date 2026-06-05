from __future__ import annotations

import time
from contextlib import contextmanager

from app.agent.memory_stores.sqlite_memory import record_agent_run
from app.core.config import settings


@contextmanager
def timed_step(name: str, timings: dict[str, int]):
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = int((time.perf_counter() - started) * 1000)


def record_run(state, latency_ms: int, success: bool, error: str | None = None) -> None:
    record_agent_run(
        user_id=state.user_id,
        mode=state.mode,
        intent=state.intent,
        category=state.category,
        web_used=state.web_used,
        tools_used=state.selected_tools,
        confidence=state.confidence,
        risk_level=state.risk_level,
        latency_ms=latency_ms,
        success=success,
        error=error,
        timings=state.timings_ms,
    )


def langfuse_status() -> dict:
    return {
        "enabled": settings.langfuse_enabled,
        "host": settings.langfuse_host or None,
        "adapter_ready": True,
        "integrated": False,
    }
