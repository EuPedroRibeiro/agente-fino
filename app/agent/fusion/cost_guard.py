from __future__ import annotations


def allow_model_count(requested: int, maximum: int = 2) -> int:
    return max(1, min(int(requested), int(maximum)))
