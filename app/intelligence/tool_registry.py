from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.runtime import is_cloud


Risk = Literal["low", "medium", "high", "blocked"]


class IntelligenceTool(BaseModel):
    name: str
    description: str
    intents: set[str] = Field(default_factory=set)
    argument_schema: dict[str, Any] = Field(default_factory=dict)
    risk: Risk = "low"
    timeout_seconds: float = 15.0
    rate_limit_per_hour: int | None = None
    required_env: list[str] = Field(default_factory=list)
    cloud_available: bool = True
    requires_confirmation: bool = False
    fallback: str | None = None


TOOLS = [
    IntelligenceTool(name="disk_space", description="Le espaco livre do disco.", intents={"disk_space", "storage_status"}, cloud_available=False),
    IntelligenceTool(name="folder_size", description="Calcula tamanho ou quantidade de arquivos.", intents={"folder_size", "file_count"}, argument_schema={"path": "string"}, timeout_seconds=15, cloud_available=False),
    IntelligenceTool(name="disk_usage", description="Lista as maiores pastas.", intents={"folder_usage_top", "disk_usage", "followup_accept_offer"}, argument_schema={"path": "string"}, timeout_seconds=20, cloud_available=False),
    IntelligenceTool(name="system_status", description="Le metricas simples do computador.", intents={"ram_status", "cpu_status", "local_ip_status", "uptime_status", "simple_pc_metric"}, cloud_available=False),
    IntelligenceTool(name="spooler_status", description="Le o estado do spooler.", intents={"spooler_status"}, cloud_available=False),
    IntelligenceTool(name="analyze_pc", description="Executa diagnostico tecnico somente leitura.", intents={"pc_diagnostic", "pc_analysis"}, timeout_seconds=30, cloud_available=False),
    IntelligenceTool(name="printer_status", description="Consulta impressoras e spooler.", intents={"printer_support", "printer_status"}, cloud_available=False),
    IntelligenceTool(name="network_info", description="Consulta configuracao de rede.", intents={"network_support", "network_info"}, cloud_available=False),
    IntelligenceTool(name="web_search", description="Pesquisa fontes web.", intents={"web_research", "deep_web_research", "deep_research", "price_or_product_advice"}, timeout_seconds=35, fallback="general_analysis"),
    IntelligenceTool(name="rag_search", description="Consulta a base local.", intents={"rag_search", "tech_support", "software_support", "printer_support", "network_support", "cybersecurity_learning"}, timeout_seconds=12, cloud_available=False),
    IntelligenceTool(name="memory_search", description="Consulta memoria autorizada.", intents={"memory_search"}, timeout_seconds=8),
    IntelligenceTool(name="memory_save", description="Salva memoria autorizada.", intents={"memory_save"}),
    IntelligenceTool(name="document_lookup", description="Consulta documento em fonte autorizada.", intents={"cpf_lookup", "cnpj_lookup"}, timeout_seconds=15, rate_limit_per_hour=100, required_env=["DOCUMENT_LOOKUP_ENABLED"], fallback="document_unavailable"),
    IntelligenceTool(name="cpf_validate_local", description="Valida digitos de CPF localmente.", intents={"cpf_validate"}, timeout_seconds=2),
    IntelligenceTool(name="cpf_lab_simulation", description="Executa simulacao documental com dados ficticios.", intents={"cpf_lab_lookup"}, timeout_seconds=2),
    IntelligenceTool(name="public_data", description="Consulta fonte publica.", intents={"public_data_query", "mcp_brasil"}, timeout_seconds=25, fallback="public_data_unavailable"),
    IntelligenceTool(name="sherlock", description="Abre o modulo Sherlock.", intents={"sherlock_query"}, risk="medium", requires_confirmation=True),
    IntelligenceTool(name="restart_spooler", description="Reinicia o spooler.", intents={"restart_spooler"}, risk="medium", requires_confirmation=True, cloud_available=False),
    IntelligenceTool(name="clean_temp", description="Limpa temporarios seguros.", intents={"clean_temp"}, risk="medium", requires_confirmation=True, cloud_available=False),
]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools = {tool.name: tool for tool in TOOLS}

    def get(self, name: str) -> IntelligenceTool | None:
        return self._tools.get(name)

    def select(self, execution_intent: str, route: dict[str, Any] | None = None) -> list[IntelligenceTool]:
        route = route or {}
        explicit = route.get("tool")
        if explicit and explicit in self._tools:
            return [self._tools[explicit]]
        return [tool for tool in self._tools.values() if execution_intent in tool.intents]

    def authorize(self, tools: list[IntelligenceTool], confidence: float) -> tuple[list[IntelligenceTool], list[str]]:
        allowed: list[IntelligenceTool] = []
        blocked: list[str] = []
        for tool in tools:
            if is_cloud() and not tool.cloud_available:
                blocked.append(f"{tool.name}:indisponivel_no_cloud")
                continue
            if tool.risk in {"medium", "high", "blocked"} and confidence < 0.65:
                blocked.append(f"{tool.name}:confianca_baixa")
                continue
            if tool.risk == "blocked":
                blocked.append(f"{tool.name}:bloqueada")
                continue
            allowed.append(tool)
        return allowed, blocked

    def catalog(self) -> list[dict[str, Any]]:
        return [tool.model_dump(mode="json") for tool in self._tools.values()]
