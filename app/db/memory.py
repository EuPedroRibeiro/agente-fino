from __future__ import annotations

import json
from threading import RLock
from typing import Any
from uuid import uuid4

from app.agent.memory_stores.sqlite_memory import now_iso


class MemoryConversationRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._conversations: dict[str, dict[str, Any]] = {}
        self._messages: dict[int, dict[str, Any]] = {}
        self._next_message_id = 1

    def init(self) -> None:
        return None

    def ensure_conversation(self, conversation_id: str, *, title: str | None = None) -> dict[str, Any]:
        now = now_iso()
        with self._lock:
            row = self._conversations.get(conversation_id)
            if not row:
                row = {
                    "id": conversation_id,
                    "title": title or "Nova conversa",
                    "created_at": now,
                    "updated_at": now,
                    "provider_used": None,
                    "model_used": None,
                    "message_count": 0,
                }
                self._conversations[conversation_id] = row
            elif title and row["title"] == "Nova conversa":
                row["title"] = title
                row["updated_at"] = now
            return dict(row)

    def create_conversation(self, title: str | None = None) -> dict[str, Any]:
        return self.ensure_conversation(str(uuid4()), title=title or "Nova conversa")

    def list_conversations(self, query: str | None = None, limit: int = 60) -> list[dict[str, Any]]:
        q = (query or "").lower()
        with self._lock:
            rows = [dict(row) for row in self._conversations.values() if q in row["title"].lower()]
        rows.sort(key=lambda item: item["updated_at"], reverse=True)
        return rows[: max(1, min(limit, 200))]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conversations.get(conversation_id)
            return dict(row) if row else None

    def update_conversation(self, conversation_id: str, title: str) -> dict[str, Any]:
        with self._lock:
            row = self._conversations.get(conversation_id)
            if not row:
                raise KeyError("Conversa nao encontrada.")
            row["title"] = title.strip() or "Sem titulo"
            row["updated_at"] = now_iso()
            return dict(row)

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            existed = self._conversations.pop(conversation_id, None) is not None
            for message_id in [mid for mid, msg in self._messages.items() if msg["conversation_id"] == conversation_id]:
                self._messages.pop(message_id, None)
            return existed

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
    ) -> dict[str, Any]:
        with self._lock:
            self.ensure_conversation(conversation_id, title=_title_from_message(content) if role == "user" else None)
            now = now_iso()
            message_id = self._next_message_id
            self._next_message_id += 1
            item = {
                "id": message_id,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "created_at": now,
                "provider": provider,
                "model": model,
                "intent": intent,
                "tools_used": tools_used or [],
                "web_sources_count": int(web_sources_count),
                "latency_ms": latency_ms,
            }
            self._messages[message_id] = item
            conversation = self._conversations[conversation_id]
            conversation["updated_at"] = now
            conversation["message_count"] = sum(1 for msg in self._messages.values() if msg["conversation_id"] == conversation_id)
            if role == "assistant":
                conversation["provider_used"] = provider or conversation.get("provider_used")
                conversation["model_used"] = model or conversation.get("model_used")
            return dict(item)

    def get_message(self, message_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._messages.get(message_id)
            return dict(row) if row else None

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = [dict(row) for row in self._messages.values() if row["conversation_id"] == conversation_id]
        rows.sort(key=lambda item: int(item["id"]))
        return rows


def _title_from_message(content: str) -> str:
    compact = " ".join(content.strip().split())
    if not compact:
        return "Nova conversa"
    return compact[:54] + ("..." if len(compact) > 54 else "")

