from __future__ import annotations

import unittest

from app.agent.intelligence.permissions import PermissionLevel, permission_for_tool, requires_confirmation


class ToolPermissionsTests(unittest.TestCase):
    def test_disk_usage_is_read_only(self) -> None:
        self.assertEqual(permission_for_tool("disk_usage"), PermissionLevel.READ_ONLY)
        self.assertFalse(requires_confirmation("disk_usage"))

    def test_delete_temp_requires_confirmation(self) -> None:
        self.assertTrue(requires_confirmation("clean_temp"))

    def test_blocked_shell_tool(self) -> None:
        self.assertEqual(permission_for_tool("powershell"), PermissionLevel.BLOCKED)


if __name__ == "__main__":
    unittest.main()
