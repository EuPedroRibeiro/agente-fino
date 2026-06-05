from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.agent.schemas.evidence import EvidenceItem, SourceCitation
from app.agent.schemas.plans import Plan


class AgentState(BaseModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "local-user"
    user_message: str
    normalized_message: str = ""
    intent: str = "general"
    category: str = "general"
    mode: str = "OFFLINE"
    system_context: dict[str, Any] = Field(default_factory=dict)
    local_report: dict[str, Any] | None = None
    memory_context: list[dict[str, Any]] = Field(default_factory=list)
    rag_context: list[dict[str, Any]] = Field(default_factory=list)
    web_context: list[dict[str, Any]] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    plan: Plan | None = None
    draft_answer: str = ""
    verified_answer: str = ""
    final_answer: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    risk_level: str = "low"
    confidence: float = 0.5
    needs_confirmation: bool = False
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    language: str = "pt-BR"
    urgency: str = "normal"
    requested_action: bool = False
    web_used: bool = False
    web_needed: bool = False
    searched_at: str | None = None
    model_used: dict[str, Any] = Field(default_factory=dict)
    rag_status: dict[str, Any] = Field(default_factory=dict)
    web_status: dict[str, Any] = Field(default_factory=dict)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
