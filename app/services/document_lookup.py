from __future__ import annotations

import hashlib
import time
from typing import Any, Callable

from app.agent.providers.document_lookup import DocumentLookupError, DocumentLookupProvider
from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.security.audit import audit_event
from app.security.documents import (
    classify_document_request,
    is_clear_cpf_abuse,
    mask_cnpj,
    mask_cpf,
    sanitize_document_payload,
    validate_cpf,
    validate_cnpj,
)
from app.services.cnpj_lookup import CnpjLookupError, CnpjLookupService
from app.security.rate_limit import allow_request


AuditFunction = Callable[..., dict[str, Any]]
RateLimitFunction = Callable[..., bool]


class DocumentLookupService:
    def __init__(
        self,
        provider: DocumentLookupProvider | None = None,
        *,
        rate_limiter: RateLimitFunction = allow_request,
        auditor: AuditFunction = audit_event,
        cnpj_service: CnpjLookupService | None = None,
    ) -> None:
        self.provider = provider or DocumentLookupProvider()
        self.custom_provider = provider is not None
        self.cnpj_service = cnpj_service or CnpjLookupService(auditor=auditor)
        self.rate_limiter = rate_limiter
        self.auditor = auditor

    def status(self) -> dict[str, Any]:
        status = self.provider.status()
        status["cpf_lab"] = "ativo" if settings.sherlock_cpf_lab_enabled else "inativo"
        status["cnpj_public"] = self.cnpj_service.status()
        return status

    def handle(self, message: str, *, user_id: str = "local-user") -> dict[str, Any] | None:
        route = classify_document_request(message)
        if not route:
            return None
        started = time.perf_counter()
        intent = route["intent"]
        documents = route["documents"]
        document_type = route["document_type"]

        if intent == "cpf_validate":
            answers = [
                f"CPF {mask_cpf(document)}: {'valido' if validate_cpf(document) else 'invalido'}."
                for document in documents
            ]
            self.auditor(
                "cpf_validate_completed",
                details={"documents": [mask_cpf(document) for document in documents], "valid": [validate_cpf(document) for document in documents]},
            )
            return self._result(
                route,
                "\n".join(answers),
                "\n".join(answers),
                started,
                status="ok",
                tool="cpf_validate_local",
            )

        if intent == "cpf_lab_lookup":
            answers = []
            for document in documents:
                masked = mask_cpf(document)
                if not settings.sherlock_cpf_lab_enabled:
                    answers.append("O modo laboratorio de CPF esta desativado.")
                    continue
                answers.append(
                    "Modo laboratorio: dados ficticios para estudo.\n\n"
                    f"CPF: {masked}\nNome: Pessoa Ficticia de Demonstracao\n"
                    "Situacao simulada: regular\nUF simulada: SP"
                )
                self.auditor("cpf_lab_simulated", details={"document": masked})
            return self._result(
                route,
                "\n\n".join(answers),
                f"Simulacao de CPF concluida para {', '.join(mask_cpf(document) for document in documents)}.",
                started,
                status="ok" if settings.sherlock_cpf_lab_enabled else "disabled",
                tool="cpf_lab_simulation",
            )

        if intent == "cpf_lookup" and is_clear_cpf_abuse(message, documents):
            masked = [mask_cpf(document) for document in documents[:5]]
            self.auditor(
                "cpf_lookup_blocked",
                details={"documents": masked, "reason": "mass_or_automated_pattern", "count": len(documents)},
                severity="warning",
            )
            answer = "Bloqueei esta consulta porque ela parece ser uma lista ou consulta automatizada. Envie apenas um CPF por pedido."
            return self._result(route, answer, answer, started, status="blocked", tool="document_lookup")

        limit = settings.cpf_lookup_rate_limit_per_hour if document_type == "cpf" else settings.cnpj_lookup_rate_limit_per_hour
        if not self._consume_rate_limit(document_type, user_id, len(documents), limit):
            event = "cpf_lookup_blocked" if document_type == "cpf" else "cnpj_lookup_failed"
            self.auditor(event, details={"reason": "rate_limit", "limit_per_hour": limit}, severity="warning")
            answer = f"O limite horario de consultas de {document_type.upper()} foi atingido. Tente novamente mais tarde."
            return self._result(route, answer, answer, started, status="rate_limited", tool="document_lookup")

        answers: list[str] = []
        history: list[str] = []
        statuses: list[str] = []
        for document in documents:
            masked = mask_cpf(document) if document_type == "cpf" else mask_cnpj(document)
            event_prefix = "cpf_lookup" if document_type == "cpf" else "cnpj_lookup"
            try:
                if document_type == "cnpj" and not self.custom_provider:
                    if not validate_cnpj(document):
                        raise CnpjLookupError(f"CNPJ {masked}: invalido.")
                    raw = self.cnpj_service.lookup(document)
                else:
                    raw = self.provider.lookup(document_type, document)
                display, status = _format_lookup_response(document_type, masked, raw)
                answers.append(display)
                history.append(f"Consulta autorizada concluida para {document_type.upper()} {masked}. Status: {status}.")
                statuses.append(status)
                self.auditor(
                    f"{event_prefix}_completed",
                    details={"document": masked, "status": status, "provider": self.provider.name},
                )
            except (DocumentLookupError, CnpjLookupError) as exc:
                error = mask_secrets(str(exc))
                if document_type == "cpf" and "nao configurado" in error.lower():
                    answers.append(
                        "A consulta real de CPF ainda nao esta configurada no ambiente de producao. "
                        "Posso validar o CPF localmente ou simular uma consulta em modo laboratorio."
                    )
                else:
                    answers.append(f"Nao consegui consultar {document_type.upper()} {masked} agora. {error}")
                history.append(f"Consulta autorizada falhou para {document_type.upper()} {masked}.")
                statuses.append("error")
                self.auditor(
                    f"{event_prefix}_failed",
                    details={"document": masked, "error": error, "provider": self.provider.name},
                    severity="warning",
                )
            except Exception as exc:
                error = mask_secrets(str(exc))
                answers.append(f"Nao consegui consultar {document_type.upper()} {masked} agora.")
                history.append(f"Consulta autorizada falhou para {document_type.upper()} {masked}.")
                statuses.append("error")
                self.auditor(
                    f"{event_prefix}_failed",
                    details={"document": masked, "error": error, "provider": self.provider.name},
                    severity="error",
                )

        overall = "ok" if statuses and all(status != "error" for status in statuses) else "error"
        return self._result(
            route,
            "\n\n".join(answers),
            "\n".join(history),
            started,
            status=overall,
            tool="document_lookup",
        )

    def _consume_rate_limit(self, document_type: str, user_id: str, count: int, limit: int) -> bool:
        identity = hashlib.sha256((user_id or "local-user").encode("utf-8")).hexdigest()[:20]
        key = f"document_lookup:{document_type}:{identity}"
        return all(self.rate_limiter(key, limit=limit, window_seconds=3600) for _ in range(max(1, count)))

    @staticmethod
    def _result(
        route: dict[str, Any],
        answer: str,
        history_summary: str,
        started: float,
        *,
        status: str,
        tool: str,
    ) -> dict[str, Any]:
        return {
            "intent": route["intent"],
            "category": route["category"],
            "answer": answer,
            "history_summary": history_summary,
            "status": status,
            "tool": tool,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "documents": [
                mask_cpf(document) if route["document_type"] == "cpf" else mask_cnpj(document)
                for document in route["documents"]
            ],
        }


