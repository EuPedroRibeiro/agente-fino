from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app.core.logging_db import get_connection


AGENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    category TEXT,
    confidence REAL,
    risk_level TEXT,
    web_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    importance INTEGER NOT NULL DEFAULT 1,
    source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machine_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname TEXT NOT NULL UNIQUE,
    os TEXT,
    cpu TEXT,
    ram TEXT,
    disk TEXT,
    gpu TEXT,
    printers_json TEXT,
    network_json TEXT,
    last_report_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS web_research_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL UNIQUE,
    results_json TEXT NOT NULL,
    sources_json TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    source TEXT,
    version TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    tags TEXT,
    score_boost REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    mode TEXT,
    intent TEXT,
    category TEXT,
    web_used INTEGER NOT NULL DEFAULT 0,
    tools_used TEXT,
    confidence REAL,
    risk_level TEXT,
    latency_ms INTEGER,
    success INTEGER NOT NULL DEFAULT 1,
    error TEXT,
    timings_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    conversation_id TEXT,
    provider TEXT NOT NULL,
    model TEXT,
    used_model INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    success INTEGER NOT NULL DEFAULT 1,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_pending_actions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    action_name TEXT NOT NULL,
    payload_json TEXT,
    risk_level TEXT NOT NULL,
    requires_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def init_agent_storage() -> None:
    with get_connection() as connection:
        connection.executescript(AGENT_SCHEMA)
        _try_create_fts(connection)
        connection.commit()


