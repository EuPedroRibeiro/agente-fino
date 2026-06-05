from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from app.core.config import settings


def _path() -> Path:
    path = settings.db_path
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_memory_graph() -> None:
    with closing(sqlite3.connect(_path())) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS memory_nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, type TEXT NOT NULL, confidence REAL DEFAULT 0.8)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS memory_edges (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER, relation TEXT NOT NULL, target_id INTEGER, confidence REAL DEFAULT 0.8)"
        )


def add_node(label: str, type_: str = "entity", confidence: float = 0.8) -> dict:
    init_memory_graph()
    with closing(sqlite3.connect(_path())) as connection:
        cursor = connection.execute(
            "INSERT INTO memory_nodes (label, type, confidence) VALUES (?, ?, ?)",
            (label, type_, confidence),
        )
        connection.commit()
        node_id = cursor.lastrowid
    return {"id": node_id, "label": label, "type": type_, "confidence": confidence}


def search_nodes(query: str, limit: int = 20) -> list[dict]:
    init_memory_graph()
    term = f"%{query}%"
    with closing(sqlite3.connect(_path())) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, label, type, confidence FROM memory_nodes WHERE label LIKE ? ORDER BY confidence DESC LIMIT ?",
            (term, max(1, min(limit, 100))),
        ).fetchall()
    return [dict(row) for row in rows]
