from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.runtime import is_cloud


SCHEMA = """
CREATE TABLE IF NOT EXISTS action_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_name TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    requires_admin INTEGER NOT NULL DEFAULT 0,
    technical_error TEXT
);
"""


MIGRATIONS = [
    ("requires_admin", "ALTER TABLE action_logs ADD COLUMN requires_admin INTEGER NOT NULL DEFAULT 0"),
    ("technical_error", "ALTER TABLE action_logs ADD COLUMN technical_error TEXT"),
]

_MEMORY_DB_URI = "file:agente_fino_cloud_preview?mode=memory&cache=shared"
_MEMORY_ANCHOR: sqlite3.Connection | None = None


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc_value, traceback))
        finally:
            self.close()


def _db_path() -> Path:
    path = settings.db_path
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    if _use_memory_database():
        _ensure_memory_anchor()
        connection = sqlite3.connect(_MEMORY_DB_URI, uri=True, factory=ClosingConnection)
        connection.row_factory = sqlite3.Row
        return connection
    connection = sqlite3.connect(_db_path(), factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    return connection


def _use_memory_database() -> bool:
    return is_cloud() and not settings.database_url


def _ensure_memory_anchor() -> None:
    global _MEMORY_ANCHOR
    if _MEMORY_ANCHOR is None:
        _MEMORY_ANCHOR = sqlite3.connect(_MEMORY_DB_URI, uri=True)


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(SCHEMA)
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(action_logs)").fetchall()
        }
        for column_name, statement in MIGRATIONS:
            if column_name not in existing_columns:
                connection.execute(statement)
        connection.commit()


def log_action(
    action_name: str,
    status: str,
    message: str,
    *,
    requires_admin: bool = False,
    technical_error: str | None = None,
) -> dict[str, Any]:
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO action_logs (action_name, status, message, created_at, requires_admin, technical_error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (action_name, status, message, created_at, int(requires_admin), technical_error),
        )
        connection.commit()
        log_id = cursor.lastrowid

    return {
        "id": log_id,
        "action_name": action_name,
        "status": status,
        "message": message,
        "created_at": created_at,
        "timestamp": created_at,
        "requires_admin": requires_admin,
        "technical_error": technical_error,
    }


def list_action_logs(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 200))
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, action_name, status, message, created_at, requires_admin, technical_error
            FROM action_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    logs: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["requires_admin"] = bool(item["requires_admin"])
        item["timestamp"] = item["created_at"]
        logs.append(item)
    return logs
