from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.agent.orchestrator import AgentOrchestrator, clear_local_tool_contexts
from app.agent.router import classify_message
from app.agent.schemas.messages import AgentChatRequest
from app.services.folder_size import clear_folder_size_cache, get_folder_size, resolve_folder_target


class FolderSizeRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_folder_size_cache()
        clear_local_tool_contexts()

    def test_windows_path_routes_to_folder_size(self) -> None:
        route = classify_message(r"C:\Users\Suporte usa quanto de espaco?")
        self.assertEqual(route["intent"], "folder_size")
        self.assertEqual(route["path"], r"C:\Users\Suporte")

    def test_disk_with_users_path_routes_to_folder_size(self) -> None:
        route = classify_message(r"Verifica meu disco c:\users o espaco usado")
        self.assertEqual(route["intent"], "folder_size")
        self.assertEqual(route["path"], r"C:\users")

    def test_usuario_alias_routes_to_users_folder(self) -> None:
        target = resolve_folder_target("Quantos gb a pasta usuario consome?")
        self.assertEqual(target["source"], "users_alias")
        self.assertTrue(str(target["path"]).lower().endswith(r"\users"))
        route = classify_message("Quantos gb a pasta usuario consome?")
        self.assertEqual(route["intent"], "folder_size")

    def test_disk_space_without_folder_stays_disk_space(self) -> None:
        route = classify_message("Quanto espaco tem meu disco C?")
        self.assertEqual(route["intent"], "disk_space")

    def test_top_folder_request_routes_to_folder_usage_top(self) -> None:
        route = classify_message("Quais pastas ocupam mais espaco?")
        self.assertEqual(route["intent"], "folder_usage_top")

    def test_downloads_alias_routes_to_user_downloads(self) -> None:
        target = resolve_folder_target("Downloads ocupa quanto?")
        self.assertEqual(target["source"], "known_folder_alias")
        self.assertTrue(str(target["path"]).lower().endswith(r"\downloads"))
        route = classify_message("Downloads ocupa quanto?")
        self.assertEqual(route["intent"], "folder_size")

    def test_folder_size_does_not_call_llm_or_disk_space(self) -> None:
        fake_result = {
            "path": r"C:\Users\Suporte",
            "size_bytes": 42 * 1024**3,
            "size_gb": 42.0,
            "file_count": 18240,
            "folder_count": 2130,
            "skipped_count": 12,
            "timed_out": False,
            "partial": True,
            "cache_hit": False,
            "elapsed_ms": 25,
        }
        with (
            patch("app.agent.orchestrator.get_folder_size", return_value=fake_result) as folder_size,
            patch("app.agent.orchestrator.get_system_status") as disk_space,
            patch("app.agent.orchestrator.ModelRouter.status") as router_status,
            patch("app.agent.orchestrator.AgentOrchestrator._model_answer") as model_answer,
        ):
            state = AgentOrchestrator().run(AgentChatRequest(message=r"C:\Users\Suporte usa quanto de espaco?", use_web=True))

        folder_size.assert_called_once()
        disk_space.assert_not_called()
        router_status.assert_not_called()
        model_answer.assert_not_called()
        self.assertEqual(state.intent, "folder_size")
        self.assertEqual(state.mode, "LOCAL_TOOL_FAST")
        self.assertEqual(state.selected_tools, ["folder_size"])
        self.assertEqual(state.model_used["provider"], "local-tool")
        self.assertFalse(state.model_used["used_model"])
        self.assertIn(r"C:\Users\Suporte usa aproximadamente 42,00 GB", state.final_answer)
        self.assertNotIn("Disco C:", state.final_answer)

    def test_folder_size_nonexistent_path_is_friendly(self) -> None:
        with patch(
            "app.agent.orchestrator.get_folder_size",
            return_value={
                "path": r"C:\Users\Suporte\XYZ",
                "error": r"Nao encontrei esse caminho: C:\Users\Suporte\XYZ",
                "error_type": "not_found",
                "cache_hit": False,
                "timed_out": False,
                "skipped_count": 0,
            },
        ):
            state = AgentOrchestrator().run(AgentChatRequest(message=r"C:\Users\Suporte\XYZ usa quanto?", use_web=False))

        self.assertEqual(state.intent, "folder_size")
        self.assertIn("Nao consegui calcular o tamanho dessa pasta.", state.final_answer)
        self.assertIn(r"C:\Users\Suporte\XYZ", state.final_answer)

    def test_folder_size_permission_error_does_not_break(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.services.folder_size.os.scandir", side_effect=PermissionError("negado")):
                result = get_folder_size(temp_dir, use_cache=False)

        self.assertEqual(result["skipped_count"], 1)
        self.assertTrue(result["partial"])
        self.assertNotIn("error", result)

    def test_folder_size_cache_hit_on_second_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "arquivo.bin"), "wb") as handle:
                handle.write(b"x" * 1024)

            first = get_folder_size(temp_dir)
            second = get_folder_size(temp_dir)

        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["size_bytes"], second["size_bytes"])

    def test_followup_appdata_uses_contextual_user_profile(self) -> None:
        conversation_id = "ctx-appdata"

        def fake_folder_size(path, **kwargs):
            normalized = str(path).lower()
            if normalized.endswith("\\appdata"):
                return {
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
            return {
                "path": r"C:\Users\Suporte",
                "size_bytes": 35_090_000_000,
                "size_gb": 35.09,
                "file_count": 50000,
                "folder_count": 7000,
                "skipped_count": 2,
                "timed_out": False,
                "partial": False,
                "cache_hit": False,
                "elapsed_ms": 20,
            }

        with (
            patch.dict(os.environ, {"USERPROFILE": r"C:\Users\Suporte", "SystemDrive": "C:"}),
            patch("app.agent.orchestrator.get_folder_size", side_effect=fake_folder_size),
        ):
            orchestrator = AgentOrchestrator()
            first = orchestrator.run(AgentChatRequest(message=r"C:\Users\Suporte ocupa quanto?", conversation_id=conversation_id, use_web=False))
            second = orchestrator.run(AgentChatRequest(message="E a pasta appdata?", conversation_id=conversation_id, use_web=False))

        self.assertEqual(first.intent, "folder_size")
        self.assertEqual(second.intent, "folder_size")
        self.assertEqual(second.model_used["path"], r"C:\Users\Suporte\AppData")
        self.assertIn(r"C:\Users\Suporte\AppData usa aproximadamente", second.final_answer)

    def test_file_count_followup_uses_last_appdata_result(self) -> None:
        conversation_id = "ctx-file-count"
        appdata_result = {
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
        with (
            patch.dict(os.environ, {"USERPROFILE": r"C:\Users\Suporte", "SystemDrive": "C:"}),
            patch("app.agent.orchestrator.get_folder_size", return_value=appdata_result) as folder_size,
        ):
            orchestrator = AgentOrchestrator()
            orchestrator.run(AgentChatRequest(message="E a pasta appdata?", conversation_id=conversation_id, use_web=False))
            state = orchestrator.run(
                AgentChatRequest(
                    message="Se for contar todos os arquivos dela, quantos tem totais no appdata?",
                    conversation_id=conversation_id,
                    use_web=False,
                )
            )

        self.assertEqual(folder_size.call_count, 1)
        self.assertEqual(state.intent, "file_count")
        self.assertEqual(state.mode, "LOCAL_TOOL_FAST")
        self.assertFalse(state.model_used["used_model"])
        self.assertTrue(state.model_used["cache_hit"])
        self.assertTrue(state.model_used["path"].endswith(r"\AppData"))
        self.assertTrue(state.final_answer.startswith(r"C:\Users\Suporte\AppData tem 38.823 arquivos analisados."))
        self.assertNotIn("usa aproximadamente 10,93 GB", state.final_answer.splitlines()[0])

    def test_accept_offer_runs_subfolder_ranking_on_last_path(self) -> None:
        conversation_id = "ctx-offer"
        appdata_result = {
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
            "folders": [
                {"name": "Local", "path": r"C:\Users\Suporte\AppData\Local", "size_gb": 7.4},
                {"name": "Roaming", "path": r"C:\Users\Suporte\AppData\Roaming", "size_gb": 3.2},
            ],
            "skipped": 1,
            "truncated": False,
        }
        with (
            patch.dict(os.environ, {"USERPROFILE": r"C:\Users\Suporte", "SystemDrive": "C:"}),
            patch("app.agent.orchestrator.get_folder_size", return_value=appdata_result),
            patch("app.agent.orchestrator.get_disk_usage_ranking", return_value=ranking) as disk_ranking,
        ):
            orchestrator = AgentOrchestrator()
            orchestrator.run(AgentChatRequest(message="E a pasta appdata?", conversation_id=conversation_id, use_web=False))
            state = orchestrator.run(AgentChatRequest(message="Sim, tudo", conversation_id=conversation_id, use_web=False))

        disk_ranking.assert_called_once()
        self.assertEqual(state.intent, "followup_accept_offer")
        self.assertEqual(state.selected_tools, ["folder_usage_top"])
        self.assertEqual(state.model_used["provider"], "local-tool")
        self.assertFalse(state.model_used["used_model"])
        self.assertIn(r"subpastas que mais ocupam espaco em C:\Users\Suporte\AppData", state.final_answer)
        self.assertIn("1. Local - 7,40 GB", state.final_answer)

    def test_pronoun_file_count_uses_last_path(self) -> None:
        conversation_id = "ctx-pronoun"
        result = {
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
        with patch("app.agent.orchestrator.get_folder_size", return_value=result):
            orchestrator = AgentOrchestrator()
            orchestrator.run(AgentChatRequest(message=r"C:\Users\Suporte\AppData ocupa quanto?", conversation_id=conversation_id, use_web=False))
            state = orchestrator.run(AgentChatRequest(message="quantos arquivos tem nela?", conversation_id=conversation_id, use_web=False))

        self.assertEqual(state.intent, "file_count")
        self.assertEqual(state.model_used["path"], r"C:\Users\Suporte\AppData")
        self.assertTrue(state.final_answer.startswith(r"C:\Users\Suporte\AppData tem 38.823 arquivos analisados."))

    def test_accept_without_offer_asks_for_context(self) -> None:
        state = AgentOrchestrator().run(AgentChatRequest(message="sim", conversation_id="ctx-empty", use_web=False))
        self.assertEqual(state.intent, "followup_accept_offer")
        self.assertEqual(state.mode, "LOCAL_TOOL_FAST")
        self.assertIn("Preciso de um pouco mais de contexto", state.final_answer)


if __name__ == "__main__":
    unittest.main()
