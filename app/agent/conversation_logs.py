from __future__ import annotations

from typing import Any

from app.db import get_conversation_repository
from app.security.documents import mask_personal_documents


def init_conversation_logs() -> None:
    get_conversation_repository().init()


def ensure_conversation(conversation_id: str, *, title: str | None = None) -> dict[str, Any]:
    return get_conversation_repository().ensure_conversation(conversation_id, title=title)


def create_conversation(title: str | None = None) -> dict[str, Any]:
    return get_conversation_repository().create_conversation(title)


def list_conversations(query: str | None = None, limit: int = 60) -> list[dict[str, Any]]:
    return get_conversation_repository().list_conversations(query=query, limit=limit)


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    return get_conversation_repository().get_conversation(conversation_id)


def update_conversation(conversation_id: str, title: str) -> dict[str, Any]:
    return get_conversation_repository().update_conversation(conversation_id, title)


def delete_conversation(conversation_id: str) -> bool:
    return get_conversation_repository().delete_conversation(conversation_id)


def add_message(
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
) -> dict[str, Any]:
    return get_conversation_repository().add_message(
        conversation_id=conversation_id,
        role=role,
        content=mask_personal_documents(content),
        provider=provider,
        model=model,
        intent=intent,
        tools_used=tools_used,
        web_sources_count=web_sources_count,
        latency_ms=latency_ms,
    )


def get_message(message_id: int) -> dict[str, Any] | None:
    return get_conversation_repository().get_message(message_id)


def list_messages(conversation_id: str) -> list[dict[str, Any]]:
    return get_conversation_repository().list_messages(conversation_id)
