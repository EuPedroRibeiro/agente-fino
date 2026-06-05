from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from starlette.requests import Request

from app.agent import conversation_logs
from app.agent.core import NexusCore
from app.agent.providers.document_lookup import DocumentLookupError
from app.agent.router import classify_message
from app.agent.schemas.messages import AgentChatRequest
from app.agent.security.sanitizer import mask_secrets
from app.routes.agent import agent_chat
from app.security.documents import mask_cnpj, mask_cpf, validate_cpf
from app.services.document_lookup import DocumentLookupService


class FakeDocumentProvider:
    name = "document-lookup"

    def __init__(self, payload: dict | None = None, error: str | None = None) -> None:
        self.payload = payload or {"status": "regular", "nome": "Pessoa Autorizada", "uf": "RJ"}
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def lookup(self, document_type: str, document: str) -> dict:
        self.calls.append((document_type, document))
        if self.error:
            raise DocumentLookupError(self.error)
        return dict(self.payload)

    def status(self) -> dict:
        return {"enabled": True, "configured": True, "available": True}


class DocumentLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit_events: list[tuple[str, dict]] = []

    def service(self, provider: FakeDocumentProvider | None = None, rate_limiter=None) -> DocumentLookupService:
        def auditor(event_type: str, **kwargs):
            self.audit_events.append((event_type, kwargs.get("details") or {}))
            return {"event_type": event_type}

        return DocumentLookupService(
            provider=provider or FakeDocumentProvider(),
            rate_limiter=rate_limiter or (lambda *_args, **_kwargs: True),
            auditor=auditor,
        )

    def test_cpf_validation_is_local_and_uses_verifier_digits(self) -> None:
        provider = FakeDocumentProvider()
        result = self.service(provider).handle("Validar CPF 52998224725")
        self.assertEqual(result["intent"], "cpf_validate")
        self.assertIn("valido", result["answer"])
        self.assertIn("529******25", result["answer"])
        self.assertEqual(provider.calls, [])
        self.assertTrue(validate_cpf("52998224725"))
        self.assertFalse(validate_cpf("11111111111"))

    def test_direct_cpf_lookup_uses_authorized_provider_and_masks_history(self) -> None:
        provider = FakeDocumentProvider()
        result = self.service(provider).handle("Consulte o cpf 20345568796")
        self.assertEqual(result["intent"], "cpf_lookup")
        self.assertEqual(provider.calls, [("cpf", "20345568796")])
        self.assertIn("Pessoa Autorizada", result["answer"])
        self.assertNotIn("20345568796", result["answer"])
        self.assertNotIn("Pessoa Autorizada", result["history_summary"])
        self.assertIn("203******96", result["history_summary"])
        self.assertEqual(self.audit_events[0][0], "cpf_lookup_completed")
        self.assertNotIn("20345568796", str(self.audit_events))

    def test_direct_cnpj_lookup_uses_authorized_provider(self) -> None:
        provider = FakeDocumentProvider({"situacao_cadastral": "ATIVA", "razao_social": "Empresa Autorizada LTDA"})
        result = self.service(provider).handle("Consultar cnpj 00000000000100")
        self.assertEqual(result["intent"], "cnpj_lookup")
        self.assertEqual(provider.calls, [("cnpj", "00000000000100")])
        self.assertIn("Empresa Autorizada LTDA", result["answer"])
        self.assertIn("00.***.***/****-00", result["answer"])
        self.assertEqual(self.audit_events[0][0], "cnpj_lookup_completed")

    def test_external_api_error_returns_valid_friendly_result(self) -> None:
        provider = FakeDocumentProvider(error="provider indisponivel")
        result = self.service(provider).handle("Consulte o cpf 20345568796")
        self.assertEqual(result["status"], "error")
        self.assertIn("Nao consegui consultar", result["answer"])
        self.assertEqual(self.audit_events[0][0], "cpf_lookup_failed")

    def test_blocks_only_clear_mass_or_automated_cpf_abuse(self) -> None:
        provider = FakeDocumentProvider()
        documents = " ".join(
            ["52998224725", "16899535009", "11144477735", "12345678909", "39053344705", "98765432100"]
        )
        result = self.service(provider).handle(f"Consulte os cpf {documents}")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.audit_events[0][0], "cpf_lookup_blocked")

        allowed_provider = FakeDocumentProvider()
        allowed = self.service(allowed_provider).handle("Consulte o cpf 20345568796")
        self.assertEqual(allowed["intent"], "cpf_lookup")
        self.assertEqual(len(allowed_provider.calls), 1)

    def test_rate_limit_failure_does_not_call_provider(self) -> None:
        provider = FakeDocumentProvider()
        result = self.service(provider, rate_limiter=lambda *_args, **_kwargs: False).handle("Consulte o cpf 20345568796")
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(provider.calls, [])

    def test_router_classifies_document_intents_before_public_data_router(self) -> None:
        self.assertEqual(classify_message("Consulte o cpf 20345568796")["intent"], "cpf_lookup")
        self.assertEqual(classify_message("Validar CPF 52998224725")["intent"], "cpf_validate")
        self.assertEqual(classify_message("Consultar cnpj 00000000000100")["intent"], "cnpj_lookup")

    def test_masking_covers_logs_and_audit_payloads(self) -> None:
        payload = mask_secrets({"cpf": "20345568796", "cnpj": "00000000000100"})
        self.assertEqual(payload["cpf"], mask_cpf("20345568796"))
        self.assertEqual(payload["cnpj"], mask_cnpj("00000000000100"))
        self.assertNotIn("20345568796", str(payload))
        self.assertNotIn("00000000000100", str(payload))

    def test_conversation_history_masks_documents(self) -> None:
        repository = Mock()
        repository.add_message.return_value = {"id": 1}
        with patch("app.agent.conversation_logs.get_conversation_repository", return_value=repository):
            conversation_logs.add_message(conversation_id="conv-doc", role="user", content="Consulte CPF 20345568796")
        stored = repository.add_message.call_args.kwargs["content"]
        self.assertIn("203******96", stored)
        self.assertNotIn("20345568796", stored)

    def test_core_document_lookup_does_not_call_mcp_or_llm(self) -> None:
        core = NexusCore()
        core.document_lookup = self.service(FakeDocumentProvider())
        core.mcp_brasil = Mock()
        with patch("app.agent.core.production_config_errors", return_value=[]):
            response = core.chat(AgentChatRequest(message="Consultar cnpj 00000000000100"))
        core.mcp_brasil.ask.assert_not_called()
        self.assertEqual(response.intent, "cnpj_lookup")
        self.assertFalse(response.model_used["llm_used"])
        self.assertEqual(response.model_used["provider"], "document-lookup")

    def test_agent_chat_route_never_leaks_unhandled_error_as_500(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/agent/chat",
                "headers": [],
                "client": ("testclient", 1234),
                "server": ("testserver", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )
        payload = AgentChatRequest(message="Consulte o cpf 20345568796")
        with (
            patch("app.routes.agent.core.chat", side_effect=RuntimeError("provider explodiu")),
            patch("app.routes.agent.audit_event") as audit,
        ):
            response = agent_chat(payload, request)
        self.assertEqual(response["intent"], "chat_error")
        self.assertIn("Nao consegui concluir", response["final_answer"])
        audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
