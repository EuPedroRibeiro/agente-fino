from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntelligenceState(BaseModel):
    user_message: str
    intent: str = "general_question"
    risk_level: str = "low"
    mode: str = "BALANCED"
    selected_provider: str = "local-rules"
    selected_model: str = "deterministic-rules"
    memory_used: bool = False
    rag_used: bool = False
    web_used: bool = False
    tools_used: list[str] = Field(default_factory=list)
    verifier_result: dict[str, Any] = Field(default_factory=dict)
    final_answer: str = ""
    confidence: float = 0.5
    latency_ms: int = 0
    fallback_reason: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
