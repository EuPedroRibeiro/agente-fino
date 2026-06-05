from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings


class DocumentLookupError(RuntimeError):
    pass


class DocumentLookupProvider:
    name = "document-lookup"

    def is_configured(self) -> bool:
        return bool(settings.document_lookup_enabled and settings.document_lookup_base_url)

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": settings.document_lookup_enabled,
            "configured": self.is_configured(),
            "available": self.is_configured(),
            "timeout_seconds": settings.document_lookup_timeout_seconds,
        }

    def lookup(self, document_type: str, document: str) -> dict[str, Any]:
        if document_type not in {"cpf", "cnpj"}:
            raise DocumentLookupError("Tipo de documento nao suportado.")
        if not self.is_configured():
            raise DocumentLookupError("Provider autorizado de consulta documental nao configurado.")

        path_template = settings.document_lookup_cpf_path if document_type == "cpf" else settings.document_lookup_cnpj_path
        path = path_template.format(document=urllib.parse.quote(document), type=document_type)
        url = f"{settings.document_lookup_base_url.rstrip('/')}/{path.lstrip('/')}"
        method = settings.document_lookup_method.upper()
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "AgenteFino-DocumentLookup/1.0",
        }
        if method != "GET":
            body = json.dumps({"document": document, "document_type": document_type}).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if settings.document_lookup_api_key:
            headers[settings.document_lookup_api_key_header] = (
                f"{settings.document_lookup_api_key_prefix}{settings.document_lookup_api_key}"
            )

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=settings.document_lookup_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
        except urllib.error.HTTPError as exc:
            raise DocumentLookupError(f"API autorizada retornou HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise DocumentLookupError("Nao foi possivel conectar ao provider autorizado.") from exc
        except TimeoutError as exc:
            raise DocumentLookupError("A consulta documental excedeu o tempo limite.") from exc
        except json.JSONDecodeError as exc:
            raise DocumentLookupError("O provider autorizado retornou uma resposta invalida.") from exc
        except Exception as exc:
            raise DocumentLookupError(mask_secrets(f"Falha na consulta documental: {exc}")) from exc

        if not isinstance(payload, dict):
            raise DocumentLookupError("O provider autorizado retornou um formato inesperado.")
        return payload
