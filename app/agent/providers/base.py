from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelResponse:
    text: str
    provider: str
    model: str
    used_model: bool
    error_type: str | None = None


class ModelProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        ...
