from __future__ import annotations


def memory_requirement(intent: str) -> dict:
    needed = intent in {"memory_search", "memory_save", "personal_reflection", "relationship_advice"}
    return {
        "needed": needed,
        "mode": "explicit" if intent in {"memory_search", "memory_save"} else ("light" if needed else "skip"),
    }
