from __future__ import annotations

from app.agent.schemas.tools import ToolDefinition
from app.core.runtime import is_cloud


TOOLS = [
    ToolDefinition(name="get_system_status", description="Coleta status atual do sistema.", category="diagnostic", risk_level="low", function_path="app.services.system_info.get_system_status"),
    ToolDefinition(name="generate_report", description="Gera relatorio tecnico local.", category="diagnostic", risk_level="low", function_path="app.services.report.generate_technical_report"),
    ToolDefinition(name="analyze_report", description="Analisa relatorio local com Nexus Core.", category="diagnostic", risk_level="low", function_path="app.agent.core.NexusCore.analyze_pc"),
    ToolDefinition(name="quick_diagnostic", description="Diagnostico rapido baseado em status e RAG.", category="diagnostic", risk_level="low", function_path="app.agent.core.NexusCore.chat"),
    ToolDefinition(name="full_diagnostic", description="Diagnostico completo com relatorio, memoria, RAG e web se necessario.", category="diagnostic", risk_level="low", function_path="app.agent.core.NexusCore.analyze_pc"),
    ToolDefinition(name="search_knowledge", description="Busca na base local RAG.", category="knowledge", risk_level="low", function_path="app.agent.rag.search"),
    ToolDefinition(name="search_web", description="Pesquisa web read-only com citacoes.", category="web", risk_level="low", function_path="app.agent.web.search.WebSearchEngine.search"),
    ToolDefinition(name="check_spooler", description="Consulta status do spooler.", category="printer", risk_level="low", function_path="app.services.system_info.get_service_status"),
    ToolDefinition(name="list_printers", description="Lista impressoras instaladas.", category="printer", risk_level="low", function_path="app.services.system_info.get_installed_printers"),
    ToolDefinition(name="get_network_info", description="Coleta adaptadores, gateway e DNS.", category="network", risk_level="low", function_path="app.services.system_info.get_network_configuration"),
    ToolDefinition(name="flush_dns", description="Limpeza de cache DNS planejada para allowlist futura.", category="network", risk_level="medium", requires_confirmation=True, function_path="not_implemented", enabled=False),
    ToolDefinition(name="renew_ip", description="Renovacao de IP planejada para allowlist futura.", category="network", risk_level="medium", requires_confirmation=True, function_path="not_implemented", enabled=False),
    ToolDefinition(name="restart_spooler", description="Reinicia spooler de impressao.", category="printer", risk_level="medium", requires_admin=True, requires_confirmation=True, function_path="app.services.actions.restart_spooler"),
    ToolDefinition(name="clear_print_queue", description="Limpeza de fila planejada para allowlist futura.", category="printer", risk_level="medium", requires_admin=True, requires_confirmation=True, function_path="not_implemented", enabled=False),
    ToolDefinition(name="clean_temp", description="Limpa temporarios seguros do usuario.", category="maintenance", risk_level="medium", requires_confirmation=True, function_path="app.services.actions.clean_temp_files"),
    ToolDefinition(name="export_report", description="Exporta relatorio gerado.", category="report", risk_level="low", function_path="dashboard_download"),
]

FORBIDDEN_TOOL_NAMES = {"shell", "cmd", "powershell", "exec", "registry_edit", "download_and_run"}
LOCAL_ONLY_TOOL_NAMES = {
    "get_system_status",
    "generate_report",
    "analyze_report",
    "quick_diagnostic",
    "full_diagnostic",
    "search_knowledge",
    "check_spooler",
    "list_printers",
    "get_network_info",
    "restart_spooler",
    "clean_temp",
    "export_report",
}

CLOUD_TOOLS = [
    ToolDefinition(name="chat", description="Conversa e geracao de texto com providers online.", category="chat", risk_level="low", function_path="app.agent.core.NexusCore.chat"),
    ToolDefinition(name="search_web", description="Pesquisa web read-only com citacoes.", category="web", risk_level="low", function_path="app.agent.web.search.WebSearchEngine.search"),
    ToolDefinition(name="memory_user", description="Memoria do usuario em banco cloud quando configurado.", category="memory", risk_level="low", function_path="app.agent.memory"),
    ToolDefinition(name="artifact_text", description="Cria artefatos textuais baseados em conteudo enviado.", category="artifact", risk_level="low", function_path="app.agent.artifacts"),
]


def list_tools() -> list[dict]:
    if is_cloud():
        return [tool.model_dump() for tool in CLOUD_TOOLS]
    return [tool.model_dump() for tool in TOOLS]


def get_tool(name: str) -> ToolDefinition | None:
    for tool in TOOLS:
        if tool.name == name:
            return tool
    return None


def suggest_tools(category: str, intent: str) -> list[str]:
    if is_cloud():
        if intent in {"web_research", "deep_web_research", "price_or_product_advice"} or category == "web_research":
            return ["search_web"]
        return []
    suggestions = ["search_knowledge"]
    if intent in {"report_analysis", "pc_diagnostic"}:
        suggestions.append("generate_report")
    if category == "printer":
        suggestions.extend(["check_spooler", "list_printers"])
    if category == "network":
        suggestions.append("get_network_info")
    if category in {"performance", "hardware", "windows"}:
        suggestions.append("generate_report")
    if intent in {"web_research", "deep_web_research", "price_or_product_advice"} or category == "web_research":
        suggestions.append("search_web")
    return list(dict.fromkeys(suggestions))
