from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


BRASIL_KEYWORDS = {
    "brasil",
    "governo",
    "dados publicos",
    "ibge",
    "banco central",
    "bacen",
    "bcb",
    "selic",
    "ipca",
    "ptax",
    "dolar",
    "cambio",
    "ipea",
    "cnpj",
    "cep",
    "brasilapi",
    "camara",
    "senado",
    "deputado",
    "senador",
    "projeto de lei",
    "votacao",
    "tse",
    "eleicao",
    "eleicoes",
    "candidato",
    "prestacao de contas",
    "transparencia",
    "contrato publico",
    "licitacao",
    "pncp",
    "tcu",
    "tce",
    "datasus",
    "anvisa",
    "educacao",
    "inep",
    "enem",
    "ideb",
    "seguranca publica",
    "municipio",
    "estado",
    "volta redonda",
    "rio de janeiro",
    "indicadores publicos",
}


@dataclass
class MCPBrasilPlan:
    intent: str
    tool_name: str | None = None
    arguments: dict = field(default_factory=dict)
    reason: str = ""
    explicit_command: bool = False


class MCPBrasilRouter:
    @staticmethod
    def normalize(message: str) -> str:
        normalized = unicodedata.normalize("NFKD", (message or "").lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def should_use_mcp_brasil(cls, message: str) -> bool:
        text = cls.normalize(message)
        if not text:
            return False
        if text.startswith("/mcp"):
            return True
        if cls.extract_cep(text) or cls.extract_cnpj(text):
            return True
        return any(keyword in text for keyword in BRASIL_KEYWORDS)

    @classmethod
    def plan_query(cls, message: str) -> MCPBrasilPlan:
        original = message or ""
        text = cls.normalize(original)
        if text.startswith("/mcp"):
            return cls._plan_command(original, text)
        cep = cls.extract_cep(text)
        if cep:
            return MCPBrasilPlan("cep_lookup", "brasilapi_cep", {"cep": cep}, "Consulta de CEP via BrasilAPI.")
        cnpj = cls.extract_cnpj(text)
        if cnpj:
            return MCPBrasilPlan("cnpj_lookup", "brasilapi_cnpj", {"cnpj": cnpj}, "Consulta de CNPJ via BrasilAPI.")
        if "selic" in text:
            return MCPBrasilPlan("bacen_selic", "bacen_selic", {"months": 12}, "Consulta da Selic via Banco Central.")
        if "ipca" in text:
            return MCPBrasilPlan("bacen_ipca", "bacen_ipca", {"months": 12}, "Consulta de IPCA via Banco Central.")
        if "ibge" in text or "municipio" in text or "volta redonda" in text:
            municipio = cls.extract_municipality(text) or "Volta Redonda"
            return MCPBrasilPlan("ibge_municipio", "ibge_municipio", {"municipio": municipio}, "Consulta municipal via IBGE.")
        if any(word in text for word in ["features", "fontes", "dados publicos", "consegue consultar"]):
            return MCPBrasilPlan("features", "listar_features", {}, "Listagem de features publicas.")
        if any(word in text for word in ["planejar", "compare", "comparar"]):
            return MCPBrasilPlan("plan", "planejar_consulta", {"query": original}, "Planejamento de consulta MCP Brasil.")
        return MCPBrasilPlan("public_data_question", "recomendar_tools", {"query": original}, "Pergunta sobre dados publicos brasileiros.")

    @staticmethod
    def extract_cep(text: str) -> str | None:
        match = re.search(r"\b(\d{5})-?(\d{3})\b", text)
        return f"{match.group(1)}{match.group(2)}" if match else None

    @staticmethod
    def extract_cnpj(text: str) -> str | None:
        match = re.search(r"\b(\d{2})\.?(\d{3})\.?(\d{3})/?(\d{4})-?(\d{2})\b", text)
        return "".join(match.groups()) if match else None

    @staticmethod
    def extract_municipality(text: str) -> str | None:
        if "volta redonda" in text:
            return "Volta Redonda"
        match = re.search(r"(?:municipio de|cidade de|dados de|sobre)\s+([a-z\s]{3,60})(?:\s+no ibge|\s+pelo ibge|$)", text)
        if not match:
            return None
        return " ".join(word.capitalize() for word in match.group(1).strip().split())

    @classmethod
    def _plan_command(cls, original: str, text: str) -> MCPBrasilPlan:
        command = text.removeprefix("/mcp").strip()
        if not command or command == "status":
            return MCPBrasilPlan("status", "status", {}, "Status do modulo MCP Brasil.", True)
        if command in {"features", "fontes", "tools"}:
            return MCPBrasilPlan("features", "listar_features", {}, "Listagem de features publicas.", True)
        cep = cls.extract_cep(command)
        if "cep" in command and cep:
            return MCPBrasilPlan("cep_lookup", "brasilapi_cep", {"cep": cep}, "Comando manual de CEP.", True)
        cnpj = cls.extract_cnpj(command)
        if "cnpj" in command and cnpj:
            return MCPBrasilPlan("cnpj_lookup", "brasilapi_cnpj", {"cnpj": cnpj}, "Comando manual de CNPJ.", True)
        if "ibge" in command:
            municipio = cls.extract_municipality(command) or command.replace("ibge", "").replace("municipio", "").strip() or "Volta Redonda"
            return MCPBrasilPlan("ibge_municipio", "ibge_municipio", {"municipio": municipio}, "Comando manual de IBGE.", True)
        if "selic" in command or "bacen" in command:
            return MCPBrasilPlan("bacen_selic", "bacen_selic", {"months": 12}, "Comando manual de Selic.", True)
        if "planejar" in command:
            query = original.split("planejar", 1)[-1].strip().strip('"') or original
            return MCPBrasilPlan("plan", "planejar_consulta", {"query": query}, "Comando manual de planejamento.", True)
        return MCPBrasilPlan("manual", "recomendar_tools", {"query": original}, "Comando MCP Brasil generico.", True)
