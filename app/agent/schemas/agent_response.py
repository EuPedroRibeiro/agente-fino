from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.schemas.evidence import EvidenceItem, SourceCitation
from app.agent.schemas.plans import Plan


class AgentResponse(BaseModel):
    conversation_id: str
    answer: str
    final_answer: str
    intent: str
    category: str
    mode: str
    web_used: bool = False
    searched_at: str | None = None
    sources: list[SourceCitation] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    plan: Plan | None = None
    safe_actions: list[dict[str, Any]] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    model_used: dict[str, Any] = Field(default_factory=dict)
    rag_status: dict[str, Any] = Field(default_factory=dict)
    web_status: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"
    confidence: float = 0.5
    needs_confirmation: bool = False
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    intelligence: dict[str, Any] = Field(default_factory=dict)
