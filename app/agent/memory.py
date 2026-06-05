from __future__ import annotations

from app.agent.memory_policy import should_auto_save
from app.agent.memory_router import route_memory_intent
from app.agent.memory_store import SmartMemoryStore
from app.agent.memory_stores import sqlite_memory
from app.core.config import settings


class AgentMemory:
    def __init__(self) -> None:
        self.smart_store = SmartMemoryStore()

    def remember_interaction(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        agent_response: str,
        category: str,
        confidence: float,
        risk_level: str,
        web_used: bool,
    ) -> None:
        if _use_postgres_memory():
            return
        sqlite_memory.save_conversation(
            user_id=user_id,
            session_id=conversation_id,
            user_message=user_message,
            agent_response=agent_response,
            category=category,
            confidence=confidence,
            risk_level=risk_level,
            web_used=web_used,
        )
        if category in {"open_world", "system", "math"}:
            return
        if confidence >= 0.7 and risk_level in {"low", "medium"}:
            sqlite_memory.save_memory(
                user_id=user_id,
                memory_type="resolved_or_relevant",
                title=f"Caso {category}",
                content=f"Pergunta: {user_message}\nResposta: {agent_response[:1200]}",
                tags=[category],
                importance=2,
                source="conversation",
            )

    def search(self, user_id: str, query: str, limit: int = 8) -> list[dict]:
        smart = [{"type": "long_term_memory", **item} for item in self.smart_store.search(query, limit=limit)]
        if _use_postgres_memory():
            return smart
        memories = sqlite_memory.search_memory(user_id, query, limit=limit)
        conversations = sqlite_memory.search_conversations(user_id, query, limit=limit)
        return smart + [
            {"type": "memory", **item}
            for item in memories
        ] + [
            {"type": "conversation", **item}
            for item in conversations
        ]

    def recent_conversation_turns(self, user_id: str, conversation_id: str, limit: int = 4) -> list[dict]:
        if _use_postgres_memory():
            return []
        return sqlite_memory.recent_conversation_turns(user_id, conversation_id, limit=limit)

    def list(self, user_id: str, limit: int = 50) -> list[dict]:
        return self.smart_store.list(limit=limit)

    def delete(self, memory_id: int) -> bool:
        return self.smart_store.delete(memory_id)

    def save_note(self, user_id: str, title: str, content: str, tags: list[str] | None = None) -> int:
        routed = route_memory_intent(content)
        category = routed.get("category") or "user_preferences"
        value = routed.get("value") or content
        if not should_auto_save(category, value, explicit=True):
            category = "do_not_remember"
        item = self.smart_store.create(category=category, key=title, value=value, source="user", confidence=0.9, pinned=False)
        return int(item["id"])


def _use_postgres_memory() -> bool:
    return settings.db_engine == "postgres" and bool(settings.database_url)
