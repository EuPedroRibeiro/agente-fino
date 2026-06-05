from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


RiskLevel = Literal["low", "medium", "high", "blocked"]


class ToolDefinition(BaseModel):
    name: str
    description: str
    category: str
    risk_level: RiskLevel = "low"
    requires_admin: bool = False
    requires_confirmation: bool = False
    function_path: str
    enabled: bool = True


class ToolCallResult(BaseModel):
    name: str
    success: bool
    message: str
    data: Any = None
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False
