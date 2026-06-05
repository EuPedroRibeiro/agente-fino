from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class DatabaseStatus:
    engine: str
    configured: bool
    persistent: bool
    message: str


class ConversationRepository(Protocol):
    def init(self) -> None: ...
    def create_conversation(self, title: str | None = None) -> dict[str, Any]: ...
    def ensure_conversation(self, conversation_id: str, *, title: str | None = None) -> dict[str, Any]: ...
    def list_conversations(self, query: str | None = None, limit: int = 60) -> list[dict[str, Any]]: ...
    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None: ...
    def update_conversation(self, conversation_id: str, title: str) -> dict[str, Any]: ...
    def delete_conversation(self, conversation_id: str) -> bool: ...
    def add_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        intent: str | None = None,
        tools_used: list[str] | None = None,
        web_sources_count: int = 0,
        latency_ms: int | None = None,
    ) -> dict[str, Any]: ...
    def get_message(self, message_id: int) -> dict[str, Any] | None: ...
    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]: ...

