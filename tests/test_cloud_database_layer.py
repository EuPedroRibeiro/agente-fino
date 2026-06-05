from __future__ import annotations

import unittest

from app.agent import conversation_logs
from app.db import get_database_status


class CloudDatabaseLayerTests(unittest.TestCase):
    def test_database_status_uses_memory_without_database_url(self) -> None:
        status = get_database_status()
        self.assertEqual(status.engine, "memory")
        self.assertFalse(status.persistent)
        self.assertIn("Persistencia cloud nao configurada", status.message)

    def test_history_uses_repository_abstraction(self) -> None:
        created = conversation_logs.create_conversation("Cloud repo teste")
        conversation_logs.add_message(conversation_id=created["id"], role="user", content="oi")
        messages = conversation_logs.list_messages(created["id"])
        self.assertEqual(messages[0]["content"], "oi")
        self.assertTrue(conversation_logs.delete_conversation(created["id"]))

