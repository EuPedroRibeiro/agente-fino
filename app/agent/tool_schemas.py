from __future__ import annotations

from pydantic import BaseModel


class EmptyToolInput(BaseModel):
    pass


class SearchKnowledgeInput(BaseModel):
    query: str
    category: str | None = None
    limit: int = 6


class SearchWebInput(BaseModel):
    query: str
    max_results: int = 8
    official_first: bool = True
