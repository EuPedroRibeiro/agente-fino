from __future__ import annotations

from typing import Any

from app.agent.memory_policy import build_memory_payload, sanitize_memory_value
from app.agent.memory_stores.sqlite_memory import now_iso
from app.core.config import settings
from app.core.logging_db import get_connection
from app.core.production import production_config_errors
from app.db.postgres import get_postgres_connection, init_postgres_schema


SMART_MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS long_term_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT,
    confidence REAL NOT NULL DEFAULT 0.6,
    pinned INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_long_term_memories_category ON long_term_memories(category);
CREATE INDEX IF NOT EXISTS idx_long_term_memories_pinned ON long_term_memories(pinned, archived);
CREATE INDEX IF NOT EXISTS idx_long_term_memories_updated ON long_term_memories(updated_at);
"""


class SmartMemoryStore:
    def init(self) -> None:
        _raise_if_unavailable()
        if _use_postgres():
            init_postgres_schema()
            return
        with get_connection() as connection:
            connection.executescript(SMART_MEMORY_SCHEMA)
            connection.commit()

    def create(
        self,
        *,
        category: str | None,
        key: str | None,
        value: str,
        source: str = "user",
        confidence: float = 0.85,
        pinned: bool = False,
        archived: bool = False,
    ) -> dict[str, Any]:
        _raise_if_unavailable()
        payload = build_memory_payload(
            category=category,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            pinned=pinned,
        )
        created_at = now_iso()
        if _use_postgres():
            with get_postgres_connection() as connection:
                row = connection.execute(
                    """
                    INSERT INTO long_term_memories
                    (created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                    RETURNING id
                    """,
                    (
                        created_at,
                        created_at,
                        payload["category"],
                        payload["key"],
                        payload["value"],
                        source,
                        confidence,
                        bool(pinned),
                        bool(archived),
                    ),
                ).fetchone()
                connection.commit()
            item = self.get(int(row["id"]))
            item["masked_secret"] = payload["masked_secret"]
            item["requires_confirmation"] = payload["requires_confirmation"]
            return item
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO long_term_memories
                (created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    created_at,
                    created_at,
                    payload["category"],
                    payload["key"],
                    payload["value"],
                    source,
                    confidence,
                    int(pinned),
                    int(archived),
                ),
            )
            connection.commit()
            memory_id = int(cursor.lastrowid)
        item = self.get(memory_id)
        item["masked_secret"] = payload["masked_secret"]
        item["requires_confirmation"] = payload["requires_confirmation"]
        return item

    def get(self, memory_id: int) -> dict[str, Any]:
        _raise_if_unavailable()
        if _use_postgres():
            with get_postgres_connection() as connection:
                row = connection.execute(
                    """
                    SELECT id, created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at
                    FROM long_term_memories
                    WHERE id = %s
                    """,
                    (memory_id,),
                ).fetchone()
            if not row:
                raise KeyError(f"Memoria {memory_id} nao encontrada.")
            return _row_to_memory(row)
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at
                FROM long_term_memories
                WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"Memoria {memory_id} nao encontrada.")
        return _row_to_memory(row)

    def list(self, *, include_archived: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        _raise_if_unavailable()
        if _use_postgres():
            where = "" if include_archived else "WHERE archived = FALSE"
            with get_postgres_connection() as connection:
                rows = connection.execute(
                    f"""
                    SELECT id, created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at
                    FROM long_term_memories
                    {where}
                    ORDER BY pinned DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (max(1, min(limit, 300)),),
                ).fetchall()
            return [_row_to_memory(row) for row in rows]
        where = "" if include_archived else "WHERE archived = 0"
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at
                FROM long_term_memories
                {where}
                ORDER BY pinned DESC, updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 300)),),
            ).fetchall()
        return [_row_to_memory(row) for row in rows]

    def search(self, query: str, *, limit: int = 20, include_archived: bool = False) -> list[dict[str, Any]]:
        _raise_if_unavailable()
        if _use_postgres():
            pattern = f"%{query}%"
            where_archived = "" if include_archived else "AND archived = FALSE"
            with get_postgres_connection() as connection:
                rows = connection.execute(
                    f"""
                    SELECT id, created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at
                    FROM long_term_memories
                    WHERE (category ILIKE %s OR key ILIKE %s OR value ILIKE %s OR source ILIKE %s)
                    {where_archived}
                    ORDER BY pinned DESC, confidence DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (pattern, pattern, pattern, pattern, max(1, min(limit, 100))),
                ).fetchall()
                ids = [row["id"] for row in rows]
                if ids:
                    connection.executemany("UPDATE long_term_memories SET last_used_at = %s WHERE id = %s", [(now_iso(), memory_id) for memory_id in ids])
                    connection.commit()
            return [_row_to_memory(row) for row in rows]
        pattern = f"%{query}%"
        where_archived = "" if include_archived else "AND archived = 0"
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, created_at, updated_at, category, key, value, source, confidence, pinned, archived, last_used_at
                FROM long_term_memories
                WHERE (category LIKE ? OR key LIKE ? OR value LIKE ? OR source LIKE ?)
                {where_archived}
                ORDER BY pinned DESC, confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, max(1, min(limit, 100))),
            ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                connection.executemany("UPDATE long_term_memories SET last_used_at = ? WHERE id = ?", [(now_iso(), memory_id) for memory_id in ids])
                connection.commit()
        return [_row_to_memory(row) for row in rows]

    def update(self, memory_id: int, updates: dict[str, Any]) -> dict[str, Any]:
        _raise_if_unavailable()
        allowed = {"category", "key", "value", "source", "confidence", "pinned", "archived"}
        changes: dict[str, Any] = {key: value for key, value in updates.items() if key in allowed and value is not None}
        if "value" in changes:
            changes["value"] = sanitize_memory_value(str(changes["value"]))[0]
        if "pinned" in changes:
            changes["pinned"] = bool(changes["pinned"]) if _use_postgres() else int(bool(changes["pinned"]))
        if "archived" in changes:
            changes["archived"] = bool(changes["archived"]) if _use_postgres() else int(bool(changes["archived"]))
        if not changes:
            return self.get(memory_id)
        changes["updated_at"] = now_iso()
        if _use_postgres():
            set_clause = ", ".join(f"{key} = %s" for key in changes)
            values = list(changes.values()) + [memory_id]
            with get_postgres_connection() as connection:
                cursor = connection.execute(f"UPDATE long_term_memories SET {set_clause} WHERE id = %s", values)
                connection.commit()
            if cursor.rowcount == 0:
                raise KeyError(f"Memoria {memory_id} nao encontrada.")
            return self.get(memory_id)
        set_clause = ", ".join(f"{key} = ?" for key in changes)
        values = list(changes.values()) + [memory_id]
        with get_connection() as connection:
            cursor = connection.execute(f"UPDATE long_term_memories SET {set_clause} WHERE id = ?", values)
            connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Memoria {memory_id} nao encontrada.")
        return self.get(memory_id)

    def delete(self, memory_id: int) -> bool:
        _raise_if_unavailable()
        if _use_postgres():
            with get_postgres_connection() as connection:
                cursor = connection.execute("DELETE FROM long_term_memories WHERE id = %s", (memory_id,))
                connection.commit()
                return cursor.rowcount > 0
        with get_connection() as connection:
            cursor = connection.execute("DELETE FROM long_term_memories WHERE id = ?", (memory_id,))
            connection.commit()
            return cursor.rowcount > 0

    def pin(self, memory_id: int, pinned: bool = True) -> dict[str, Any]:
        return self.update(memory_id, {"pinned": pinned})

    def archive(self, memory_id: int, archived: bool = True) -> dict[str, Any]:
        return self.update(memory_id, {"archived": archived})


def _row_to_memory(row) -> dict[str, Any]:
    item = dict(row)
    item["pinned"] = bool(item["pinned"])
    item["archived"] = bool(item["archived"])
    item["confidence"] = float(item["confidence"] or 0)
    return item


def _use_postgres() -> bool:
    return settings.db_engine == "postgres" and bool(settings.database_url)


def _raise_if_unavailable() -> None:
    errors = production_config_errors()
    if errors:
        raise RuntimeError("Memoria persistente indisponivel: " + "; ".join(errors))
