from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Reliability = Literal["high", "medium", "low", "unknown"]


class EvidenceItem(BaseModel):
    source_type: str
    title: str
    content: str
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)


class SourceCitation(BaseModel):
    title: str
    url: str
    domain: str
    reliability: Reliability = "unknown"
    used_for: str = "referencia tecnica"
    excerpt: str = ""
    fetched_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    source_status: str = "lida"
