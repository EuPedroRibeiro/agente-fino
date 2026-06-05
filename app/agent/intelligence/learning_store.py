from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.agent.security.sanitizer import mask_secrets


class LearningStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.db_path
        if not self.path.is_absolute():
            self.path = Path.cwd() / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def init(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS agent_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT, created_at TEXT)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS learning_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, rule TEXT, created_at TEXT)"
            )

    def save_feedback(self, payload: dict) -> dict:
        import json

        cleaned = json.dumps(mask_secrets(payload), ensure_ascii=False)
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path)) as connection:
            cursor = connection.execute("INSERT INTO agent_feedback (payload, created_at) VALUES (?, ?)", (cleaned, created_at))
            connection.commit()
        return {"id": cursor.lastrowid, "saved": True}

    def save_rule(self, rule: str) -> dict:
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path)) as connection:
            cursor = connection.execute("INSERT INTO learning_rules (rule, created_at) VALUES (?, ?)", (mask_secrets(rule), created_at))
            connection.commit()
        return {"id": cursor.lastrowid, "rule": mask_secrets(rule)}
