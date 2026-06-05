from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.production import is_production_cloud, production_config_errors
from app.core.runtime import is_cloud
from app.db.base import ConversationRepository, DatabaseStatus
from app.db.memory import MemoryConversationRepository
from app.db.postgres import PostgresConversationRepository
from app.db.sqlite_legacy import SQLiteLegacyConversationRepository


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    engine = _effective_engine()
    if engine == "unconfigured":
        return UnavailableConversationRepository()
    if engine == "memory":
        return MemoryConversationRepository()
    if engine == "postgres":
        return PostgresConversationRepository(settings.database_url)
    return SQLiteLegacyConversationRepository()


def init_database_layer() -> None:
    get_conversation_repository().init()


def get_database_status() -> DatabaseStatus:
    engine = _effective_engine()
    if engine == "unconfigured":
        errors = production_config_errors()
        return DatabaseStatus(
            engine="unconfigured",
            configured=False,
            persistent=False,
            message="; ".join(errors) or "Banco de producao nao configurado.",
        )
    if engine == "memory":
        return DatabaseStatus(
            engine="memory",
            configured=False,
            persistent=False,
            message="Persistencia cloud nao configurada. Usando memoria temporaria de preview.",
        )
    if engine == "postgres":
        return DatabaseStatus(
            engine="postgres",
            configured=bool(settings.database_url),
            persistent=bool(settings.database_url),
            message="Postgres configurado via DATABASE_URL." if settings.database_url else "DATABASE_URL ausente.",
        )
    return DatabaseStatus(
        engine="sqlite",
        configured=True,
        persistent=not is_cloud(),
        message="SQLite legado local." if not is_cloud() else "SQLite em ambiente cloud nao e persistencia confiavel.",
    )


def _effective_engine() -> str:
    engine = (settings.db_engine or "").strip().lower()
    if is_production_cloud() and production_config_errors():
        return "unconfigured"
    if is_cloud() and not settings.database_url:
        return "memory"
    if engine == "postgres" and not settings.database_url:
        return "memory"
    if engine in {"postgres", "sqlite", "memory"}:
        return engine
    return "memory" if is_cloud() else "sqlite"


class UnavailableConversationRepository:
    message = "Banco Postgres obrigatorio nao configurado para producao cloud."

    def init(self) -> None:
        return None

    def _raise(self):
        raise RuntimeError(self.message)

    def create_conversation(self, title: str | None = None) -> dict:
        self._raise()

    def ensure_conversation(self, conversation_id: str, *, title: str | None = None) -> dict:
        self._raise()

    def list_conversations(self, query: str | None = None, limit: int = 60) -> list[dict]:
        self._raise()

    def get_conversation(self, conversation_id: str) -> dict | None:
        self._raise()

    def update_conversation(self, conversation_id: str, title: str) -> dict:
        self._raise()

    def delete_conversation(self, conversation_id: str) -> bool:
        self._raise()

    def add_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        intent: str | None = None,
        tools_used: list[str] | None = None,
        web_sources_count: int = 0,
        latency_ms: int | None = None,
    ) -> dict:
        self._raise()

    def get_message(self, message_id: int) -> dict | None:
        self._raise()

    def list_messages(self, conversation_id: str) -> list[dict]:
        self._raise()


def main() -> None:
    status = get_database_status()
    if status.engine == "unconfigured":
        raise SystemExit(f"Banco nao configurado: {status.message}")
    init_database_layer()
    print(
        {
            "engine": status.engine,
            "configured": status.configured,
            "persistent": status.persistent,
            "message": status.message,
        }
    )


if __name__ == "__main__":
    main()
