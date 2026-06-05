from __future__ import annotations

import json
import time
from typing import Any, Callable

from app.agent.providers.public_data import PublicDataError, PublicDataProvider, _rows, sanitize_public_data
from app.agent.public_data_router import PublicDataPlan, PublicDataRouter
from app.agent.security.sanitizer import mask_secrets
from app.security.audit import audit_event
from app.security.documents import mask_personal_documents


AuditFunction = Callable[..., dict[str, Any]]


class PublicDataService:
    def __init__(self, provider: PublicDataProvider | None = None, *, auditor: AuditFunction = audit_event) -> None:
        self.provider = provider or PublicDataProvider()
        self.auditor = auditor

    def status(self) -> dict[str, Any]:
        return self.provider.status()

    def should_handle(self, message: str) -> bool:
        return PublicDataRouter.should_use_public_data(message)

    def ask(self, message: str, *, user: str = "local-user") -> dict[str, Any]:
        started = time.perf_counter()
        plan = PublicDataRouter.plan_query(message)
        if plan.topic == "common_cpf_notice":
            answer = (
                "DadosAbertosBrasil nao fornece consulta livre de CPF de pessoa fisica. "
                "Ele consulta apenas fontes publicas governamentais compativeis."
            )
            self.auditor(
                "public_data_cpf_lookup_blocked",
                details={"reason": "free_cpf_lookup_not_supported", "arguments": _safe_arguments(plan.arguments), "user": user},
                severity="warning",
            )
            return self._result(plan, answer, started, status="blocked", web_used=False)
        try:
            raw = self.provider.query(plan)
            answer = format_public_data_answer(plan, raw)
            result = self._result(plan, answer, started, status="ok", web_used=plan.tool_name != "public_data_help")
            self.auditor(
                "public_data_query_completed",
                details={"topic": plan.topic, "tool": plan.tool_name, "arguments": _safe_arguments(plan.arguments), "user": user},
            )
            return result
        except PublicDataError as exc:
            error = mask_secrets(str(exc))
            answer = f"Nao consegui concluir a consulta de dados publicos agora. {error}"
            self.auditor(
                "public_data_query_failed",
                details={"topic": plan.topic, "tool": plan.tool_name, "error": error, "arguments": _safe_arguments(plan.arguments)},
                severity="warning",
            )
            return self._result(plan, answer, started, status="error", web_used=False, error=error)
        except Exception as exc:
            error = mask_secrets(str(exc))
            answer = "Nao consegui concluir a consulta de dados publicos agora. A falha foi registrada com seguranca."
            self.auditor(
                "public_data_query_failed",
                details={"topic": plan.topic, "tool": plan.tool_name, "error": error, "arguments": _safe_arguments(plan.arguments)},
                severity="error",
            )
            return self._result(plan, answer, started, status="error", web_used=False, error=error)

    @staticmethod
    def _result(
        plan: PublicDataPlan,
        answer: str,
        started: float,
        *,
        status: str,
        web_used: bool,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "answer": mask_personal_documents(answer),
            "intent": "public_data_query",
            "topic": plan.topic,
            "tool": plan.tool_name,
            "arguments": _safe_arguments(plan.arguments),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "web_used": web_used,
            "source": "DadosAbertosBrasil/PublicDataProvider",
            "source_url": source_url_for(plan),
            "error": error,
        }


