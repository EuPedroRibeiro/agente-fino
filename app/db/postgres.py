from __future__ import annotations

import json
import hashlib
import time
from typing import Any
from uuid import uuid4

from app.agent.memory_stores.sqlite_memory import now_iso
from app.core.config import settings


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    provider_used TEXT,
    model_used TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    mode TEXT,
    intent TEXT,
    tools_used TEXT,
    web_sources_count INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT,
    username TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    revoked_at DOUBLE PRECISION,
    last_seen_at DOUBLE PRECISION,
    user_agent TEXT,
    ip_address TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS long_term_memories (
    id BIGSERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.6,
    pinned BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    last_used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_long_term_memories_category ON long_term_memories(category);
CREATE INDEX IF NOT EXISTS idx_long_term_memories_pinned ON long_term_memories(pinned, archived);
CREATE INDEX IF NOT EXISTS idx_long_term_memories_updated ON long_term_memories(updated_at);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    path TEXT,
    method TEXT,
    client TEXT,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type);

CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    reset_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id BIGSERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def get_postgres_connection(database_url: str | None = None):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("psycopg nao instalado. Instale requirements.txt para usar DATABASE_URL.") from exc
    return psycopg.connect(database_url or settings.database_url, row_factory=dict_row)


def init_postgres_schema(database_url: str | None = None) -> None:
    with get_postgres_connection(database_url) as connection:
        for statement in _schema_statements(POSTGRES_SCHEMA):
            connection.execute(statement)
        connection.commit()
    ensure_admin_user()


