from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.security.audit import audit_event
from app.security.documents import digits_only, mask_cnpj, sanitize_document_payload, validate_cnpj
from app.utils.cache import ConsultaCache, consulta_cache


AuditFunction = Callable[..., dict[str, Any]]


class CnpjLookupError(RuntimeError):
    pass


class CnpjLookupService:
    def __init__(
        self,
        *,
        cache: ConsultaCache = consulta_cache,
        auditor: AuditFunction = audit_event,
        opener=urllib.request.urlopen,
    ) -> None:
        self.cache = cache
        self.auditor = auditor
        self.opener = opener

    def status(self) -> dict[str, Any]:
        return {
            "enabled": settings.cnpj_lookup_enabled,
            "provider": settings.cnpj_lookup_provider if settings.cnpj_lookup_enabled else "off",
            "available": settings.cnpj_lookup_enabled and settings.cnpj_lookup_provider == "brasilapi",
            "timeout_seconds": settings.cnpj_lookup_timeout_seconds,
            "cache": self.cache.status(),
        }

    def lookup(self, document: str) -> dict[str, Any]:
        digits = digits_only(document)
        masked = mask_cnpj(digits)
        if not settings.cnpj_lookup_enabled:
            raise CnpjLookupError("A consulta publica de CNPJ esta desativada.")
        if settings.cnpj_lookup_provider != "brasilapi":
            raise CnpjLookupError("O provider publico de CNPJ configurado nao e suportado.")
        if not validate_cnpj(digits):
            raise CnpjLookupError(f"CNPJ {masked}: invalido.")

        cached, hit = self.cache.get("cnpj_brasilapi", digits)
        self.auditor("cache_hit" if hit else "cache_miss", details={"kind": "cnpj", "document": masked})
        if hit and isinstance(cached, dict):
            return cached

        request = urllib.request.Request(
            f"https://brasilapi.com.br/api/cnpj/v1/{digits}",
            headers={"Accept": "application/json", "User-Agent": "AgenteFino-Sherlock/1.0"},
        )
        try:
            with self.opener(request, timeout=settings.cnpj_lookup_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
        except urllib.error.HTTPError as exc:
            if exc.code in {400, 404}:
                raise CnpjLookupError(f"CNPJ {masked} invalido ou nao encontrado.") from exc
            raise CnpjLookupError(f"BrasilAPI retornou HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise CnpjLookupError("Nao foi possivel conectar a BrasilAPI agora.") from exc
        except TimeoutError as exc:
            raise CnpjLookupError("A consulta de CNPJ excedeu o tempo limite.") from exc
        except json.JSONDecodeError as exc:
            raise CnpjLookupError("A BrasilAPI retornou uma resposta invalida.") from exc
        except Exception as exc:
            raise CnpjLookupError(mask_secrets(f"Falha na consulta publica de CNPJ: {exc}")) from exc

        if not isinstance(payload, dict):
            raise CnpjLookupError("A BrasilAPI retornou um formato inesperado.")
        result = _selected_cnpj_fields(payload, masked)
        self.cache.set("cnpj_brasilapi", digits, result, ttl_seconds=settings.cnpj_cache_ttl_seconds)
        return result


def _selected_cnpj_fields(payload: dict[str, Any], masked: str) -> dict[str, Any]:
    primary_activity = payload.get("cnae_fiscal_descricao")
    if not primary_activity:
        activities = payload.get("cnaes_secundarios") or []
        if activities and isinstance(activities[0], dict):
            primary_activity = activities[0].get("descricao")
    result = {
        "document": masked,
        "razao_social": payload.get("razao_social"),
        "nome_fantasia": payload.get("nome_fantasia"),
        "situacao_cadastral": payload.get("descricao_situacao_cadastral") or payload.get("situacao_cadastral"),
        "municipio": payload.get("municipio"),
        "uf": payload.get("uf"),
        "cnae_fiscal_descricao": primary_activity,
        "provider": "brasilapi",
    }
    return sanitize_document_payload({key: value for key, value in result.items() if value not in (None, "", [], {})})
