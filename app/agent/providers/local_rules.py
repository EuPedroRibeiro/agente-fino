from __future__ import annotations

from app.agent.providers.base import ModelResponse


class LocalRulesProvider:
    name = "local-rules"

    def is_available(self) -> bool:
        return True

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        user_content = messages[-1]["content"] if messages else ""
        return ModelResponse(
            text=self._fallback_answer(user_content),
            provider=self.name,
            model="deterministic-rules",
            used_model=False,
        )

    def _fallback_answer(self, content: str) -> str:
        return (
            "Entendi. Vou responder de forma direta com o que tenho localmente e, quando o pedido exigir dados do PC, web ou RAG, "
            "o backend usa as ferramentas seguras antes de concluir. "
            f"Pedido recebido: {content[:500]}"
        )
