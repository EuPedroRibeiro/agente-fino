from __future__ import annotations

import unittest
from pathlib import Path

from app.agent import conversation_logs
from app.agent.schemas.messages import (
    ConversationCreateRequest,
    MemoryPinRequest,
    MemorySearchRequest,
    PersonalityPatchRequest,
    SmartMemoryCreateRequest,
)
from app.routes import agent as agent_routes
from app.routes.status import read_health


class Premium350Tests(unittest.TestCase):
    def test_health_reports_agente_fino_cut(self) -> None:
        self.assertEqual(read_health()["version"], "2.1.1")

    def test_agent_page_loads_with_new_layout(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        self.assertIn("Agente Fino", html)
        self.assertIn("Pergunte qualquer coisa", html)
        self.assertIn("conversationList", html)
        self.assertIn("retestGeminiBtn", html)
        self.assertIn("technical-toggle", html)
        self.assertIn("detailsDrawer", html)
        self.assertIn("personalityModal", html)
        self.assertIn("memoryModal", html)
        self.assertNotIn("Nexus Core", html)
        self.assertNotIn("Black Gold", html)

    def test_initial_page_has_no_visible_empty_dashboard_cards(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        forbidden = ["Jogo do agente", "Nenhum plano ainda", "Nenhuma fonte consultada", "Matriz IA</h2>\n          <div id=\"catalogBox\" class=\"catalog-grid\">Carregando"]
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, html)

    def test_light_red_css_has_no_old_palette(self) -> None:
        css = Path("app/static/css/agent.css").read_text(encoding="utf-8").lower()
        forbidden = ["#20c997", "#2563eb", "#facc15", "--green", "--blue", "--yellow", "#d4af37", "#c9a227", "#f0d77a", "--gold"]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, css)

    def test_technical_status_is_hidden_in_drawer(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        drawer_start = html.index('id="detailsDrawer"')
        drawer = html[drawer_start:]
        before_drawer = html[:drawer_start]
        for technical in ["geminiStatus", "ollamaStatus", "ragStatus", "webStatus", "modelStatus"]:
            with self.subTest(technical=technical):
                self.assertNotIn(technical, before_drawer)
                self.assertIn(technical, drawer)

    def test_empty_conversation_state_is_discreet(self) -> None:
        js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        self.assertIn("empty-conversations", js)
        self.assertIn("Sem conversas ainda.", js)

    def test_enter_and_shift_enter_behavior_exists(self) -> None:
        js = Path("app/static/js/agent.js").read_text(encoding="utf-8")
        self.assertIn('event.key === "Enter" && !event.shiftKey', js)
        self.assertIn('event.key === "Enter" && event.ctrlKey', js)
        self.assertIn("event.preventDefault();", js)
        self.assertIn("sendMessage();", js)
        self.assertNotIn('event.key === "Enter" && event.shiftKey', js)

    def test_personality_saves(self) -> None:
        data = agent_routes.agent_personality_update(PersonalityPatchRequest(tone="Harvey mode", detail_level="curto", emoji_usage="nunca"))
        self.assertEqual(data["tone"], "Harvey mode")
        self.assertEqual(data["detail_level"], "curto")
        self.assertEqual(data["emoji_usage"], "nunca")

    def test_memory_list_create_and_delete(self) -> None:
        listed = agent_routes.agent_memory()
        self.assertIn("memory", listed)
        created = agent_routes.agent_memory_create(SmartMemoryCreateRequest(category="user_preferences", key="teste-350", value="Prefere respostas premium e diretas."))
        memory_id = created["id"]
        searched = agent_routes.agent_memory_search(MemorySearchRequest(query="premium", limit=10))
        self.assertTrue(any(item["id"] == memory_id for item in searched["results"]))
        pinned = agent_routes.agent_memory_pin(memory_id, MemoryPinRequest(pinned=True))
        self.assertTrue(pinned["pinned"])
        deleted = agent_routes.agent_memory_delete(memory_id)
        self.assertTrue(deleted["deleted"])

    def test_conversation_created_and_message_history_reads(self) -> None:
        created = agent_routes.agent_conversation_create(ConversationCreateRequest(title="Teste premium"))
        conversation_id = created["id"]
        conversation_logs.add_message(conversation_id=conversation_id, role="user", content="Mensagem teste")
        conversation_logs.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content="Resposta teste",
            provider="gemini",
            model="gemini-2.5-flash",
            intent="casual_chat",
            tools_used=[],
            web_sources_count=0,
            latency_ms=123,
        )
        messages = agent_routes.agent_conversation_messages(conversation_id)
        self.assertEqual(len(messages["messages"]), 2)
        deleted = agent_routes.agent_conversation_delete(conversation_id)
        self.assertTrue(deleted["deleted"])

    def test_retest_gemini_endpoint_can_return_status(self) -> None:
        original = agent_routes.core.retest_gemini
        agent_routes.core.retest_gemini = lambda: {
            "gemini_status": "online",
            "selected_provider": "gemini",
            "selected_model": "gemini-2.5-flash",
            "real_llm_enabled": True,
            "fallback_reason": None,
            "ollama_status": "online",
        }
        try:
            response = agent_routes.agent_gemini_retest()
        finally:
            agent_routes.core.retest_gemini = original
        self.assertEqual(response["selected_provider"], "gemini")

    def test_provider_panel_ids_exist(self) -> None:
        html = Path("app/templates/agent.html").read_text(encoding="utf-8")
        for element_id in ["modelStatus", "geminiStatus", "ollamaStatus", "webStatus", "ragStatus", "memoryStatus", "detailsBtn"]:
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, html)


if __name__ == "__main__":
    unittest.main()
