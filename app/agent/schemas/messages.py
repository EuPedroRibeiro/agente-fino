from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    use_web: bool = True
    include_system_context: bool = True
    mode: str = "auto"
    conversation_id: str | None = None
    user_id: str = "local-user"


class ResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    official_first: bool = True
    max_results: int = Field(default=8, ge=1, le=20)


class DeepResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    depth: str = "normal"
    official_first: bool = True


class ConfirmActionRequest(BaseModel):
    pending_action_id: str
    confirm: bool


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)


class DiskUsageRequest(BaseModel):
    root: str | None = None
    limit: int = Field(default=10, ge=1, le=30)
    max_depth: int = Field(default=3, ge=1, le=5)
    max_seconds: float = Field(default=8, ge=1, le=20)


class SmartMemoryCreateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=4000)
    category: str | None = None
    key: str | None = None
    source: str = "user"
    confidence: float = Field(default=0.9, ge=0, le=1)
    pinned: bool = False


class SmartMemoryUpdateRequest(BaseModel):
    value: str | None = Field(default=None, min_length=1, max_length=4000)
    category: str | None = None
    key: str | None = None
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    pinned: bool | None = None
    archived: bool | None = None


class MemoryPinRequest(BaseModel):
    pinned: bool = True


class MemoryArchiveRequest(BaseModel):
    archived: bool = True


class PersonalityPatchRequest(BaseModel):
    tone: str | None = None
    detail_level: str | None = None
    style: str | None = None
    technical_default: str | None = None
    emoji_usage: str | None = None
    posture: str | None = None
    auto_web: bool | None = None
    auto_memory: bool | None = None
    response_preference: str | None = None


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
