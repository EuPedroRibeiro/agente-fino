from __future__ import annotations

from app.agent.providers.model_router import ModelRouter


class IntelligenceModelSelector:
    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router = router or ModelRouter()

    def status(self) -> dict:
        return self.router.status()

    def online_available(self) -> bool:
        status = self.status()
        return bool(status.get("real_llm_enabled"))

    def selected(self) -> tuple[str, str, str | None]:
        status = self.status()
        return (
            status.get("selected_provider", "local-rules"),
            status.get("selected_model", "deterministic-rules"),
            status.get("fallback_reason"),
        )