def _format_lookup_response(document_type: str, masked_document: str, raw: dict[str, Any]) -> tuple[str, str]:
    data = dict(raw.get("data") or raw.get("result") or raw)
    data = sanitize_document_payload(data)
    fields = _selected_fields(document_type, data)
    status = str(
        data.get("status")
        or data.get("situacao")
        or data.get("situacao_cadastral")
        or data.get("descricao_situacao_cadastral")
        or data.get("registration_status")
        or "concluida"
    )
    lines = [f"Consulta autorizada concluida para {document_type.upper()} {masked_document}.", f"Status: {status}."]
    lines.extend(f"{label}: {value}" for label, value in fields)
    return "\n".join(lines), status


def _selected_fields(document_type: str, data: dict[str, Any]) -> list[tuple[str, str]]:
    labels = {
        "nome": "Nome",
        "name": "Nome",
        "data_nascimento": "Data de nascimento",
        "birth_date": "Data de nascimento",
        "razao_social": "Razao social",
        "legal_name": "Razao social",
        "nome_fantasia": "Nome fantasia",
        "trade_name": "Nome fantasia",
        "cnae_fiscal_descricao": "Atividade principal",
        "situacao_cadastral": "Situacao cadastral",
        "descricao_situacao_cadastral": "Situacao cadastral",
        "municipio": "Municipio",
        "city": "Municipio",
        "uf": "UF",
        "state": "UF",
    }
    allowed = (
        ("nome", "name", "data_nascimento", "birth_date", "municipio", "city", "uf", "state")
        if document_type == "cpf"
        else (
            "razao_social",
            "legal_name",
            "nome_fantasia",
            "trade_name",
            "situacao_cadastral",
            "descricao_situacao_cadastral",
            "cnae_fiscal_descricao",
            "municipio",
            "city",
            "uf",
            "state",
        )
    )
    selected: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    for key in allowed:
        value = data.get(key)
        label = labels[key]
        if value in (None, "", [], {}) or label in seen_labels:
            continue
        selected.append((label, str(value)[:240]))
        seen_labels.add(label)
    return selected