def ensure_admin_user() -> None:
    if not settings.database_url or not settings.admin_user:
        return
    now = now_iso()
    with get_postgres_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'admin', %s, %s)
            ON CONFLICT (username) DO UPDATE
            SET email = EXCLUDED.email,
                password_hash = COALESCE(NULLIF(EXCLUDED.password_hash, ''), users.password_hash),
                updated_at = EXCLUDED.updated_at
            """,
            (
                f"user-{hashlib.sha256(settings.admin_user.encode('utf-8')).hexdigest()[:16]}",
                settings.admin_user,
                settings.admin_email or None,
                settings.admin_password_hash or None,
                now,
                now,
            ),
        )
        connection.commit()


def create_session_record(
    *,
    token: str,
    csrf_token: str,
    username: str,
    expires_at: float,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> None:
    now = time.time()
    token_hash = hash_token(token)
    with get_postgres_connection() as connection:
        user_row = connection.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()
        connection.execute(
            """
            INSERT INTO sessions
            (token_hash, user_id, username, csrf_token, created_at, expires_at, revoked_at, last_seen_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, %s)
            """,
            (
                token_hash,
                user_row["id"] if user_row else None,
                username,
                csrf_token,
                now,
                expires_at,
                now,
                user_agent,
                ip_address,
            ),
        )
        connection.commit()


def get_session_record(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    now = time.time()
    with get_postgres_connection() as connection:
        row = connection.execute(
            """
            SELECT token_hash, user_id, username, csrf_token, created_at, expires_at, revoked_at, last_seen_at
            FROM sessions
            WHERE token_hash = %s AND revoked_at IS NULL AND expires_at >= %s
            """,
            (hash_token(token), now),
        ).fetchone()
        if row:
            connection.execute("UPDATE sessions SET last_seen_at = %s WHERE token_hash = %s", (now, row["token_hash"]))
            connection.commit()
    return dict(row) if row else None


def revoke_session_record(token: str | None) -> bool:
    if not token:
        return False
    with get_postgres_connection() as connection:
        cursor = connection.execute(
            "UPDATE sessions SET revoked_at = %s WHERE token_hash = %s AND revoked_at IS NULL",
            (time.time(), hash_token(token)),
        )
        connection.commit()
        return cursor.rowcount > 0


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def insert_audit_event(event: dict[str, Any]) -> None:
    with get_postgres_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit_events (id, created_at, event_type, severity, path, method, client, details_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                event["id"],
                event["created_at"],
                event["event_type"],
                event["severity"],
                event.get("path"),
                event.get("method"),
                event.get("client"),
                json.dumps(event.get("details") or {}, ensure_ascii=False, default=str),
            ),
        )
        connection.commit()


def list_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    with get_postgres_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, event_type, severity, path, method, client, details_json
            FROM audit_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["details"] = json.loads(item.pop("details_json") or "{}")
        except json.JSONDecodeError:
            item["details"] = {}
        events.append(item)
    return events


def allow_postgres_rate_limit(key: str, *, limit: int, window_seconds: int = 60, now: float | None = None) -> bool:
    now = now or time.time()
    with get_postgres_connection() as connection:
        with connection.transaction():
            row = connection.execute("SELECT key, count, reset_at FROM rate_limits WHERE key = %s FOR UPDATE", (key,)).fetchone()
            if not row or float(row["reset_at"]) <= now:
                connection.execute(
                    """
                    INSERT INTO rate_limits (key, count, reset_at, updated_at)
                    VALUES (%s, 1, %s, %s)
                    ON CONFLICT (key) DO UPDATE
                    SET count = 1, reset_at = EXCLUDED.reset_at, updated_at = EXCLUDED.updated_at
                    """,
                    (key, now + window_seconds, now),
                )
                return True
            if int(row["count"]) >= limit:
                connection.execute("UPDATE rate_limits SET updated_at = %s WHERE key = %s", (now, key))
                return False
            connection.execute("UPDATE rate_limits SET count = count + 1, updated_at = %s WHERE key = %s", (now, key))
            return True


class PostgresConversationRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return get_postgres_connection(self.database_url)

    def init(self) -> None:
        init_postgres_schema(self.database_url)

    def ensure_conversation(self, conversation_id: str, *, title: str | None = None) -> dict[str, Any]:
        now = now_iso()
        with self._connect() as connection:
            row = connection.execute("SELECT id, title, created_at, updated_at, provider_used, model_used, message_count FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
            if not row:
                connection.execute(
                    """
                    INSERT INTO conversations (id, title, created_at, updated_at, provider_used, model_used, message_count)
                    VALUES (%s, %s, %s, %s, NULL, NULL, 0)
                    """,
                    (conversation_id, title or "Nova conversa", now, now),
                )
                connection.commit()
                row = connection.execute("SELECT id, title, created_at, updated_at, provider_used, model_used, message_count FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
            elif title and row["title"] == "Nova conversa":
                connection.execute("UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s", (title, now, conversation_id))
                connection.commit()
                row = connection.execute("SELECT id, title, created_at, updated_at, provider_used, model_used, message_count FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
        return dict(row)

    def create_conversation(self, title: str | None = None) -> dict[str, Any]:
        return self.ensure_conversation(str(uuid4()), title=title or "Nova conversa")

    def list_conversations(self, query: str | None = None, limit: int = 60) -> list[dict[str, Any]]:
        pattern = f"%{query or ''}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at, provider_used, model_used, message_count
                FROM conversations
                WHERE archived_at IS NULL AND title ILIKE %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (pattern, max(1, min(limit, 200))),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, created_at, updated_at, provider_used, model_used, message_count
                FROM conversations
                WHERE id = %s AND archived_at IS NULL
                """,
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_conversation(self, conversation_id: str, title: str) -> dict[str, Any]:
        now = now_iso()
        with self._connect() as connection:
            cursor = connection.execute("UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s", (title.strip() or "Sem titulo", now, conversation_id))
            connection.commit()
            if cursor.rowcount == 0:
                raise KeyError("Conversa nao encontrada.")
        return self.get_conversation(conversation_id) or {}

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("UPDATE conversations SET archived_at = %s WHERE id = %s", (now_iso(), conversation_id))
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
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, created_at, provider, model, intent, tools_used, web_sources_count, latency_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
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
            ).fetchone()
            connection.execute(
                """
                UPDATE conversations
                SET updated_at = %s, provider_used = COALESCE(%s, provider_used), model_used = COALESCE(%s, model_used),
                    message_count = (SELECT COUNT(*) FROM messages WHERE conversation_id = %s)
                WHERE id = %s
                """,
                (now, provider if role == "assistant" else None, model if role == "assistant" else None, conversation_id, conversation_id),
            )
            connection.commit()
            return self.get_message(int(row["id"])) or {}

    def get_message(self, message_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, provider, model, intent, tools_used, web_sources_count, latency_ms
                FROM messages
                WHERE id = %s
                """,
                (message_id,),
            ).fetchone()
        return _message_row(row) if row else None

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, provider, model, intent, tools_used, web_sources_count, latency_ms
                FROM messages
                WHERE conversation_id = %s
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


def _schema_statements(schema: str) -> list[str]:
    return [statement.strip() for statement in schema.split(";") if statement.strip()]
