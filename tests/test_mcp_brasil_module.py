from __future__ import annotations

import unittest
from pathlib import Path

from app.agent.core import NexusCore
from app.agent.schemas.messages import AgentChatRequest
from app.routes.mcp_brasil import mcp_brasil_status
from app.security.access import is_protected_path
from modules.mcp_brasil.client import MCPBrasilClient
from modules.mcp_brasil.router import MCPBrasilRouter
from modules.mcp_brasil.service import MCPBrasilConfig, MCPBrasilService


class FakeMCPBrasilService:
    def ask(self, user_message: str, *, user: str = "local-user") -> dict:
        return {
            "status": "ok",
            "answer": "Consultei fontes publicas via MCP Brasil e encontrei o CEP solicitado.",
            "intent": "cep_lookup",
            "tool": "brasilapi_cep",
            "arguments": {"cep": "27200000"},
            "tool_call": {"status": "ok", "tool": "brasilapi_cep", "latency_ms": 12, "result": {"cep": "27200000"}},
            "latency_ms": 12,
            "web_used": True,
        }

    def status(self) -> dict:
        return {"enabled": True, "available": True, "running": False}


class FailingMCPBrasilService(FakeMCPBrasilService):
    def ask(self, user_message: str, *, user: str = "local-user") -> dict:
        return {
            "status": "ok",
            "answer": "O modulo MCP Brasil esta instalado, mas nao consegui acessar o servidor agora.",
            "intent": "public_data_question",
            "tool": "recomendar_tools",
            "arguments": {"query": user_message},
            "tool_call": {"status": "error", "tool": "recomendar_tools", "latency_ms": 3, "message": "offline"},
            "latency_ms": 3,
            "web_used": False,
        }


class FallbackCepClient(MCPBrasilClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://127.0.0.1:8766")
        self.calls: list[str] = []

    def get_json(self, url: str):
        self.calls.append(url)
        if "brasilapi.com.br/api/cep/v2" in url:
            raise RuntimeError("HTTP 404 ao consultar fonte publica.")
        return {"cep": "27200000", "logradouro": "Rua teste"}


class MCPBrasilModuleTests(unittest.TestCase):
    def test_disabled_config_blocks_module(self) -> None:
        service = MCPBrasilService(
            MCPBrasilConfig(False, "./tools/mcp-brasil", "http", "127.0.0.1", 8766, "none", False, 5)
        )
        self.assertFalse(service.is_enabled())
        result = service.ask("/mcp status")
        self.assertEqual(result["status"], "disabled")
        self.assertIn("desativado", result["answer"])

    def test_status_endpoint_is_available_after_login(self) -> None:
        data = mcp_brasil_status()
        self.assertIn("enabled", data)
        self.assertIn("url", data)
        self.assertTrue(is_protected_path("/api/mcp-brasil/status"))
        self.assertTrue(is_protected_path("/mcp-brasil"))

    def test_router_detects_ibge_selic_cnpj_and_cep(self) -> None:
        self.assertTrue(MCPBrasilRouter.should_use_mcp_brasil("Me mostra dados do IBGE sobre Volta Redonda"))
        self.assertTrue(MCPBrasilRouter.should_use_mcp_brasil("Qual foi a Selic nos ultimos meses?"))
        self.assertTrue(MCPBrasilRouter.should_use_mcp_brasil("Consulta o CNPJ 00.000.000/0001-91"))
        self.assertTrue(MCPBrasilRouter.should_use_mcp_brasil("Consulta o CEP 27200-000"))
        self.assertEqual(MCPBrasilRouter.plan_query("Consulta o CEP 27200-000").tool_name, "brasilapi_cep")
        self.assertEqual(MCPBrasilRouter.plan_query("Qual foi a Selic?").tool_name, "bacen_selic")

    def test_router_does_not_call_mcp_for_common_chat(self) -> None:
        self.assertFalse(MCPBrasilRouter.should_use_mcp_brasil("oi, tudo bem?"))
        self.assertFalse(MCPBrasilRouter.should_use_mcp_brasil("me ajuda a pensar numa rotina de estudos"))

    def test_cep_adapter_falls_back_when_first_source_fails(self) -> None:
        client = FallbackCepClient()
        result = client.brasilapi_cep("27200000")
        self.assertEqual(result["cep"], "27200000")
        self.assertGreaterEqual(len(client.calls), 2)

    def test_chat_uses_mcp_brasil_with_simulated_return(self) -> None:
        core = NexusCore()
        core.mcp_brasil = FakeMCPBrasilService()
        response = core.chat(AgentChatRequest(message="Consulta o CEP 27200-000"))
        self.assertEqual(response.mode, "MCP_BRASIL")
        self.assertEqual(response.intent, "cep_lookup")
        self.assertEqual(response.model_used["provider"], "mcp-brasil")
        self.assertIn("MCP Brasil", response.final_answer)
        self.assertIn("brasilapi_cep", response.selected_tools)

    def test_mcp_failure_does_not_break_chat_response(self) -> None:
        core = NexusCore()
        core.mcp_brasil = FailingMCPBrasilService()
        response = core.chat(AgentChatRequest(message="Busque dados publicos sobre deputados do RJ"))
        self.assertEqual(response.mode, "MCP_BRASIL")
        self.assertIn("nao consegui acessar", response.final_answer)
        self.assertEqual(response.model_used["provider"], "mcp-brasil")

    def test_external_repositories_are_isolated_from_production_repo(self) -> None:
        self.assertFalse(Path("tools/mcp-brasil").exists())
        self.assertFalse(Path("tools/DarkForest-Hunter-OpenAI").exists())
        self.assertTrue(Path("modules/mcp_brasil").exists())
        self.assertTrue(Path("modules/darkforest").exists())

    def test_direct_adapters_remain_available_without_external_repository(self) -> None:
        service = MCPBrasilService(
            MCPBrasilConfig(True, "./tools/mcp-brasil", "http", "127.0.0.1", 8766, "none", False, 5)
        )
        service.client = FallbackCepClient()
        result = service.ask("Consulta o CEP 27200-000")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "brasilapi_cep")

    def test_agent_template_has_hidden_mcp_status(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        self.assertIn("mcpBrasilStatus", html)
        self.assertIn("mcpBrasilBtn", html)
        self.assertIn("/api/mcp-brasil/status", js)
        self.assertIn('window.location.href = "/mcp-brasil"', js)


if __name__ == "__main__":
    unittest.main()
