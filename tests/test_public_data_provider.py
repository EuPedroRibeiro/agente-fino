from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from starlette.requests import Request

from app.agent.core import NexusCore
from app.agent.providers.public_data import PublicDataError
from app.agent.providers.public_data import PublicDataProvider
from app.agent.public_data_router import PublicDataRouter
from app.agent.router import classify_message
from app.agent.schemas.messages import AgentChatRequest
from app.routes.public_data import public_data_query, public_data_status
from app.security.access import is_protected_path
from app.services.public_data import PublicDataService


class FakePublicDataProvider:
    name = "DadosAbertosBrasil/PublicDataProvider"

    def __init__(self, *, error: str | None = None) -> None:
        self.error = error
        self.calls = []

    def status(self):
        return {
            "enabled": True,
            "active": True,
            "available": True,
            "requires_api_key": False,
            "library_installed": False,
        }

    def query(self, plan):
        self.calls.append(plan)
        if self.error:
            raise PublicDataError(self.error)
        if plan.topic == "camara_deputies":
            return {"dados": [{"id": 1, "nome": "Rodrigo Maia", "siglaPartido": "X", "siglaUf": "RJ"}]}
        if plan.topic == "camara_expenses":
            return {
                "deputy": {"id": 1, "nome": "Deputado Teste"},
                "expenses": [{"dataDocumento": "2026-01-01", "nomeFornecedor": "Fornecedor", "valorLiquido": 10}],
            }
        return {"status": "ok"}


class PublicDataProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = Mock()

    def service(self, provider=None):
        return PublicDataService(provider or FakePublicDataProvider(), auditor=self.audit)

    def test_status_does_not_require_api_key(self) -> None:
        status = self.service().status()
        self.assertTrue(status["active"])
        self.assertFalse(status["requires_api_key"])
        self.assertTrue(is_protected_path("/api/public-data/status"))
        self.assertIn("active", public_data_status())

    def test_installed_library_is_used_with_direct_adapter_fallback_available(self) -> None:
        fake_dab = Mock()
        fake_dab.camara.lista_deputados.return_value = {
            "dados": [{"id": 1, "nome": "Deputado Biblioteca", "siglaPartido": "X", "siglaUf": "RJ"}]
        }
        provider = PublicDataProvider()
        plan = PublicDataRouter.plan_query("buscar dados do deputado Biblioteca")
        with (
            patch("app.agent.providers.public_data.importlib.util.find_spec", return_value=object()),
            patch("app.agent.providers.public_data.importlib.import_module", return_value=fake_dab),
            patch.object(provider, "_get_json") as direct_http,
        ):
            result = provider.query(plan)
        self.assertEqual(result["dados"][0]["nome"], "Deputado Biblioteca")
        direct_http.assert_not_called()

    def test_common_cpf_does_not_route_to_public_data(self) -> None:
        message = "Consulte o CPF 20345568796"
        self.assertFalse(PublicDataRouter.should_use_public_data(message))
        self.assertEqual(classify_message(message)["intent"], "cpf_lookup")
        service = self.service()
        result = service.ask(message)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("nao fornece consulta livre de CPF", result["answer"])
        self.assertEqual(service.provider.calls, [])

    def test_public_data_request_routes_to_provider(self) -> None:
        self.assertEqual(classify_message("buscar dados do deputado Rodrigo Maia")["intent"], "public_data_query")
        service = self.service()
        result = service.ask("buscar dados do deputado Rodrigo Maia")
        self.assertEqual(result["intent"], "public_data_query")
        self.assertEqual(result["topic"], "camara_deputies")
        self.assertIn("Rodrigo Maia", result["answer"])
        self.assertEqual(len(service.provider.calls), 1)

    def test_supported_public_topics_route_without_document_lookup(self) -> None:
        messages = (
            "consultar despesas de deputado",
            "dados do IBGE sobre populacao",
            "serie do Banco Central",
            "proposicoes da Camara",
            "votacoes da Camara",
            "dados do Senado",
            "series do IPEA",
            "dados da UF RJ",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(classify_message(message)["intent"], "public_data_query")

    def test_parliamentary_expense_supplier_uses_public_data_before_document_lookup(self) -> None:
        core = NexusCore()
        core.public_data = self.service()
        core.document_lookup = Mock()
        with patch("app.agent.core.production_config_errors", return_value=[]):
            response = core.chat(AgentChatRequest(message="Consulte despesas do deputado Teste com fornecedor CNPJ 00.000.000/0001-00"))
        self.assertEqual(response.intent, "public_data_query")
        self.assertEqual(response.mode, "PUBLIC_DATA")
        self.assertFalse(response.model_used["llm_used"])
        core.document_lookup.handle.assert_not_called()

    def test_provider_error_is_friendly_and_never_raises(self) -> None:
        result = self.service(FakePublicDataProvider(error="fonte fora do ar")).ask("dados do IBGE sobre populacao")
        self.assertEqual(result["status"], "error")
        self.assertIn("Nao consegui concluir", result["answer"])
        self.audit.assert_called_once()

    def test_endpoint_error_returns_valid_structure_not_500(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/public-data/query",
                "headers": [],
                "client": ("testclient", 1234),
                "server": ("testserver", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )
        with patch("app.routes.public_data.service.ask", side_effect=RuntimeError("biblioteca indisponivel")):
            response = public_data_query(request, {"message": "dados do IBGE sobre populacao"})
        self.assertEqual(response["status"], "error")
        self.assertIn("answer", response)

    def test_agent_chat_uses_public_data_without_mcp_or_llm(self) -> None:
        core = NexusCore()
        core.public_data = self.service()
        core.mcp_brasil = Mock()
        core.document_lookup = Mock()
        core.document_lookup.handle.return_value = None
        with patch("app.agent.core.production_config_errors", return_value=[]):
            response = core.chat(AgentChatRequest(message="buscar dados do deputado Rodrigo Maia"))
        self.assertEqual(response.mode, "PUBLIC_DATA")
        self.assertEqual(response.model_used["provider"], "public-data")
        self.assertFalse(response.model_used["llm_used"])
        core.mcp_brasil.ask.assert_not_called()

    def test_technical_drawer_has_public_data_status(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        self.assertIn("publicDataStatus", html)
        self.assertIn("Dados publicos", html)
        self.assertIn("/api/public-data/status", js)


if __name__ == "__main__":
    unittest.main()
