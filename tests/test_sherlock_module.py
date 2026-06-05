from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

from app.agent.core import NexusCore
from app.agent.schemas.messages import AgentChatRequest
from app.routes.sherlock import sherlock_query
from app.security.access import is_protected_path
from app.security.documents import mask_cnpj, mask_cpf, validate_cnpj
from app.services.cnpj_lookup import CnpjLookupService
from app.services.document_lookup import DocumentLookupService
from app.services.sherlock import SherlockService
from app.utils.cache import ConsultaCache, _MEMORY_CACHE, hashed_cache_key


VALID_CPF = "52998224725"
INVALID_CPF = "11111111111"
VALID_CNPJ = "27962372000155"


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeDocumentProvider:
    name = "fake-document-provider"

    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured

    def is_configured(self) -> bool:
        return self.configured

    def status(self) -> dict:
        return {"configured": self.configured, "available": self.configured}

    def lookup(self, document_type: str, document: str) -> dict:
        return {"status": "regular", "nome": "Nao deve ser persistido"}


class FakeCnpjService:
    def status(self) -> dict:
        return {"provider": "brasilapi", "cache": {"backend": "memory", "redis_available": False}}

    def lookup(self, document: str) -> dict:
        return {
            "document": mask_cnpj(document),
            "razao_social": "Empresa Exemplo LTDA",
            "situacao_cadastral": "ATIVA",
            "municipio": "Sao Paulo",
            "uf": "SP",
        }


class SherlockModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        _MEMORY_CACHE.clear()
        self.events: list[tuple[str, dict]] = []

    def auditor(self, event_type: str, **kwargs):
        self.events.append((event_type, kwargs.get("details") or {}))
        return {"event_type": event_type}

    def test_valid_and_invalid_cpf_are_checked_locally(self) -> None:
        service = SherlockService(document_provider=FakeDocumentProvider(), cnpj_service=FakeCnpjService(), auditor=self.auditor)
        valid = service.validate_cpf_local(VALID_CPF)
        invalid = service.validate_cpf_local(INVALID_CPF)
        self.assertTrue(valid["valid"])
        self.assertFalse(invalid["valid"])
        self.assertIn(mask_cpf(VALID_CPF), valid["answer"])
        self.assertNotIn(VALID_CPF, str(valid))

    def test_cpf_lab_returns_only_fictitious_masked_data(self) -> None:
        service = SherlockService(document_provider=FakeDocumentProvider(), cnpj_service=FakeCnpjService(), auditor=self.auditor)
        result = service.simulate_cpf(VALID_CPF)
        self.assertEqual(result["intent"], "cpf_lab_lookup")
        self.assertTrue(result["laboratory"])
        self.assertIn("dados ficticios", result["answer"])
        self.assertNotIn(VALID_CPF, str(result))
        self.assertEqual(self.events[0][0], "cpf_lab_simulated")

    def test_real_cpf_without_provider_is_clear_and_safe(self) -> None:
        service = SherlockService(document_provider=FakeDocumentProvider(configured=False), cnpj_service=FakeCnpjService(), auditor=self.auditor)
        result = service.query(VALID_CPF)
        self.assertEqual(result["status"], "unconfigured")
        self.assertIn("nao esta configurada", result["answer"])
        self.assertNotIn(VALID_CPF, str(result))
        self.assertEqual(self.events[0][0], "cpf_lookup_blocked_unconfigured")

    def test_cpf_list_is_blocked_by_chat_flow(self) -> None:
        service = DocumentLookupService(
            provider=FakeDocumentProvider(),
            cnpj_service=FakeCnpjService(),
            auditor=self.auditor,
            rate_limiter=lambda *_args, **_kwargs: True,
        )
        result = service.handle(f"consultar cpf {VALID_CPF} e 16899535009")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("apenas um CPF", result["answer"])

    def test_cnpj_brasilapi_response_is_selected_and_masked(self) -> None:
        payload = {
            "cnpj": VALID_CNPJ,
            "razao_social": "Empresa Exemplo LTDA",
            "nome_fantasia": "Empresa Exemplo",
            "descricao_situacao_cadastral": "ATIVA",
            "municipio": "Sao Paulo",
            "uf": "SP",
            "cnae_fiscal_descricao": "Tecnologia",
            "campo_extra": "nao deve sair",
        }
        cache = ConsultaCache(enabled=True, redis_url="")
        service = CnpjLookupService(cache=cache, auditor=self.auditor, opener=lambda *_args, **_kwargs: FakeResponse(payload))
        result = service.lookup(VALID_CNPJ)
        self.assertTrue(validate_cnpj(VALID_CNPJ))
        self.assertEqual(result["razao_social"], "Empresa Exemplo LTDA")
        self.assertEqual(result["document"], mask_cnpj(VALID_CNPJ))
        self.assertNotIn("campo_extra", result)
        self.assertNotIn(VALID_CNPJ, str(result))

    def test_invalid_cnpj_and_provider_failure_are_friendly(self) -> None:
        service = SherlockService(document_provider=FakeDocumentProvider(), cnpj_service=FakeCnpjService(), auditor=self.auditor)
        result = service.query("00000000000100")
        self.assertEqual(result["status"], "error")
        self.assertIn("invalido", result["answer"])

        failing = SherlockService(document_provider=FakeDocumentProvider(), cnpj_service=FakeCnpjService(), auditor=self.auditor)
        failing.cnpj_service.lookup = lambda _document: (_ for _ in ()).throw(RuntimeError("api fora do ar"))
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/sherlock/query",
                "headers": [],
                "client": ("testclient", 1234),
                "server": ("testserver", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )
        with patch("app.routes.sherlock.service", failing):
            response = sherlock_query(request, {"document": VALID_CNPJ})
        self.assertEqual(response["status"], "error")
        self.assertIn("Nao consegui", response["answer"])

    def test_cache_uses_hash_and_masks_values(self) -> None:
        cache = ConsultaCache(enabled=True, redis_url="")
        cache.set("cnpj", VALID_CNPJ, {"cnpj": VALID_CNPJ}, ttl_seconds=60)
        key = hashed_cache_key("cnpj", VALID_CNPJ)
        value, hit = cache.get("cnpj", VALID_CNPJ)
        self.assertTrue(hit)
        self.assertIn(key, _MEMORY_CACHE)
        self.assertNotIn(VALID_CNPJ, key)
        self.assertNotIn(VALID_CNPJ, str(value))
        self.assertIn(mask_cnpj(VALID_CNPJ), str(value))

    def test_chat_recognizes_lab_and_public_cnpj_without_llm(self) -> None:
        core = NexusCore()
        core.document_lookup = DocumentLookupService(
            provider=None,
            cnpj_service=FakeCnpjService(),
            auditor=self.auditor,
            rate_limiter=lambda *_args, **_kwargs: True,
        )
        lab = core.chat(AgentChatRequest(message=f"simular consulta cpf {VALID_CPF}"))
        cnpj = core.chat(AgentChatRequest(message=f"consultar cnpj {VALID_CNPJ}"))
        self.assertEqual(lab.intent, "cpf_lab_lookup")
        self.assertFalse(lab.model_used["llm_used"])
        self.assertEqual(cnpj.intent, "cnpj_lookup")
        self.assertFalse(cnpj.model_used["llm_used"])

    def test_page_assets_status_and_auth_protection_exist(self) -> None:
        html = Path("app/templates/sherlock.html").read_text(encoding="utf-8")
        css = Path("app/static/css/sherlock.css").read_text(encoding="utf-8")
        js = Path("app/static/js/sherlock.js").read_text(encoding="utf-8")
        agent_html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        agent_js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        self.assertIn("Sherlock Consultas", html)
        self.assertIn("/api/sherlock/query", js)
        self.assertIn("/api/sherlock/status", agent_js)
        self.assertIn("sherlockBtn", agent_html)
        self.assertIn("sherlockCpfLabStatus", agent_html)
        self.assertIn("backdrop-filter", css)
        self.assertTrue(is_protected_path("/sherlock"))
        self.assertTrue(is_protected_path("/api/sherlock/query"))

    def test_new_module_has_no_hardcoded_secret_or_raw_documents(self) -> None:
        files = [
            Path("app/routes/sherlock.py"),
            Path("app/services/sherlock.py"),
            Path("app/services/cnpj_lookup.py"),
            Path("app/utils/cache.py"),
            Path("app/templates/sherlock.html"),
            Path("app/static/js/sherlock.js"),
        ]
        content = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotIn("sk-proj-", content)
        self.assertNotIn("Bearer ey", content)
        self.assertNotIn(VALID_CPF, content)
        self.assertNotIn(VALID_CNPJ, content)


if __name__ == "__main__":
    unittest.main()
