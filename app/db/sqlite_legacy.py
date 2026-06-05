from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.agent.memory_stores.sqlite_memory import now_iso
from app.core.logging_db import get_connection


CONVERSATION_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    provider_used TEXT,
    model_used TEXT,
    message_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    intent TEXT,
    tools_used TEXT,
    web_sources_count INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);
"""


class SQLiteLegacyConversationRepository:
    def init(self) -> None:
        with get_connection() as connection:
            connection.executescript(CONVERSATION_LOG_SCHEMA)
            connection.commit()

    def ensure_conversation(self, conversation_id: str, *, title: str | None = None) -> dict[str, Any]:
        now = now_iso()
        with get_connection() as connection:
            row = connection.execute("SELECT id, title, created_at, updated_at, provider_used, model_used, message_count FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if not row:
                connection.execute(
                    """
                    INSERT INTO conversations (id, title, created_at, updated_at, provider_used, model_used, message_count)
                    VALUES (?, ?, ?, ?, NULL, NULL, 0)
                    """,
                    (conversation_id, title or "Nova conversa", now, now),
                )
                connection.commit()
                row = connection.execute("SELECT id, title, created_at, updated_at, provider_used, model_used, message_count FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            elif title and row["title"] == "Nova conversa":
                connection.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?", (title, now, conversation_id))
                connection.commit()
                row = connection.execute("SELECT id, title, created_at, updated_at, provider_used, model_used, message_count FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return dict(row)

    def create_conversation(self, title: str | None = None) -> dict[str, Any]:
        return self.ensure_conversation(str(uuid4()), title=title or "Nova conversa")

    def list_conversations(self, query: str | None = None, limit: int = 60) -> list[dict[str, Any]]:
        pattern = f"%{query or ''}%"
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at, provider_used, model_used, message_count
                FROM conversations
                WHERE title LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (pattern, max(1, min(limit, 200))),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, title, created_at, updated_at, provider_used, model_used, message_count
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_conversation(self, conversation_id: str, title: str) -> dict[str, Any]:
        now = now_iso()
        with get_connection() as connection:
            cursor = connection.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?", (title.strip() or "Sem titulo", now, conversation_id))
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError("Conversa nao encontrada.")
        return self.get_conversation(conversation_id) or {}

    def delete_conversation(self, conversation_id: str) -> bool:
        with get_connection() as connection:
            connection.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            cursor = connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            connection.commit()
            return cursor.rowcount > 0

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
        self.ensure_conversation(conversation_id, title=_title_from_message(content) if role == "user" else None)
        now = now_iso()
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, created_at, provider, model, intent, tools_used, web_sources_count, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    content,
                    now,
                    provider,
                    model,
                    intent,
                    json.dumps(tools_used or [], ensure_ascii=False),
                    int(web_sources_count),
                    latency_ms,
                ),
            )
            connection.execute(
                """
                UPDATE conversations
                SET updated_at = ?, provider_used = COALESCE(?, provider_used), model_used = COALESCE(?, model_used),
                    message_count = (SELECT COUNT(*) FROM messages WHERE conversation_id = ?)
                WHERE id = ?
                """,
                (now, provider if role == "assistant" else None, model if role == "assistant" else None, conversation_id, conversation_id),
            )
            connection.commit()
            message_id = int(cursor.lastrowid)
        return self.get_message(message_id) or {}

    def get_message(self, message_id: int) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, provider, model, intent, tools_used, web_sources_count, latency_ms
                FROM messages
                WHERE id = ?
                """,
                (message_id,),
            ).fetchone()
        return _message_row(row) if row else None

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, provider, model, intent, tools_used, web_sources_count, latency_ms
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [_message_row(row) for row in rows]


def _message_row(row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["tools_used"] = json.loads(item.get("tools_used") or "[]")
    except json.JSONDecodeError:
        item["tools_used"] = []
    return item


def _title_from_message(content: str) -> str:
    compact = " ".join(content.strip().split())
    if not compact:
        return "Nova conversa"
    return compact[:54] + ("..." if len(compact) > 54 else "")

