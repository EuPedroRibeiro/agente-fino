from __future__ import annotations

from app.db.base import ConversationRepository, DatabaseStatus

__all__ = ["ConversationRepository", "DatabaseStatus", "get_conversation_repository", "get_database_status", "init_database_layer"]


def get_conversation_repository():
    from app.db.migrations import get_conversation_repository as _get_conversation_repository

    return _get_conversation_repository()


def get_database_status() -> DatabaseStatus:
    from app.db.migrations import get_database_status as _get_database_status

    return _get_database_status()


def init_database_layer() -> None:
    from app.db.migrations import init_database_layer as _init_database_layer

    _init_database_layer()
