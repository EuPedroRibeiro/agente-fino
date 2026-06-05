from __future__ import annotations

from enum import Enum


class PermissionLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK_ACTION = "LOW_RISK_ACTION"
    HIGH_RISK_ACTION = "HIGH_RISK_ACTION"
    BLOCKED = "BLOCKED"


READ_ONLY_TOOLS = {
    "analyze_pc",
    "disk_usage",
    "disk_space",
    "folder_size",
    "folder_usage_top",
    "system_status",
    "ram_status",
    "cpu_status",
    "local_ip_status",
    "uptime_status",
    "spooler_status",
    "printer_status",
    "network_info",
    "web_search",
    "rag_search",
    "memory_search",
}
LOW_RISK_ACTIONS = {"clean_temp", "restart_spooler", "flush_dns", "renew_ip"}
BLOCKED_TOOLS = {"shell", "cmd", "powershell", "exec", "registry_edit", "download_and_run"}


def permission_for_tool(tool_name: str) -> PermissionLevel:
    if tool_name in BLOCKED_TOOLS:
        return PermissionLevel.BLOCKED
    if tool_name in READ_ONLY_TOOLS:
        return PermissionLevel.READ_ONLY
    if tool_name in LOW_RISK_ACTIONS:
        return PermissionLevel.LOW_RISK_ACTION
    return PermissionLevel.HIGH_RISK_ACTION


def requires_confirmation(tool_name: str) -> bool:
    return permission_for_tool(tool_name) in {PermissionLevel.LOW_RISK_ACTION, PermissionLevel.HIGH_RISK_ACTION}