def _try_create_fts(connection: sqlite3.Connection) -> None:
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts
            USING fts5(chunk_text, tags, content='knowledge_chunks', content_rowid='id')
            """
        )
    except sqlite3.OperationalError:
        return


def save_conversation(
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    agent_response: str,
    category: str,
    confidence: float,
    risk_level: str,
    web_used: bool,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO agent_conversations
            (user_id, session_id, user_message, agent_response, category, confidence, risk_level, web_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, session_id, user_message, agent_response, category, confidence, risk_level, int(web_used), now_iso()),
        )
        connection.commit()


def search_conversations(user_id: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
    pattern = f"%{query}%"
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, session_id, user_message, agent_response, category, confidence, risk_level, web_used, created_at
            FROM agent_conversations
            WHERE user_id = ? AND (user_message LIKE ? OR agent_response LIKE ?)
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, pattern, pattern, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def recent_conversation_turns(user_id: str, session_id: str, limit: int = 4) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_message, agent_response, category, confidence, created_at
            FROM agent_conversations
            WHERE user_id = ? AND session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, session_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def save_memory(
    *,
    user_id: str,
    memory_type: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    importance: int = 1,
    source: str = "agent",
) -> int:
    created_at = now_iso()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO agent_memory
            (user_id, memory_type, title, content, tags, importance, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, memory_type, title, content, json.dumps(tags or [], ensure_ascii=False), importance, source, created_at, created_at),
        )
        connection.commit()
        return int(cursor.lastrowid)


def search_memory(user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    pattern = f"%{query}%"
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, memory_type, title, content, tags, importance, source, created_at, updated_at
            FROM agent_memory
            WHERE user_id = ? AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
            """,
            (user_id, pattern, pattern, pattern, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_memory(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, memory_type, title, content, tags, importance, source, created_at, updated_at
            FROM agent_memory
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_memory(memory_id: int) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM agent_memory WHERE id = ?", (memory_id,))
        connection.commit()
        return cursor.rowcount > 0


def upsert_machine_profile(hostname: str, report: dict[str, Any]) -> None:
    summary = report.get("summary", {})
    now = now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO machine_profiles
            (hostname, os, cpu, ram, disk, gpu, printers_json, network_json, last_report_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(hostname) DO UPDATE SET
                os=excluded.os,
                cpu=excluded.cpu,
                ram=excluded.ram,
                disk=excluded.disk,
                gpu=excluded.gpu,
                printers_json=excluded.printers_json,
                network_json=excluded.network_json,
                last_report_json=excluded.last_report_json,
                updated_at=excluded.updated_at
            """,
            (
                hostname,
                summary.get("operating_system"),
                json.dumps(report.get("cpu"), ensure_ascii=False),
                json.dumps(report.get("memory"), ensure_ascii=False),
                json.dumps(report.get("disk"), ensure_ascii=False),
                json.dumps(report.get("gpu", None), ensure_ascii=False),
                json.dumps(report.get("printers"), ensure_ascii=False),
                json.dumps(report.get("network"), ensure_ascii=False),
                json.dumps(report, ensure_ascii=False),
                now,
            ),
        )
        connection.commit()


def get_cached_web_result(query: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT query, results_json, sources_json, created_at, expires_at
            FROM web_research_cache
            WHERE query = ? AND expires_at > ?
            """,
            (query, now_iso()),
        ).fetchone()
    if not row:
        return None
    return {
        "query": row["query"],
        "results": json.loads(row["results_json"]),
        "sources": json.loads(row["sources_json"] or "[]"),
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
    }


def save_cached_web_result(query: str, results: list[dict[str, Any]], sources: list[dict[str, Any]], ttl_minutes: int) -> None:
    created_at = now_iso()
    expires_at = (datetime.now().astimezone() + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO web_research_cache (query, results_json, sources_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(query) DO UPDATE SET
                results_json=excluded.results_json,
                sources_json=excluded.sources_json,
                created_at=excluded.created_at,
                expires_at=excluded.expires_at
            """,
            (query, json.dumps(results, ensure_ascii=False), json.dumps(sources, ensure_ascii=False), created_at, expires_at),
        )
        connection.commit()


def list_sources(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT query, sources_json, created_at, expires_at
            FROM web_research_cache
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "query": row["query"],
            "sources": json.loads(row["sources_json"] or "[]"),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }
        for row in rows
    ]


def record_agent_run(
    *,
    user_id: str,
    mode: str,
    intent: str,
    category: str,
    web_used: bool,
    tools_used: list[str],
    confidence: float,
    risk_level: str,
    latency_ms: int,
    success: bool,
    error: str | None,
    timings: dict[str, int],
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO agent_runs
            (user_id, mode, intent, category, web_used, tools_used, confidence, risk_level, latency_ms, success, error, timings_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                mode,
                intent,
                category,
                int(web_used),
                json.dumps(tools_used, ensure_ascii=False),
                confidence,
                risk_level,
                latency_ms,
                int(success),
                error,
                json.dumps(timings, ensure_ascii=False),
                now_iso(),
            ),
        )
        connection.commit()


def record_model_call(
    *,
    user_id: str,
    conversation_id: str,
    provider: str,
    model: str,
    used_model: bool,
    latency_ms: int,
    success: bool,
    error: str | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO agent_model_calls
            (user_id, conversation_id, provider, model, used_model, latency_ms, success, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, conversation_id, provider, model, int(used_model), latency_ms, int(success), error, now_iso()),
        )
        connection.commit()


def create_pending_action(user_id: str, action_name: str, payload: dict[str, Any], risk_level: str, requires_admin: bool) -> dict[str, Any]:
    action_id = str(uuid4())
    created_at = now_iso()
    expires_at = (datetime.now().astimezone() + timedelta(minutes=15)).isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO agent_pending_actions
            (id, user_id, action_name, payload_json, risk_level, requires_admin, created_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (action_id, user_id, action_name, json.dumps(payload, ensure_ascii=False), risk_level, int(requires_admin), created_at, expires_at),
        )
        connection.commit()
    return {
        "id": action_id,
        "action_name": action_name,
        "risk_level": risk_level,
        "requires_admin": requires_admin,
        "created_at": created_at,
        "expires_at": expires_at,
        "status": "pending",
    }


def get_pending_action(action_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, user_id, action_name, payload_json, risk_level, requires_admin, created_at, expires_at, status
            FROM agent_pending_actions
            WHERE id = ?
            """,
            (action_id,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json") or "{}")
    item["requires_admin"] = bool(item["requires_admin"])
    return item


def update_pending_action_status(action_id: str, status: str) -> None:
    with get_connection() as connection:
        connection.execute("UPDATE agent_pending_actions SET status = ? WHERE id = ?", (status, action_id))
        connection.commit()
