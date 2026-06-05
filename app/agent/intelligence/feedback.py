from __future__ import annotations

from app.agent.intelligence.learning_store import LearningStore


def save_feedback(payload: dict) -> dict:
    return LearningStore().save_feedback(payload)
