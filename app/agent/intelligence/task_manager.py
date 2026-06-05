from __future__ import annotations

TASKS: list[dict] = []


def create_task(title: str, description: str = "") -> dict:
    task = {"id": len(TASKS) + 1, "title": title, "description": description, "status": "planned"}
    TASKS.append(task)
    return task


def list_tasks() -> list[dict]:
    return TASKS
