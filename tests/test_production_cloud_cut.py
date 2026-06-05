from __future__ import annotations

import unittest
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import Response

from app.agent.memory_store import SmartMemoryStore
from app.core import production
from app.core.auth import clear_local_session, create_local_session, validate_csrf_token, validate_token
from app.core.config import settings
from app.db.migrations import get_conversation_repository, get_database_status
from app.db.postgres import PostgresConversationRepository, POSTGRES_SCHEMA
from app.routes.status import read_admin_health, read_health
from app.security import audit
from app.security.access import is_protected_path
from app.security.config import security_settings
from app.security.rate_limit import allow_request, rate_limit_storage_mode


class ProductionCloudCutTests(unittest.TestCase):
    def setUp(self) -> None:
        get_conversation_repository.cache_clear()

    def tearDown(self) -> None:
        get_conversation_repository.cache_clear()

    def test_production_memory_db_is_unhealthy(self) -> None:
        with _production_env(db_engine="memory", database_url="postgres://example"):
            readiness = production.production_readiness()
            self.assertFalse(readiness.ready)
            self.assertIn("AGENTE_FINO_DB_ENGINE", " ".join(readiness.errors))
            self.assertEqual(get_database_status().engine, "unconfigured")

    def test_production_without_database_url_is_unhealthy(self) -> None:
        with _production_env(database_url=""):
            health = read_health()
            self.assertEqual(health["status"], "unhealthy")
            self.assertIn("DATABASE_URL", " ".join(health["configuration_errors"]))

    def test_production_without_session_secret_is_unhealthy(self) -> None:
        with _production_env(session_secret=""):
            health = read_health()
            self.assertEqual(health["status"], "unhealthy")
            self.assertIn("AGENTE_FINO_SESSION_SECRET", " ".join(health["configuration_errors"]))

    def test_production_without_admin_hash_is_unhealthy(self) -> None:
        with _production_env(admin_password_hash=""):
            health = read_health()
            self.assertEqual(health["status"], "unhealthy")
            self.assertIn("AGENTE_FINO_ADMIN_PASSWORD_HASH", " ".join(health["configuration_errors"]))

    def test_cloud_with_postgres_repository_uses_postgres(self) -> None:
        with _production_env():
            repository = get_conversation_repository()
            self.assertIsInstance(repository, PostgresConversationRepository)
            self.assertTrue(get_database_status().persistent)

    def test_postgres_schema_contains_production_tables(self) -> None:
        for table in ["users", "sessions", "conversations", "messages", "long_term_memories", "audit_events", "feedback", "rate_limits"]:
            with self.subTest(table=table):
                self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", POSTGRES_SCHEMA)

    def test_memory_uses_postgres_schema_when_configured(self) -> None:
        with _production_env(), patch("app.agent.memory_store.init_postgres_schema") as init_schema:
            SmartMemoryStore().init()
        init_schema.assert_called_once()

    def test_postgres_session_can_be_created_validated_and_revoked(self) -> None:
        with (
            _production_env(),
            patch("app.db.postgres.create_session_record") as create_record,
            patch("app.db.postgres.get_session_record", return_value={"csrf_token": "csrf-ok"}) as get_record,
            patch("app.db.postgres.revoke_session_record", return_value=True) as revoke_record,
        ):
            response = Response()
            payload = create_local_session(response)
            token = response.headers["set-cookie"].split("agente_fino_session=", 1)[1].split(";", 1)[0]
            self.assertEqual(payload["mode"], "postgres-session")
            self.assertTrue(validate_token(token))
            self.assertTrue(validate_csrf_token(token, "csrf-ok"))
            clear_local_session(_request_with_cookie(token), Response())
        create_record.assert_called_once()
        get_record.assert_called()
        revoke_record.assert_called_once()

    def test_admin_health_is_protected_and_reports_storage_modes(self) -> None:
        self.assertTrue(is_protected_path("/api/admin/health"))
        with _production_env():
            health = read_admin_health()
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["database"]["engine"], "postgres")
            self.assertEqual(health["security"]["rate_limit_mode"], "postgres")
            self.assertEqual(health["security"]["audit_mode"], "postgres")

    def test_audit_events_use_postgres_when_configured(self) -> None:
        fake_secret = "s" + "k" + "-proj-abcdefghijklmnopqrstuvwxyz123456"
        with _production_env(), patch("app.db.postgres.insert_audit_event") as insert_event:
            event = audit.audit_event("login_success", details={"token": fake_secret})
        insert_event.assert_called_once()
        self.assertIn("***", str(event["details"]))

    def test_rate_limit_uses_postgres_when_configured(self) -> None:
        with _production_env(), patch("app.db.postgres.allow_postgres_rate_limit", return_value=False) as allow_pg:
            self.assertFalse(allow_request("chat:test", limit=1))
            self.assertEqual(rate_limit_storage_mode(), "postgres")
        allow_pg.assert_called_once()

    def test_raw_temporary_password_is_not_in_project_files(self) -> None:
        forbidden = "0802" + "2004"
        skipped_parts = {"backup_before_cloud_native_200", "__pycache__", ".git", "data"}
        for path in Path(".").rglob("*"):
            if not path.is_file() or any(part in skipped_parts for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".txt", ".md", ".html", ".css", ".js", ".json", ".example", ".ps1"}:
                continue
            with self.subTest(path=str(path)):
                self.assertNotIn(forbidden, path.read_text(encoding="utf-8", errors="ignore"))


def _production_env(
    *,
    db_engine: str = "postgres",
    database_url: str = "postgresql://user:pass@example.invalid/agente_fino",
    session_secret: str = "test-session-secret",
    admin_password_hash: str = "pbkdf2_sha256$260000$salt$hash",
):
    @contextmanager
    def _ctx():
        with ExitStack() as stack:
            stack.enter_context(patch.object(settings, "db_engine", db_engine))
            stack.enter_context(patch.object(settings, "database_url", database_url))
            stack.enter_context(patch.object(settings, "admin_password_hash", admin_password_hash))
            stack.enter_context(patch.object(security_settings, "public_mode", True))
            stack.enter_context(patch.object(security_settings, "environment", "production"))
            stack.enter_context(patch.object(security_settings, "session_secret", session_secret))
            yield

    return _ctx()


def _request_with_cookie(token: str):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/logout",
            "headers": [(b"cookie", f"agente_fino_session={token}".encode("ascii"))],
            "server": ("testserver", 80),
            "scheme": "https",
        }
    )


if __name__ == "__main__":
    unittest.main()
