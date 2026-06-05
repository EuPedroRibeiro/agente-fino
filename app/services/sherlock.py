from __future__ import annotations

import time
from typing import Any, Callable

from app.agent.providers.document_lookup import DocumentLookupError, DocumentLookupProvider
from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.security.audit import audit_event
from app.security.documents import digits_only, mask_cnpj, mask_cpf, validate_cpf, validate_cnpj
from app.services.cnpj_lookup import CnpjLookupError, CnpjLookupService


AuditFunction = Callable[..., dict[str, Any]]


class SherlockService:
    def __init__(
        self,
        *,
        document_provider: DocumentLookupProvider | None = None,
        cnpj_service: CnpjLookupService | None = None,
        auditor: AuditFunction = audit_event,
    ) -> None:
        self.document_provider = document_provider or DocumentLookupProvider()
        self.cnpj_service = cnpj_service or CnpjLookupService(auditor=auditor)
        self.auditor = auditor

    def status(self) -> dict[str, Any]:
        document_status = self.document_provider.status()
        cnpj_status = self.cnpj_service.status()
        return {
            "enabled": settings.sherlock_enabled,
            "active": settings.sherlock_enabled,
            "name": "Sherlock Consultas",
            "cpf_real": "configurado" if document_status.get("configured") else "nao_configurado",
            "cpf_lab": "ativo" if settings.sherlock_cpf_lab_enabled else "inativo",
            "cnpj_provider": cnpj_status.get("provider", "off"),
            "redis_cache": "ativo" if cnpj_status.get("cache", {}).get("redis_available") else "inativo",
            "cache_backend": cnpj_status.get("cache", {}).get("backend", "memory"),
        }

    def validate_cpf_local(self, document: str) -> dict[str, Any]:
        started = time.perf_counter()
        digits = digits_only(document)
        masked = mask_cpf(digits)
        valid = validate_cpf(digits)
        self.auditor("cpf_validate_completed", details={"document": masked, "valid": valid, "module": "sherlock"})
        return {
            "status": "ok",
            "intent": "cpf_validate",
            "document_type": "cpf",
            "document": masked,
            "valid": valid,
            "answer": f"CPF {masked}: {'valido' if valid else 'invalido'}.",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    def simulate_cpf(self, document: str) -> dict[str, Any]:
        started = time.perf_counter()
        digits = digits_only(document)
        masked = mask_cpf(digits)
        if not settings.sherlock_cpf_lab_enabled:
            return self._error("cpf_lab_lookup", masked, "O modo laboratorio de CPF esta desativado.", started)
        if len(digits) != 11:
            return self._error("cpf_lab_lookup", masked, "Informe um CPF com 11 digitos para simular.", started)
        self.auditor("cpf_lab_simulated", details={"document": masked, "module": "sherlock"})
        return {
            "status": "ok",
            "intent": "cpf_lab_lookup",
            "document_type": "cpf",
            "document": masked,
            "laboratory": True,
            "answer": (
                "Modo laboratorio: dados ficticios para estudo.\n\n"
                f"CPF: {masked}\nNome: Pessoa Ficticia de Demonstracao\n"
                "Situacao simulada: regular\nUF simulada: SP"
            ),
            "data": {
                "document": masked,
                "nome": "Pessoa Ficticia de Demonstracao",
                "situacao": "regular",
                "uf": "SP",
                "laboratory": True,
            },
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    def query(self, document: str) -> dict[str, Any]:
        started = time.perf_counter()
        digits = digits_only(document)
        if len(digits) == 11:
            masked = mask_cpf(digits)
            if not self.document_provider.is_configured():
                self.auditor("cpf_lookup_blocked_unconfigured", details={"document": masked, "module": "sherlock"}, severity="warning")
                return self._error(
                    "cpf_lookup",
                    masked,
                    "A consulta real de CPF ainda nao esta configurada no ambiente de producao. "
                    "Posso validar o CPF localmente ou simular uma consulta em modo laboratorio.",
                    started,
                    status="unconfigured",
                )
            try:
                raw = self.document_provider.lookup("cpf", digits)
                self.auditor("cpf_lookup_completed", details={"document": masked, "module": "sherlock"})
                return {
                    "status": "ok",
                    "intent": "cpf_lookup",
                    "document_type": "cpf",
                    "document": masked,
                    "answer": f"Consulta autorizada concluida para CPF {masked}.",
                    "data": _safe_cpf_summary(raw, masked),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                }
            except DocumentLookupError as exc:
                self.auditor("cpf_lookup_failed", details={"document": masked, "error": mask_secrets(str(exc))}, severity="warning")
                return self._error("cpf_lookup", masked, "Nao consegui concluir a consulta real de CPF agora.", started)
        if len(digits) == 14:
            masked = mask_cnpj(digits)
            if not validate_cnpj(digits):
                return self._error("cnpj_lookup", masked, f"CNPJ {masked}: invalido.", started)
            try:
                data = self.cnpj_service.lookup(digits)
                self.auditor("cnpj_lookup_completed", details={"document": masked, "provider": "brasilapi", "module": "sherlock"})
                return {
                    "status": "ok",
                    "intent": "cnpj_lookup",
                    "document_type": "cnpj",
                    "document": masked,
                    "answer": f"Consulta publica concluida para CNPJ {masked}.",
                    "data": data,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                }
            except CnpjLookupError as exc:
                self.auditor("cnpj_lookup_failed", details={"document": masked, "error": mask_secrets(str(exc))}, severity="warning")
                return self._error("cnpj_lookup", masked, str(exc), started)
        return self._error("document_lookup", "***", "Informe um CPF com 11 digitos ou CNPJ com 14 digitos.", started)

    @staticmethod
    def _error(intent: str, masked: str, answer: str, started: float, *, status: str = "error") -> dict[str, Any]:
        return {
            "status": status,
            "intent": intent,
            "document": masked,
            "answer": answer,
            "data": {},
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


def _safe_cpf_summary(raw: dict[str, Any], masked: str) -> dict[str, Any]:
    data = dict(raw.get("data") or raw.get("result") or raw)
    return {
        "document": masked,
        "status": str(data.get("status") or data.get("situacao") or "concluida")[:120],
        "provider": "document_lookup",
    }
