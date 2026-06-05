from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.security.documents import extract_cnpjs, extract_cpfs


@dataclass
class PublicDataPlan:
    topic: str
    tool_name: str | None = None
    arguments: dict = field(default_factory=dict)
    reason: str = ""


class PublicDataRouter:
    PUBLIC_TERMS = {
        "dados abertos brasil",
        "dados publicos",
        "deputado",
        "deputados",
        "partido",
        "partidos",
        "proposicao",
        "proposicoes",
        "projeto de lei",
        "votacao",
        "votacoes",
        "camara",
        "senado",
        "senador",
        "senadores",
        "bacen",
        "banco central",
        "serie sgs",
        "ibge",
        "ipea",
        "unidade federativa",
    }
    EXPENSE_TERMS = {"despesa", "despesas", "gasto", "gastos", "fornecedor", "fornecedores", "cota parlamentar"}

    @staticmethod
    def normalize(message: str) -> str:
        normalized = unicodedata.normalize("NFKD", (message or "").lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def is_parliamentary_expense_query(cls, message: str) -> bool:
        text = cls.normalize(message)
        return any(term in text for term in cls.EXPENSE_TERMS) and any(
            term in text for term in ("deputado", "deputada", "camara", "parlamentar")
        )

    @classmethod
    def should_use_public_data(cls, message: str) -> bool:
        text = cls.normalize(message)
        if not text:
            return False
        if cls.is_common_cpf_request(message):
            return False
        if cls.is_parliamentary_expense_query(message):
            return True
        if re.search(r"\b(?:uf|estado)\s+[a-z]{2}\b", text):
            return True
        return any(term in text for term in cls.PUBLIC_TERMS)

    @classmethod
    def is_common_cpf_request(cls, message: str) -> bool:
        text = cls.normalize(message)
        return bool(extract_cpfs(message) and "cpf" in text and not cls.is_parliamentary_expense_query(message))

    @classmethod
    def plan_query(cls, message: str) -> PublicDataPlan:
        text = cls.normalize(message)
        if cls.is_common_cpf_request(message):
            return PublicDataPlan(
                "common_cpf_notice",
                None,
                {},
                "DadosAbertosBrasil nao oferece consulta livre de CPF.",
            )
        if cls.is_parliamentary_expense_query(message):
            supplier = (extract_cnpjs(message) or extract_cpfs(message) or [None])[0]
            return PublicDataPlan(
                "camara_expenses",
                "camara_deputy_expenses",
                {"deputy_name": cls._extract_deputy_name(text), "supplier": supplier},
                "Despesas parlamentares publicas da Camara.",
            )
        if "deputad" in text or "camara" in text and "dados" in text:
            return PublicDataPlan(
                "camara_deputies",
                "camara_deputies",
                {"name": cls._extract_deputy_name(text)},
                "Dados publicos de deputados da Camara.",
            )
        if "partido" in text:
            return PublicDataPlan("camara_parties", "camara_parties", {}, "Partidos representados na Camara.")
        if "propos" in text or "projeto de lei" in text:
            return PublicDataPlan(
                "camara_propositions",
                "camara_propositions",
                {"keyword": cls._extract_after(text, ("sobre", "contendo"))},
                "Proposicoes publicas da Camara.",
            )
        if "votac" in text:
            return PublicDataPlan("camara_votes", "camara_votes", {}, "Votacoes publicas da Camara.")
        if "senado" in text or "senador" in text:
            return PublicDataPlan(
                "senate_members",
                "senate_members",
                {"name": cls._extract_after(text, ("senador", "senadora", "sobre"))},
                "Dados publicos do Senado.",
            )
        if "bacen" in text or "banco central" in text or "serie sgs" in text or "selic" in text:
            code_match = re.search(r"\b(?:serie|sgs|codigo)\s*(?:do\s+)?(?:banco central\s*)?(\d{1,8})\b", text)
            code = int(code_match.group(1)) if code_match else (432 if "selic" in text else None)
            return PublicDataPlan("bacen_series", "bacen_series", {"code": code}, "Serie publica do Banco Central.")
        if "ibge" in text or "populacao" in text:
            return PublicDataPlan("ibge_population", "ibge_population", {}, "Projecao populacional publica do IBGE.")
        if "ipea" in text:
            return PublicDataPlan(
                "ipea_series",
                "ipea_series",
                {"query": cls._extract_after(text, ("sobre", "serie", "ipea"))},
                "Series publicas do IPEA.",
            )
        if re.search(r"\buf\s+[a-z]{2}\b", text) or "unidade federativa" in text:
            uf_match = re.search(r"\b(?:uf|estado)\s+([a-z]{2})\b", text)
            return PublicDataPlan(
                "uf_data",
                "uf_data",
                {"uf": uf_match.group(1).upper() if uf_match else None},
                "Dados publicos de unidade federativa.",
            )
        return PublicDataPlan("public_data_help", "public_data_help", {}, "Ajuda sobre fontes publicas disponiveis.")

    @staticmethod
    def _extract_after(text: str, markers: tuple[str, ...]) -> str | None:
        for marker in markers:
            match = re.search(rf"\b{re.escape(marker)}\s+(.+)$", text)
            if match:
                value = match.group(1).strip(" ?.,")
                return value[:120] or None
        return None

    @classmethod
    def _extract_deputy_name(cls, text: str) -> str | None:
        match = re.search(r"\bdeputad[oa]\s+(?:federal\s+)?(.+)$", text)
        if not match:
            return None
        name = match.group(1)
        name = re.split(r"\s+(?:cpf|cnpj|fornecedor|nas despesas|em despesas)\b", name, maxsplit=1)[0]
        name = re.sub(r"^(?:do|da|de)\s+", "", name).strip(" ?.,")
        return " ".join(word.capitalize() for word in name.split())[:120] or None
