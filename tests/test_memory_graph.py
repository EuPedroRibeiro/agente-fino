from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent import memory_graph


class MemoryGraphTests(unittest.TestCase):
    def test_memory_graph_tables_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            with patch("app.agent.memory_graph.settings.db_path", db):
                node = memory_graph.add_node("Acer Aspire F15", "device")
                self.assertGreater(node["id"], 0)
                results = memory_graph.search_nodes("Acer")
                self.assertEqual(results[0]["label"], "Acer Aspire F15")


if __name__ == "__main__":
    unittest.main()