def format_public_data_answer(plan: PublicDataPlan, raw: Any) -> str:
    topic = plan.topic
    if topic == "public_data_help":
        return (
            "Dados publicos estao ativos sem chave de API.\n\n"
            "Fontes disponiveis: Camara, Senado, Banco Central, IBGE, IPEA e dados de UF.\n"
            "DadosAbertosBrasil nao fornece consulta livre de CPF."
        )
    if topic == "camara_deputies":
        rows = _rows(raw)
        if not rows:
            return "Nao encontrei deputados para esse filtro na fonte publica da Camara."
        lines = [
            f"- {row.get('nome', '--')} | {row.get('siglaPartido', '--')}/{row.get('siglaUf', '--')} | ID {row.get('id', '--')}"
            for row in rows[:10]
        ]
        return "Deputados encontrados na Camara:\n\n" + "\n".join(lines)
    if topic == "camara_expenses":
        deputy = raw.get("deputy") or {}
        expenses = raw.get("expenses") or []
        if not expenses:
            return f"Nao encontrei despesas publicas para {deputy.get('nome', 'o deputado')} com esse filtro."
        lines = []
        for item in expenses[:10]:
            supplier = item.get("nomeFornecedor") or "--"
            value = item.get("valorLiquido") or item.get("valorDocumento") or "--"
            date = item.get("dataDocumento") or "--"
            lines.append(f"- {date} | {supplier} | R$ {value} | {item.get('tipoDespesa') or '--'}")
        return f"Despesas parlamentares publicas de {deputy.get('nome', '--')}:\n\n" + "\n".join(lines)
    if topic == "camara_parties":
        rows = _rows(raw)
        return "Partidos encontrados na Camara:\n\n" + "\n".join(
            f"- {row.get('sigla', '--')} | {row.get('nome', '--')}" for row in rows[:10]
        )
    if topic == "camara_propositions":
        rows = _rows(raw)
        return "Proposicoes recentes/encontradas na Camara:\n\n" + "\n".join(
            f"- {row.get('siglaTipo', '--')} {row.get('numero', '--')}/{row.get('ano', '--')} | {str(row.get('ementa') or '--')[:240]}"
            for row in rows[:10]
        )
    if topic == "camara_votes":
        rows = _rows(raw)
        return "Votacoes recentes da Camara:\n\n" + "\n".join(
            f"- {row.get('dataHoraRegistro', '--')} | {row.get('siglaOrgao', '--')} | {str(row.get('descricao') or '--')[:240]}"
            for row in rows[:10]
        )
    if topic == "bacen_series":
        rows = _rows(raw)
        if not rows and isinstance(raw, list):
            rows = [item for item in raw if isinstance(item, dict)]
        return "Serie publica do Banco Central:\n\n" + "\n".join(
            f"- {row.get('data', '--')}: {row.get('valor', '--')}" for row in rows[-12:]
        )
    if topic == "ibge_population":
        projection = raw.get("projecao") if isinstance(raw, dict) else None
        population = projection.get("populacao") if isinstance(projection, dict) else None
        return f"Projecao populacional do IBGE: {population or '--'}."
    if topic == "ipea_series":
        rows = _rows(raw)
        return "Series encontradas no IPEA:\n\n" + "\n".join(
            f"- {row.get('SERCODIGO') or row.get('codigo') or '--'} | {row.get('SERNOME') or row.get('nome') or '--'}"
            for row in rows[:10]
        )
    if topic == "uf_data":
        data = raw if isinstance(raw, dict) else {}
        region = data.get("regiao") or {}
        return (
            f"UF: {data.get('nome', '--')} ({data.get('sigla', '--')})\n"
            f"Codigo IBGE: {data.get('id', '--')}\n"
            f"Regiao: {region.get('nome', '--')}"
        )
    if topic == "senate_members":
        rows = _rows(raw)
        if not rows and isinstance(raw, dict):
            rows = [item for item in _flatten_records(raw) if "NomeParlamentar" in item or "NomeCompletoParlamentar" in item]
        return "Senadores encontrados na fonte publica do Senado:\n\n" + "\n".join(
            f"- {row.get('NomeParlamentar') or row.get('NomeCompletoParlamentar') or '--'}"
            for row in rows[:10]
        )
    preview = json.dumps(raw, ensure_ascii=False, default=str)[:1200]
    return f"Consulta publica concluida:\n\n{preview}"


def source_url_for(plan: PublicDataPlan) -> str:
    if plan.topic.startswith("camara"):
        return "https://dadosabertos.camara.leg.br/"
    if plan.topic.startswith("senate"):
        return "https://legis.senado.leg.br/dadosabertos/"
    if plan.topic.startswith("bacen"):
        return "https://dadosabertos.bcb.gov.br/"
    if plan.topic.startswith("ibge") or plan.topic == "uf_data":
        return "https://servicodados.ibge.gov.br/"
    if plan.topic.startswith("ipea"):
        return "http://www.ipeadata.gov.br/"
    return "https://github.com/GusFurtado/DadosAbertosBrasil"


def _safe_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return mask_secrets(sanitize_public_data(arguments))


def _flatten_records(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        rows.append(value)
        for item in value.values():
            rows.extend(_flatten_records(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_flatten_records(item))
    return rows
