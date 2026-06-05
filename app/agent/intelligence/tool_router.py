from __future__ import annotations


def tools_for_intent(intent: str, message: str = "") -> list[str]:
    text = (message or "").lower()
    tools: list[str] = []
    if intent in {"disk_space", "storage_status"}:
        tools.append("disk_space")
    if intent == "folder_size":
        tools.append("folder_size")
    if intent == "file_count":
        tools.append("folder_size")
    if intent == "followup_accept_offer":
        tools.append("folder_usage_top")
    if intent in {"ram_status", "cpu_status", "local_ip_status", "uptime_status", "simple_pc_metric"}:
        tools.append("system_status")
    if intent == "spooler_status":
        tools.append("spooler_status")
    if intent in {"pc_diagnostic", "analyze_pc", "report_analysis"} or "analise este pc" in text:
        tools.append("analyze_pc")
    if intent in {"disk_usage", "folder_usage_top"} or any(term in text for term in ["pastas ocupam", "ocupa espaço", "uso de disco", "espaco no disco"]):
        tools.append("disk_usage")
    if intent in {"printer_support", "printer_status"} or "impressora" in text or "spooler" in text:
        tools.append("printer_status")
    if intent in {"network_support", "network_info"} or any(term in text for term in ["rede", "dns", "gateway", "ip"]):
        tools.append("network_info")
    if intent in {"web_research", "deep_web_research"} or text.startswith("pesquise") or text.startswith("pesquisa"):
        tools.append("web_search")
    if "lembra" in text:
        tools.append("memory_search")
    return list(dict.fromkeys(tools))
