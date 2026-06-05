from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.agent.orchestrator import AgentOrchestrator, clear_local_tool_contexts
from app.agent.router import classify_message
from app.agent.schemas.messages import AgentChatRequest
from app.routes import agent as agent_routes
from app.services.folder_size import resolve_folder_target


class FakeAgentResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self) -> dict:
        return dict(self._payload)


async def _collect_stream(response) -> str:
    parts: list[str] = []
    async for chunk in response.body_iterator:
        parts.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
    return "".join(parts)


def collect_stream(response) -> str:
    return asyncio.run(_collect_stream(response))


class ContextActivityStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_local_tool_contexts()

    def test_yes_accepts_previous_offer_without_switching_to_english(self) -> None:
        conversation_id = "ctx-yes-offer"
        folder_result = {
            "path": r"C:\Users\Suporte\AppData",
            "size_bytes": 10_930_000_000,
            "size_gb": 10.93,
            "file_count": 38823,
            "folder_count": 5470,
            "skipped_count": 8,
            "timed_out": False,
            "partial": True,
            "cache_hit": False,
            "elapsed_ms": 20,
        }
        ranking = {
            "root": r"C:\Users\Suporte\AppData",
            "path": r"C:\Users\Suporte\AppData",
            "folders": [{"name": "Local", "path": r"C:\Users\Suporte\AppData\Local", "size_gb": 7.4}],
            "skipped": 0,
            "truncated": False,
        }
        with (
            patch("app.agent.orchestrator.get_folder_size", return_value=folder_result),
            patch("app.agent.orchestrator.get_disk_usage_ranking", return_value=ranking),
        ):
            orchestrator = AgentOrchestrator()
            orchestrator.run(AgentChatRequest(message=r"C:\Users\Suporte\AppData ocupa quanto?", conversation_id=conversation_id))
            state = orchestrator.run(AgentChatRequest(message="Yes", conversation_id=conversation_id))

        self.assertEqual(state.intent, "followup_accept_offer")
        self.assertEqual(state.mode, "LOCAL_TOOL_FAST")
        self.assertFalse(state.model_used["used_model"])
        self.assertIn("Estas sao as subpastas", state.final_answer)
        self.assertNotIn("what can I assist", state.final_answer.lower())

    def test_language_correction_is_fast_pt_br_and_does_not_use_web(self) -> None:
        with (
            patch("app.agent.orchestrator.perform_web_research") as web_research,
            patch("app.agent.orchestrator.ModelRouter.status") as router_status,
            patch("app.agent.orchestrator.AgentOrchestrator._model_answer") as model_answer,
        ):
            state = AgentOrchestrator().run(
                AgentChatRequest(message="Fala portugues, eu falei em ingles no sarcasmo", use_web=True)
            )

        web_research.assert_not_called()
        router_status.assert_not_called()
        model_answer.assert_not_called()
        self.assertEqual(state.intent, "language_correction")
        self.assertEqual(state.mode, "LOCAL_TOOL_FAST")
        self.assertEqual(state.selected_tools, [])
        self.assertFalse(state.web_used)
        self.assertIn("vou manter portugues", state.final_answer.lower())
        self.assertIn("sarcasmo", state.final_answer.lower())

    def test_file_count_resolves_windows_folder_on_c_drive(self) -> None:
        route = classify_message("Quantos arquivos tem na pasta windows no disco C?")
        self.assertEqual(route["intent"], "file_count")
        self.assertEqual(route["path"], r"C:\Windows")

        result = {
            "path": r"C:\Windows",
            "size_bytes": 26_000_000_000,
            "size_gb": 26.0,
            "file_count": 124321,
            "folder_count": 17000,
            "skipped_count": 4,
            "timed_out": False,
            "partial": True,
            "cache_hit": False,
            "elapsed_ms": 20,
        }
        with patch("app.agent.orchestrator.get_folder_size", return_value=result) as folder_size:
            state = AgentOrchestrator().run(AgentChatRequest(message="Quantos arquivos tem na pasta windows no disco C?"))

        folder_size.assert_called_once()
        self.assertEqual(str(folder_size.call_args.args[0]), r"C:\Windows")
        self.assertEqual(state.intent, "file_count")
        self.assertEqual(state.model_used["provider"], "local-tool")
        self.assertFalse(state.model_used["used_model"])
        self.assertTrue(state.final_answer.startswith(r"C:\Windows tem 124.321 arquivos analisados."))

    def test_system32_natural_path_resolves_to_windows_system32(self) -> None:
        target = resolve_folder_target("pasta system32 no disco C")
        self.assertEqual(target["path"], r"C:\Windows\System32")
        self.assertEqual(target["source"], "natural_language_alias")

    def test_runs_sse_emits_core_events(self) -> None:
        created = agent_routes.agent_run_create(AgentChatRequest(message="oi"))
        run_id = created["run_id"]
        fake = FakeAgentResponse(
            {
                "conversation_id": "run-test",
                "answer": "Fala, Pedro.",
                "final_answer": "Fala, Pedro.",
                "intent": "greeting",
                "category": "open_world",
                "mode": "FAST",
                "web_used": False,
                "sources": [],
                "selected_tools": [],
                "tool_calls": [],
                "model_used": {"provider": "nexus-fast-path", "used_model": False},
                "rag_status": {},
                "web_status": {},
                "risk_level": "low",
                "confidence": 0.9,
                "timings_ms": {"total": 1},
            }
        )
        with patch("app.routes.agent.core.chat", return_value=fake):
            events = agent_routes.agent_run_events(run_id)
            body = collect_stream(events)

        self.assertIn("event: run_started", body)
        self.assertIn("event: route_detected", body)
        self.assertIn("event: finalizing", body)
        self.assertIn("event: run_done", body)

    def test_runs_sse_emits_web_search_events(self) -> None:
        created = agent_routes.agent_run_create(AgentChatRequest(message="pesquise na web sobre atualizacoes do Windows"))
        run_id = created["run_id"]
        fake = FakeAgentResponse(
            {
                "conversation_id": "web-run-test",
                "answer": "Pesquisa concluida.",
                "final_answer": "Pesquisa concluida.",
                "intent": "web_research",
                "category": "web_research",
                "mode": "BALANCED",
                "web_used": True,
                "sources": [{"title": "Microsoft Learn", "url": "https://learn.microsoft.com", "domain": "learn.microsoft.com"}],
                "selected_tools": ["web_search"],
                "tool_calls": [],
                "model_used": {"provider": "local-tool", "used_model": False},
                "rag_status": {},
                "web_status": {"used": True, "sources_read": 1},
                "risk_level": "low",
                "confidence": 0.9,
                "timings_ms": {"total": 10},
            }
        )
        with patch("app.routes.agent.core.chat", return_value=fake):
            events = agent_routes.agent_run_events(run_id)
            body = collect_stream(events)

        self.assertIn("event: web_search_started", body)
        self.assertIn("event: web_source_found", body)
        self.assertIn("event: web_search_done", body)

    def test_agent_frontend_contains_activity_stream_hooks(self) -> None:
        with open("app/templates/agent.html", encoding="utf-8") as html_file:
            html = html_file.read()
        with open("app/static/js/agent.js", encoding="utf-8") as js_file:
            js = js_file.read()
        self.assertIn("activityIndicator", html)
        self.assertIn("/api/agent/runs", js)
        self.assertIn("EventSource", js)
        self.assertIn("run_done", js)


if __name__ == "__main__":
    unittest.main()
