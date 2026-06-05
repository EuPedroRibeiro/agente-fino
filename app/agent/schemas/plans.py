from __future__ import annotations

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    order: int
    title: str
    detail: str
    reversible: bool = True
    tool: str | None = None


class Plan(BaseModel):
    objective: str
    assumptions: list[str] = Field(default_factory=list)
    required_context: list[str] = Field(default_factory=list)
    web_needed: bool = False
    tools_needed: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reversible_first: bool = True
    user_confirmation_required: bool = False
    steps: list[PlanStep] = Field(default_factory=list)
