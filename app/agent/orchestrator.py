from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.agent import rag
from app.agent.calculator import calculate_expression
from app.agent.conversation_policy import (
    CONVERSATION_INTENTS,
    GENERAL_CONVERSATION_INTENTS,
    INTENT_RULES,
    NEXUS_CONVERSATIONAL_SYSTEM_PROMPT,
    TECHNICAL_INTENTS,
    contains_bad_response_pattern,
    quality_rewrite_instruction,
    tool_for_intent,
)
from app.agent.fusion.engine import FusionEngine
from app.agent.memory import AgentMemory
from app.agent.memory_stores.sqlite_memory import record_model_call, upsert_machine_profile
from app.agent.nodes import perform_web_research
from app.agent.personality import build_personality_prompt
from app.agent.providers.model_router import ModelRouter
from app.agent.providers.provider_status_cache import STATUS_CACHE
from app.agent.router import classify_message, normalize_for_intent, web_needed
from app.agent.schemas.evidence import EvidenceItem
from app.agent.state import AgentState
from app.core.config import settings
from app.core.runtime import is_cloud
from app.services.disk_usage import get_disk_usage_ranking
from app.services.folder_size import get_folder_size, resolve_folder_target
from app.services.report import generate_technical_report
from app.services.system_info import get_installed_printers, get_network_adapters, get_network_configuration, get_service_status, get_system_status


READ_ONLY_TOOLS = {
    "analyze_pc",
    "folder_size",
    "disk_usage",
    "printer_status",
    "network_info",
    "web_search",
    "rag_search",
    "memory_search",
    "memory_save",
}

STRUCTURED_INTENTS = CONVERSATION_INTENTS | {"normal_chat"}

NEXUS_SYSTEM_PROMPT = NEXUS_CONVERSATIONAL_SYSTEM_PROMPT

FAST_PATH_INTENTS = {
    "greeting",
    "casual_chat",
    "general_opinion",
    "football_opinion",
    "sports_opinion",
    "music_opinion",
    "movie_opinion",
    "gaming_opinion",
}

FAST_PATH_MESSAGES = {
    "oi",
    "ola",
    "olá",
    "e ai",
    "e aí",
    "bom dia",
    "boa tarde",
    "boa noite",
    "tudo bem",
    "tudo bem?",
    "como voce esta",
    "como você está",
    "teste",
    "obrigado",
    "obrigada",
    "valeu",
    "kkkk",
    "top",
    "gostei",
    "me responde rapido",
    "me responde rápido",
}
LOCAL_TOOL_FAST_INTENTS = {
    "disk_space",
    "storage_status",
    "ram_status",
    "cpu_status",
    "local_ip_status",
    "uptime_status",
    "spooler_status",
    "simple_pc_metric",
    "folder_size",
    "file_count",
    "followup_accept_offer",
    "language_correction",
}

LOCAL_TOOL_FOR_INTENT = {
    "disk_space": "disk_space",
    "storage_status": "disk_space",
    "ram_status": "ram_status",
    "cpu_status": "cpu_status",
    "local_ip_status": "local_ip_status",
    "uptime_status": "uptime_status",
    "spooler_status": "spooler_status",
    "simple_pc_metric": "system_status",
    "folder_size": "folder_size",
    "file_count": "folder_size",
    "followup_accept_offer": "folder_usage_top",
    "language_correction": "language_policy",
}

GB = 1024**3
LOCAL_CONTEXT_TTL_SECONDS = 300
COUNT_CONTEXT_TTL_SECONDS = 120
MAX_LOCAL_CONTEXTS = 300

_LOCAL_TOOL_CONTEXTS: dict[str, dict[str, Any]] = {}


def clear_local_tool_contexts() -> None:
    _LOCAL_TOOL_CONTEXTS.clear()


class AgentOrchestrator:
    def __init__(self) -> None:
        self.memory = AgentMemory()
        self.router = ModelRouter()

    def run(self, request, decision=None) -> AgentState:
        state = AgentState(
            conversation_id=request.conversation_id or str(uuid4()),
            user_id=request.user_id,
            user_message=request.message,
        )
        started = time.perf_counter()
        state.normalized_message = normalize_for_intent(request.message)
        classification = dict(decision.route) if decision is not None else classify_message(request.message)
        if decision is not None:
            classification["intent"] = decision.execution_intent
            classification["category"] = decision.category
        state.intent = classification["intent"]
        state.category = classification["category"]
        if classification.get("path"):
            state.system_context["folder_target"] = {
                "path": classification.get("path"),
                "source": classification.get("path_source"),
            }
        local_context = _get_local_context(state)
        _apply_local_followup_context(state, local_context)
        state.web_needed = web_needed(request.message, state.intent)
        if state.intent in LOCAL_TOOL_FAST_INTENTS:
            return self._run_local_tool_fast(state, started)
        if _should_fast_path(state, request):
            return self._run_fast_path(state, started)

        state.rag_status = rag.status()

        provider_status = self.router.status()
        providers = self.router.provider_chain(provider_status)
        state.system_context["provider"] = provider_status
        state.mode = "BALANCED"

        route_provider = next((candidate for candidate in providers if candidate.name == "gemini"), None)
        if route_provider and state.intent in {"general_question", "clarification_needed"}:
            self._apply_structured_route(state, route_provider)
            state.web_needed = web_needed(request.message, state.intent)

        selected_tools = self._select_tools(state, use_web=request.use_web)
        if decision is not None:
            authorized = set(decision.selected_tools)
            denied = [tool for tool in selected_tools if tool not in authorized]
            selected_tools = [tool for tool in selected_tools if tool in authorized]
            if denied:
                state.system_context["intelligence_tool_denials"] = denied
                state.warnings.append("Ferramentas fora da decisao autorizada foram bloqueadas.")
        state.selected_tools = selected_tools
        state.mode = _logical_mode_for(state, selected_tools, providers)
        providers = self.router.provider_chain_for_mode(state.mode)
        provider = providers[0]
        state.system_context["fusion_mode"] = state.mode
        for tool_name in selected_tools:
            state.tool_calls.append(self._run_tool(tool_name, state))

        if state.intent == "calculation_query":
            calculation = calculate_expression(state.user_message)
            state.final_answer = f"{calculation.display_expression} = {calculation.result}" if calculation.ok else f"Nao consegui calcular isso com seguranca: {calculation.error}"
            state.confidence = 0.98
        elif state.intent in {"time_query", "date_query"}:
            state.final_answer = _fallback_open_chat(state)
            state.confidence = 0.98
        elif provider.name != "local-rules":
            state.final_answer = self._model_answer(state, providers)
            if not state.final_answer:
                state.final_answer = self._fallback_answer(state)
        else:
            state.final_answer = self._fallback_answer(state)

        state.final_answer = self._post_process_final_answer(state, providers)
        if state.confidence <= 0.5:
            state.confidence = self._confidence(state, provider.name)
        state.timings_ms["total"] = int((time.perf_counter() - started) * 1000)
        if not state.model_used:
            state.model_used = {"provider": "local-rules", "model": "deterministic-tools", "used_model": False, "reason": "Nenhum provider real disponivel."}
        return state

    def _run_fast_path(self, state: AgentState, started: float) -> AgentState:
        state.mode = "FAST"
        state.selected_tools = []
        state.rag_status = {"used": False, "skipped": "fast_path"}
        state.web_status = {"used": False, "skipped": "fast_path"}
        state.system_context["fast_path"] = {
            "used_rag": False,
            "used_web": False,
            "used_memory": False,
            "used_verifier": False,
            "tools_used": [],
        }
        providers = self.router.provider_chain_for_mode("FAST", direct=True)
        instant_reply = _instant_fast_reply(state, self.router)
        if instant_reply:
            state.final_answer = instant_reply
            state.model_used = {
                "provider": "nexus-fast-path",
                "model": "deterministic-micro-reply",
                "used_model": False,
                "mode": "FAST",
                "latency_ms": 0,
                "provider_latency_ms": 0,
                "provider_status_cache_hit": True,
                "used_verifier": False,
                "used_rag": False,
                "used_web": False,
                "used_memory": False,
                "fallback": True,
                "fallback_reason": "Sem provider cloud rapido cacheado; micro-resposta local para saudacao simples.",
                "attempts": [],
            }
            state.confidence = 0.96
            state.timings_ms["total"] = int((time.perf_counter() - started) * 1000)
            return state
        messages = [
            {
                "role": "system",
                "content": (
                    "Voce e o Agente Fino. Responda em portugues do Brasil, natural, curto e direto. "
                    "Esta e uma conversa simples; nao use diagnostico, web, RAG, plano ou explicacao longa."
                ),
            },
            {"role": "user", "content": state.user_message},
        ]
        attempts: list[dict[str, Any]] = []
        for provider in providers:
            if provider.name == "local-rules":
                break
            remaining = settings.fast_total_timeout_seconds - (time.perf_counter() - started)
            if remaining <= 0:
                break
            provider_started = time.perf_counter()
            response = _call_provider_chat(
                provider,
                messages,
                temperature=0.35,
                max_tokens=32,
                timeout_seconds=max(0.5, min(_provider_timeout_for("FAST", provider.name), remaining)),
            )
            latency_ms = int((time.perf_counter() - provider_started) * 1000)
            attempts.append(
                {
                    "provider": response.provider,
                    "model": response.model,
                    "used_model": response.used_model,
                    "latency_ms": latency_ms,
                    "error": None if response.used_model else response.text[:500],
                    "error_type": response.error_type,
                }
            )
            STATUS_CACHE.set_status(
                response.provider,
                _provider_status_payload(response.provider, response.model, response.used_model, response.text),
                error=None if response.used_model else response.text,
            )
            if response.used_model and response.text:
                state.final_answer = response.text.strip()
                state.model_used = {
                    "provider": response.provider,
                    "model": response.model,
                    "used_model": True,
                    "mode": "FAST",
                    "latency_ms": latency_ms,
                    "provider_latency_ms": latency_ms,
                    "provider_status_cache_hit": False,
                    "used_verifier": False,
                    "used_rag": False,
                    "used_web": False,
                    "used_memory": False,
                    "fallback": len(attempts) > 1,
                    "fallback_reason": attempts[0]["error"] if len(attempts) > 1 else None,
                    "attempts": attempts,
                }
                state.confidence = 0.9
                break

        if not state.final_answer:
            state.final_answer = _fallback_open_chat(state)
            state.model_used = {
                "provider": "local-rules",
                "model": "deterministic-fast-path",
                "used_model": False,
                "mode": "FAST",
                "used_verifier": False,
                "used_rag": False,
                "used_web": False,
                "used_memory": False,
                "fallback": True,
                "fallback_reason": attempts[-1]["error"] if attempts else "Nenhum provider rapido configurado.",
                "attempts": attempts,
            }
            state.confidence = 0.78

        if contains_bad_response_pattern(state.final_answer):
            state.final_answer = _local_quality_rewrite(state, state.final_answer)
        state.timings_ms["total"] = int((time.perf_counter() - started) * 1000)
        state.timings_ms["provider"] = int(state.model_used.get("provider_latency_ms", 0) or 0)
        return state

    def _run_local_tool_fast(self, state: AgentState, started: float) -> AgentState:
        state.mode = "LOCAL_TOOL_FAST"
        tool_name = LOCAL_TOOL_FOR_INTENT.get(state.intent, "system_status")
        state.selected_tools = [] if state.intent == "language_correction" else [tool_name]
        state.web_needed = False
        state.web_used = False
        state.rag_status = {"used": False, "skipped": "local_tool_fast"}
        state.web_status = {"used": False, "skipped": "local_tool_fast"}
        state.system_context["local_tool_fast"] = {
            "intent": state.intent,
            "mode": state.mode,
            "tool": tool_name,
            "llm_used": False,
            "web_used": False,
            "rag_used": False,
            "verifier_used": False,
            "answer_priority_applied": True,
        }

        tool_started = time.perf_counter()
        call = {"name": tool_name, "status": "success", "risk_level": "low", "requires_confirmation": False}
        try:
            if state.intent == "language_correction":
                result = {"language": "pt-BR", "updated": True}
                call["result"] = result
                state.final_answer = _language_correction_answer(state)
                _remember_language_context(state, "pt-BR")
            elif state.intent in {"folder_size", "file_count"}:
                target = _resolve_folder_target_for_state(state)
                result = _folder_result_for_state(state, target)
                if result.get("error"):
                    call["status"] = "error"
                call["result"] = result
                state.final_answer = _file_count_answer(result) if state.intent == "file_count" else _folder_size_answer(result)
                _remember_local_tool_context(state, result, offer="show_top_subfolders")
            elif state.intent == "followup_accept_offer":
                result = _run_followup_offer(state)
                if result.get("error"):
                    call["status"] = "error"
                call["result"] = result
                state.final_answer = _folder_size_answer(result) if result.get("tool") == "folder_size" else _folder_usage_top_answer(result)
                if not result.get("error") and result.get("tool") == "folder_usage_top":
                    _remember_ranking_context(state, result)
                elif not result.get("error") and result.get("tool") == "folder_size":
                    _remember_local_tool_context(state, result, offer="show_top_subfolders")
            elif state.intent == "spooler_status":
                result = {"spooler": get_service_status("Spooler")}
                call["result"] = result
                state.final_answer = _local_metric_answer(state.intent, result)
            else:
                result = get_system_status()
                call["result"] = result
                state.final_answer = _local_metric_answer(state.intent, result)
            state.evidence.append(
                EvidenceItem(
                    source_type="local_tool",
                    title=f"Metrica local rapida: {tool_name}",
                    content=state.final_answer[:1200],
                    score=1.0,
                    metadata={"tool": tool_name, "mode": state.mode},
                )
            )
            state.confidence = 0.62 if call["status"] == "error" else 0.98
        except Exception as exc:
            call["status"] = "error"
            call["error"] = str(exc)
            state.errors.append(f"{tool_name}: {exc}")
            state.final_answer = "Nao consegui ler essa metrica local agora. Nada foi alterado no PC."
            state.confidence = 0.35

        local_tool_latency_ms = int((time.perf_counter() - tool_started) * 1000)
        total_latency_ms = int((time.perf_counter() - started) * 1000)
        performance_warning = total_latency_ms > 5000
        call["latency_ms"] = local_tool_latency_ms
        state.tool_calls.append(call)
        state.timings_ms["local_tool"] = local_tool_latency_ms
        state.timings_ms["provider"] = 0
        state.timings_ms["total"] = total_latency_ms
        state.model_used = {
            "provider": "local-tool",
            "model": "deterministic-local-metric",
            "used_model": False,
            "mode": state.mode,
            "tool": tool_name,
            "llm_used": False,
            "used_web": False,
            "used_rag": False,
            "used_verifier": False,
            "answer_priority_applied": True,
            "local_tool_latency_ms": local_tool_latency_ms,
            "total_latency_ms": total_latency_ms,
            "performance_warning": performance_warning,
            "path": call.get("result", {}).get("path") if isinstance(call.get("result"), dict) else None,
            "cache_hit": call.get("result", {}).get("cache_hit") if isinstance(call.get("result"), dict) else None,
            "timeout": (call.get("result", {}).get("timed_out") or call.get("result", {}).get("truncated")) if isinstance(call.get("result"), dict) else None,
            "skipped_count": (call.get("result", {}).get("skipped_count") if call.get("result", {}).get("skipped_count") is not None else call.get("result", {}).get("skipped")) if isinstance(call.get("result"), dict) else None,
            "fallback": False,
            "fallback_reason": None,
        }
        state.system_context["local_tool_fast"].update(
            {
                "local_tool_latency_ms": local_tool_latency_ms,
                "total_latency_ms": total_latency_ms,
                "performance_warning": performance_warning,
                "path": state.model_used.get("path"),
                "cache_hit": state.model_used.get("cache_hit"),
                "timeout": state.model_used.get("timeout"),
                "skipped_count": state.model_used.get("skipped_count"),
            }
        )
        if performance_warning:
            state.warnings.append("Consulta local simples passou de 5 segundos.")
        return state

    def _select_tools(self, state: AgentState, *, use_web: bool) -> list[str]:
        text = state.normalized_message
        tools: list[str] = []
        if is_cloud():
            if use_web and web_needed(state.user_message, state.intent):
                tools.append("web_search")
            if state.intent == "memory_search" or _asks_memory(text):
                tools.append("memory_search")
            if state.intent == "memory_save" or _asks_memory_save(text):
                tools.append("memory_save")
            return list(dict.fromkeys(tools))
        mapped_tool = tool_for_intent(state.intent)
        if mapped_tool and mapped_tool != "web_search":
            tools.append(mapped_tool)
        if mapped_tool == "web_search" and use_web:
            tools.append("web_search")
        if state.intent in {"pc_diagnostic", "report_analysis", "analyze_pc"}:
            tools.append("analyze_pc")
        if state.intent == "printer_status" or state.category == "printer" or "impressora" in text or "spooler" in text:
            tools.append("printer_status")
        if state.intent == "network_info" or state.category == "network" or any(word in text for word in ["rede", "dns", "gateway", "ip local"]):
            tools.append("network_info")
        if use_web and web_needed(state.user_message, state.intent):
            tools.append("web_search")
        if settings.rag_enabled and (state.intent == "rag_search" or _should_use_rag(state)):
            tools.append("rag_search")
        if state.intent == "memory_search" or _asks_memory(text):
            tools.append("memory_search")
        if state.intent == "memory_save" or _asks_memory_save(text):
            tools.append("memory_save")
        return list(dict.fromkeys(tools))

    def _run_tool(self, tool_name: str, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        call = {"name": tool_name, "status": "success", "risk_level": "low", "requires_confirmation": False}
        try:
            if tool_name == "analyze_pc":
                result = generate_technical_report(register_log=True, deep=False)
                hostname = result.get("summary", {}).get("hostname")
                if hostname:
                    upsert_machine_profile(hostname, result)
                state.local_report = result
                state.evidence.append(EvidenceItem(source_type="local_report", title="Relatorio local do PC", content=_compact_report_text(result), score=1.0))
            elif tool_name == "folder_size":
                target = state.system_context.get("folder_target") or resolve_folder_target(state.user_message)
                result = get_folder_size(target.get("path") or "", max_seconds=10, max_entries=180_000)
                result["path_source"] = target.get("source")
                state.evidence.append(EvidenceItem(source_type="local_tool", title="Tamanho de pasta", content=_folder_size_answer(result), score=1.0, metadata={"tool": tool_name, "path": result.get("path")}))
            elif tool_name == "disk_usage":
                result = get_disk_usage_ranking(limit=10, max_depth=3, max_seconds=10)
                state.evidence.append(EvidenceItem(source_type="local_tool", title="Ranking de uso de disco", content=_disk_usage_text(result), score=1.0, metadata={"tool": tool_name}))
            elif tool_name == "printer_status":
                result = {"spooler": get_service_status("Spooler"), "printers": get_installed_printers()}
            elif tool_name == "network_info":
                result = {"configuration": get_network_configuration(), "adapters": get_network_adapters()}
            elif tool_name == "web_search":
                research = perform_web_research(state.user_message, official_first=True)
                result = {
                    "web_used": research["web_used"],
                    "searched_at": research["searched_at"],
                    "results": research["results"],
                    "sources": [source.model_dump() for source in research["sources"]],
                    "warnings": research["warnings"],
                }
                state.web_used = research["web_used"]
                state.searched_at = research["searched_at"]
                state.web_context = research["results"]
                state.citations = research["sources"]
                state.web_status = {"used": state.web_used, "sources_read": len(state.citations), "searched_at": state.searched_at}
            elif tool_name == "rag_search":
                result = {"status": state.rag_status, "results": rag.search(state.user_message, category=_rag_category(state), limit=6)}
                state.rag_context = result["results"]
                for item in state.rag_context[:4]:
                    state.evidence.append(EvidenceItem(source_type="rag", title=item.get("title", "RAG"), content=item.get("content", ""), score=float(item.get("score", 0)), metadata={"backend": item.get("backend", state.rag_status.get("honest_status"))}))
            elif tool_name == "memory_search":
                result = {"results": self.memory.search(state.user_id, state.user_message, limit=8)}
                state.memory_context = result["results"]
            elif tool_name == "memory_save":
                note = _memory_note(state.user_message)
                memory_id = self.memory.save_note(state.user_id, "Nota do usuario", note, tags=["user", "manual"])
                result = {"saved": True, "id": memory_id, "content": note}
            else:
                result = {"error": "Ferramenta desconhecida."}
                call["status"] = "error"
            call["result"] = result
        except Exception as exc:
            call["status"] = "error"
            call["error"] = str(exc)
            state.errors.append(f"{tool_name}: {exc}")
        call["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return call

    def _apply_structured_route(self, state: AgentState, provider) -> None:
        started = time.perf_counter()
        intent_list = ", ".join(sorted(STRUCTURED_INTENTS))
        prompt = (
            "Classifique a mensagem em JSON puro, sem markdown. "
            f"Use exatamente uma destas intents: {intent_list}.\n"
            "Não use web_research se o usuário pediu opinião sem pesquisar. "
            "Não transforme conversa comum em diagnóstico técnico.\n"
            "Formato: {\"intent\":\"...\",\"category\":\"open_world|personal|relationship|career|money|sports|football|culture|games|shopping|technology|system|storage|printer|network|web_research|memory|performance|security\",\"confidence\":0.0}\n"
            f"Mensagem: {state.user_message}"
        )
        response = _call_provider_chat(
            provider,
            [
                {"role": "system", "content": "Você classifica intenção para um agente conversacional amplo e técnico. Responda só JSON válido."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=120,
            timeout_seconds=settings.fast_provider_timeout_seconds,
        )
        state.timings_ms["classify_model"] = int((time.perf_counter() - started) * 1000)
        if not response.used_model:
            state.system_context["structured_route_error"] = response.text[:300]
            return
        route = _parse_route_json(response.text)
        if not route:
            state.system_context["structured_route_error"] = f"JSON invalido: {response.text[:200]}"
            return
        intent = route.get("intent")
        if intent not in STRUCTURED_INTENTS:
            return
        state.system_context["structured_route"] = route
        _apply_route_to_state(state, route)

    def _model_answer(self, state: AgentState, providers: list) -> str:
        prompt = _build_prompt(state)
        attempts: list[dict[str, Any]] = []
        for provider in providers:
            if provider.name == "local-rules":
                continue
            started = time.perf_counter()
            response = _call_provider_chat(
                provider,
                self._messages_for_model(state, prompt),
                temperature=_temperature_for(state),
                max_tokens=_max_tokens_for(state),
                timeout_seconds=_provider_timeout_for(state.mode, provider.name),
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            attempt = {
                "provider": response.provider,
                "model": response.model,
                "used_model": response.used_model,
                "latency_ms": latency_ms,
                "error": None if response.used_model else response.text[:500],
            }
            attempts.append(attempt)
            record_model_call(
                user_id=state.user_id,
                conversation_id=state.conversation_id,
                provider=response.provider,
                model=response.model,
                used_model=response.used_model,
                latency_ms=latency_ms,
                success=response.used_model,
                error=None if response.used_model else response.text[:500],
            )
            if response.used_model and response.text:
                state.model_used = {
                    "provider": response.provider,
                    "model": response.model,
                    "used_model": True,
                    "latency_ms": latency_ms,
                    "fallback": len(attempts) > 1,
                    "fallback_reason": attempts[0]["error"] if len(attempts) > 1 else None,
                    "attempts": attempts,
                }
                state.confidence = self._confidence(state, response.provider)
                return response.text.strip()
            state.warnings.append(f"Provider {response.provider} falhou; tentando fallback.")
        state.model_used = {
            "provider": "local-rules",
            "model": "deterministic-tools",
            "used_model": False,
            "fallback": True,
            "fallback_reason": attempts[-1]["error"] if attempts else "Nenhum provider real disponivel.",
            "attempts": attempts,
        }
        return ""

    def _post_process_final_answer(self, state: AgentState, providers: list) -> str:
        answer = (state.final_answer or "").strip()
        if not answer or not contains_bad_response_pattern(answer):
            return answer

        state.warnings.append("Resposta reprocessada por padrão evasivo ou robótico.")
        rewrite_prompt = quality_rewrite_instruction(answer, state.user_message)
        for provider in providers:
            if provider.name == "local-rules":
                continue
            response = _call_provider_chat(
                provider,
                [
                    {"role": "system", "content": _system_prompt_for(state)},
                    {"role": "user", "content": rewrite_prompt},
                ],
                temperature=0.25,
                max_tokens=280,
                timeout_seconds=_provider_timeout_for(state.mode, provider.name),
            )
            if response.used_model and response.text and not contains_bad_response_pattern(response.text):
                state.system_context["quality_rewrite"] = {"provider": response.provider, "model": response.model}
                return response.text.strip()
        return _local_quality_rewrite(state, answer)

    def _messages_for_model(self, state: AgentState, prompt: str) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": _system_prompt_for(state)}]
        for turn in self.memory.recent_conversation_turns(state.user_id, state.conversation_id, limit=4):
            messages.append({"role": "user", "content": str(turn.get("user_message", ""))[:1200]})
            messages.append({"role": "assistant", "content": str(turn.get("agent_response", ""))[:1200]})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _fallback_answer(self, state: AgentState) -> str:
        if any(call["name"] == "memory_search" for call in state.tool_calls):
            result = _tool_result(state, "memory_search")
            return _memory_text(result)
        if state.intent in GENERAL_CONVERSATION_INTENTS or state.intent in {"identity_query", "time_query", "date_query", "clarification_needed", "safe_refusal"}:
            return _fallback_open_chat(state)
        if any(call["name"] == "folder_size" for call in state.tool_calls):
            result = _tool_result(state, "folder_size")
            return _folder_size_answer(result)
        if any(call["name"] == "disk_usage" for call in state.tool_calls):
            result = _tool_result(state, "disk_usage")
            return _disk_usage_text(result)
        if any(call["name"] == "analyze_pc" for call in state.tool_calls):
            return _report_text(state.local_report or {})
        if any(call["name"] == "web_search" for call in state.tool_calls):
            result = _tool_result(state, "web_search")
            return _web_text(result)
        if state.rag_context:
            lines = ["Encontrei isto na base local:"]
            lines.extend(f"- {item.get('title')}: {item.get('content')}" for item in state.rag_context[:4])
            return "\n".join(lines)
        return _fallback_open_chat(state)

    def _confidence(self, state: AgentState, provider_name: str) -> float:
        confidence = 0.42
        if provider_name != "local-rules":
            confidence += 0.25
        if state.tool_calls:
            confidence += 0.16
        if state.rag_context:
            confidence += 0.08
        if state.citations:
            confidence += 0.08
        return min(confidence, 0.94)


def _context_key(state: AgentState) -> str:
    return f"{state.user_id}:{state.conversation_id}"


def _get_local_context(state: AgentState) -> dict[str, Any] | None:
    _cleanup_local_contexts()
    context = _LOCAL_TOOL_CONTEXTS.get(_context_key(state))
    if not context:
        return None
    if time.time() - float(context.get("timestamp", 0)) > LOCAL_CONTEXT_TTL_SECONDS:
        _LOCAL_TOOL_CONTEXTS.pop(_context_key(state), None)
        return None
    return context


def _remember_local_tool_context(state: AgentState, result: dict[str, Any], *, offer: str | None = None) -> None:
    path = result.get("path")
    if not path or result.get("error"):
        return
    _cleanup_local_contexts()
    _LOCAL_TOOL_CONTEXTS[_context_key(state)] = {
        "language": "pt-BR",
        "last_tool": state.intent,
        "last_path": path,
        "last_result": dict(result),
        "last_offer": offer,
        "last_offer_target": path if offer else None,
        "last_offer_options": _offer_options_for_result(result, offer),
        "timestamp": time.time(),
    }


def _remember_language_context(state: AgentState, language: str) -> None:
    _cleanup_local_contexts()
    key = _context_key(state)
    context = dict(_LOCAL_TOOL_CONTEXTS.get(key) or {})
    context.update({"language": language, "timestamp": time.time()})
    _LOCAL_TOOL_CONTEXTS[key] = context


def _remember_ranking_context(state: AgentState, result: dict[str, Any]) -> None:
    root = result.get("root") or result.get("path")
    if not root:
        return
    _cleanup_local_contexts()
    _LOCAL_TOOL_CONTEXTS[_context_key(state)] = {
        "language": "pt-BR",
        "last_tool": "folder_usage_top",
        "last_path": root,
        "last_result": dict(result),
        "last_offer": "open_details_of_subfolder",
        "last_offer_target": root,
        "last_offer_options": _offer_options_for_result(result, "open_details_of_subfolder"),
        "timestamp": time.time(),
    }


def _cleanup_local_contexts() -> None:
    now = time.time()
    expired = [
        key for key, context in _LOCAL_TOOL_CONTEXTS.items()
        if now - float(context.get("timestamp", 0)) > LOCAL_CONTEXT_TTL_SECONDS
    ]
    for key in expired:
        _LOCAL_TOOL_CONTEXTS.pop(key, None)
    if len(_LOCAL_TOOL_CONTEXTS) <= MAX_LOCAL_CONTEXTS:
        return
    oldest = sorted(_LOCAL_TOOL_CONTEXTS.items(), key=lambda item: float(item[1].get("timestamp", 0)))
    for key, _context in oldest[: max(0, len(_LOCAL_TOOL_CONTEXTS) - MAX_LOCAL_CONTEXTS)]:
        _LOCAL_TOOL_CONTEXTS.pop(key, None)


def _offer_options_for_result(result: dict[str, Any], offer: str | None) -> list[str]:
    if offer != "open_details_of_subfolder":
        return []
    options: list[str] = []
    for item in result.get("folders", [])[:10]:
        path = item.get("path")
        if path:
            options.append(str(path))
    return options


def _apply_local_followup_context(state: AgentState, context: dict[str, Any] | None) -> None:
    text = state.normalized_message.strip().lower()
    if _is_followup_accept(text):
        state.intent = "followup_accept_offer"
        state.category = "storage"
        if context and context.get("last_path"):
            state.system_context["folder_target"] = {"path": context["last_path"], "source": "last_local_context"}
        return

    if _is_subfolder_ranking_followup(text) and context and context.get("last_path"):
        state.intent = "followup_accept_offer"
        state.category = "storage"
        state.system_context["folder_target"] = {"path": context["last_path"], "source": "last_local_context"}
        return

    if state.intent in {"folder_size", "file_count"} and not state.system_context.get("folder_target", {}).get("path"):
        if context and context.get("last_path") and _references_previous_path(text):
            state.system_context["folder_target"] = {"path": context["last_path"], "source": "last_local_context"}


def _is_followup_accept(text: str) -> bool:
    cleaned = text.strip(" .!?")
    accepts = {
        "sim",
        "sim tudo",
        "sim, tudo",
        "pode",
        "pode ver",
        "manda",
        "mostra",
        "verifica",
        "faz isso",
        "quero",
        "claro",
        "yes",
        "yep",
        "yeah",
        "sure",
        "ok",
        "okay",
        "do it",
        "show",
        "go ahead",
    }
    return cleaned in accepts or any(cleaned.startswith(prefix + " ") and len(cleaned) <= 40 for prefix in ["sim", "pode", "manda", "mostra", "verifica", "quero", "yes", "sure", "show"])


def _references_previous_path(text: str) -> bool:
    return any(term in text for term in ["ela", "dela", "nela", "nessa pasta", "essa pasta", "a pasta", "ai", "aí", "isso"])


def _is_subfolder_ranking_followup(text: str) -> bool:
    ranking_terms = ["subpastas", "dentro dela", "dentro dessa pasta", "mais pesam", "mais ocupam", "maiores"]
    return _references_previous_path(text) and any(term in text for term in ranking_terms)


def _resolve_folder_target_for_state(state: AgentState) -> dict[str, Any]:
    target = state.system_context.get("folder_target") or resolve_folder_target(state.user_message)
    if target.get("path"):
        return target
    context = _get_local_context(state)
    if context and context.get("last_path") and (state.intent == "file_count" or _references_previous_path(state.normalized_message)):
        return {"path": context["last_path"], "source": "last_local_context"}
    return target


def _folder_result_for_state(state: AgentState, target: dict[str, Any]) -> dict[str, Any]:
    path = target.get("path")
    if not path:
        return {
            "path": None,
            "error": target.get("error") or "Nao consegui identificar uma pasta especifica.",
            "error_type": "path_not_detected",
            "cache_hit": False,
            "context_hit": False,
            "timed_out": False,
            "skipped_count": 0,
        }

    context = _get_local_context(state)
    if state.intent == "file_count" and context and context.get("last_path") and _same_path(path, context["last_path"]):
        age = time.time() - float(context.get("timestamp", 0))
        if age <= COUNT_CONTEXT_TTL_SECONDS and isinstance(context.get("last_result"), dict):
            result = dict(context["last_result"])
            result["cache_hit"] = True
            result["context_hit"] = True
            result["elapsed_ms"] = 0
            return result

    result = get_folder_size(path, max_seconds=10, max_entries=180_000)
    result["path_source"] = target.get("source")
    result["context_hit"] = False
    return result


def _same_path(left: str, right: str) -> bool:
    return str(left).rstrip("\\/").lower() == str(right).rstrip("\\/").lower()


def _run_followup_offer(state: AgentState) -> dict[str, Any]:
    context = _get_local_context(state)
    if not context or not context.get("last_path") or context.get("last_offer") not in {"show_top_subfolders", "open_details_of_subfolder"}:
        return {
            "error": "Nao tenho uma oferta anterior clara para executar. Me diga a pasta ou a acao que voce quer.",
            "root": None,
            "folders": [],
            "cache_hit": False,
            "timed_out": False,
            "skipped_count": 0,
        }
    if context.get("last_offer") == "open_details_of_subfolder":
        options = context.get("last_offer_options") or []
        path = options[0] if options else context["last_path"]
        result = get_folder_size(path, max_seconds=10, max_entries=180_000)
        result["tool"] = "folder_size"
        result["context_hit"] = True
        return result
    root = context["last_path"]
    result = get_disk_usage_ranking(root=root, limit=10, max_depth=3, max_seconds=10)
    result["tool"] = "folder_usage_top"
    result["path"] = root
    result["context_hit"] = True
    return result


def _build_prompt(state: AgentState) -> str:
    if any(call.get("name") == "web_search" for call in state.tool_calls):
        return _web_search_prompt(state)
    if any(call.get("name") == "folder_size" for call in state.tool_calls):
        return _folder_size_prompt(state)
    if any(call.get("name") == "disk_usage" for call in state.tool_calls):
        return _disk_usage_prompt(state)
    if any(call.get("name") == "analyze_pc" for call in state.tool_calls):
        return _report_prompt(state)
    if not state.tool_calls and state.intent == "identity_query":
        return (
            "O usuario perguntou sobre suas capacidades reais.\n"
            "Explique em portugues do Brasil, com tom natural e direto, que voce e o Agente Fino. "
            "Diga que consegue conversar, analisar o PC com ferramentas de leitura, verificar uso de disco, rede e impressoras, "
            "consultar a base RAG e a memoria tecnica do agente quando fizer sentido, pesquisar web com fontes quando ativado e sugerir acoes seguras com confirmacao. "
            "Nao confunda memoria tecnica do agente com memoria RAM. "
            "Nao prometa executar comandos livres nem acesso remoto."
        )
    if not state.tool_calls and (state.intent in GENERAL_CONVERSATION_INTENTS or state.intent in {"casual_chat", "greeting", "clarification_needed", "safe_refusal"}):
        return _conversation_prompt(state)

    context = {
        "mensagem": state.user_message,
        "intent": state.intent,
        "categoria": state.category,
        "ferramentas_executadas": _compact_tool_calls(state.tool_calls),
        "rag_status": state.rag_status,
        "rag_context": _compact_items(state.rag_context, limit=5, content_key="content"),
        "memory_context": _compact_items(state.memory_context, limit=6, content_key="content"),
        "web_status": state.web_status,
        "fontes": [source.model_dump() for source in state.citations[:6]],
    }
    return (
        "Responda ao usuario usando o contexto abaixo. "
        "Se uma ferramenta foi executada, use os resultados reais dela. "
        "Se web foi usada, cite as fontes retornadas. "
        "Se nao houver evidencia suficiente, admita. "
        "Seja objetivo, mas nao raso: traga leitura, criterio e proximos passos seguros.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def _conversation_prompt(state: AgentState) -> str:
    rule = INTENT_RULES.get(state.intent, {})
    style = rule.get("style", "natural, direto e util")
    activation_hint = ""
    if state.normalized_message.strip() in {"ative", "ativa", "ativar"}:
        activation_hint = "Se o usuário disser apenas 'Ative', trate como checagem de prontidão: diga que você está ativo e pronto para ajudar. "
    safety_hint = ""
    if state.intent == "safe_sexual_education":
        safety_hint = "Tema sexual: responda apenas como educação segura, consentimento, prevenção, saúde e limites; sem descrição gráfica ou erotização. "
    if state.intent == "safe_refusal":
        safety_hint = "O pedido tem risco: recuse de forma curta e ofereça alternativa segura e educativa. "
    if state.intent in {"life_advice", "relationship_advice", "family_advice", "friendship_advice", "emotional_support", "dating_advice"}:
        safety_hint += "Valide o contexto rapidamente e dê próximos passos práticos; não faça roleplay romântico nem finja ser terapeuta. "
    if state.intent == "football_opinion":
        safety_hint += "Se falar de Neymar ou convocação sem pesquisa, dê opinião geral sobre talento, físico, ritmo, decisão de jogo e papel no grupo; não exija web. "
    if state.intent == "gaming_opinion":
        safety_hint += "Compare proposta, público, custo, liberdade e complexidade. "
    return (
        f"Mensagem do usuário:\n{state.user_message}\n\n"
        f"Intent detectado: {state.intent}. Estilo esperado: {style}.\n"
        f"{activation_hint}{safety_hint}"
        "Responda em português do Brasil, de forma humana e direta. "
        "Não diga que o assunto foge da função. Não peça opinião de volta como resposta principal. "
        "Não cite RAG, web, processos, diagnóstico ou ferramentas se nenhuma ferramenta foi usada. "
        "Se for opinião, opine com nuance. Se faltar dado atual, ofereça análise geral sem travar a conversa."
    )


def _system_prompt() -> str:
    return (
        NEXUS_SYSTEM_PROMPT
        + " "
        + build_personality_prompt()
        + " Use apenas ferramentas ja executadas pelo backend; nunca diga que consultou o PC, web, RAG ou memoria se isso nao veio no contexto. "
        "Acoes que alteram o PC exigem confirmacao. Para ranking de disco, destaque tamanho, caminho e observacao segura. "
        "Em conversa comum, nao puxe diagnostico tecnico sem pedido claro."
    )


def _system_prompt_for(state: AgentState) -> str:
    if not state.tool_calls and (state.intent in GENERAL_CONVERSATION_INTENTS or state.intent in {"greeting", "casual_chat", "identity_query", "clarification_needed", "safe_refusal"}):
        return NEXUS_SYSTEM_PROMPT + " " + build_personality_prompt() + " Nao mencione fallback nem provider. Nao puxe diagnostico tecnico sem pedido claro."
    return _system_prompt()


def _max_tokens_for(state: AgentState) -> int:
    if state.mode == "EXPERT":
        return 1024
    if state.mode == "BALANCED":
        return 512
    if state.mode == "FAST":
        return 32
    if state.intent in {"greeting", "casual_chat"} and not state.tool_calls:
        return 140
    if state.intent == "identity_query":
        return 240
    if any(call.get("name") == "web_search" for call in state.tool_calls):
        return 360
    if state.tool_calls:
        return 420
    if state.intent in {"life_advice", "relationship_advice", "emotional_support", "career_advice", "money_advice", "decision_support"}:
        return 420
    return 520


def _temperature_for(state: AgentState) -> float:
    if state.tool_calls:
        return 0.1
    if state.intent in GENERAL_CONVERSATION_INTENTS:
        return 0.45
    return 0.25


def _compact_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for call in tool_calls:
        compacted.append(
            {
                "name": call.get("name"),
                "status": call.get("status"),
                "latency_ms": call.get("latency_ms"),
                "risk_level": call.get("risk_level"),
                "requires_confirmation": call.get("requires_confirmation"),
                "result": _compact_tool_result(call.get("name"), call.get("result", {})),
                "error": call.get("error"),
            }
        )
    return compacted


def _compact_tool_result(tool_name: str | None, result: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "analyze_pc":
        return {"summary": _compact_report_text(result), "top_processes": result.get("top_processes", [])[:5], "observations": result.get("observations", [])[:6]}
    if tool_name == "disk_usage":
        return {
            "root": result.get("root"),
            "folders": result.get("folders", [])[:10],
            "elapsed_ms": result.get("elapsed_ms"),
            "scanned_entries": result.get("scanned_entries"),
            "skipped": result.get("skipped"),
            "truncated": result.get("truncated"),
        }
    if tool_name == "folder_size":
        return {
            "path": result.get("path"),
            "size_gb": result.get("size_gb"),
            "file_count": result.get("file_count"),
            "folder_count": result.get("folder_count"),
            "skipped_count": result.get("skipped_count"),
            "timed_out": result.get("timed_out"),
            "cache_hit": result.get("cache_hit"),
            "error": result.get("error"),
        }
    if tool_name == "web_search":
        return {
            "web_used": result.get("web_used"),
            "searched_at": result.get("searched_at"),
            "sources": result.get("sources", [])[:5],
            "warnings": result.get("warnings", [])[:5],
        }
    if tool_name == "rag_search":
        return {"status": result.get("status"), "results": _compact_items(result.get("results", []), limit=5, content_key="content")}
    if tool_name == "memory_search":
        return {"results": _compact_items(result.get("results", []), limit=6, content_key="content")}
    if tool_name == "network_info":
        return {
            "configuration": result.get("configuration"),
            "adapters": _compact_items(result.get("adapters", []), limit=6, content_key="description"),
        }
    return result


def _compact_items(items: list[dict[str, Any]], *, limit: int, content_key: str) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in items[:limit]:
        copy = dict(item)
        if content_key in copy and isinstance(copy[content_key], str):
            copy[content_key] = copy[content_key][:700]
        compacted.append(copy)
    return compacted


def _parse_route_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _apply_route_to_state(state: AgentState, route: dict[str, Any]) -> None:
    intent = str(route.get("intent", "normal_chat"))
    category = str(route.get("category") or "")
    if intent == "normal_chat":
        state.intent = "casual_chat" if state.intent not in {"greeting", "casual_chat", "identity_query"} else state.intent
        state.category = "open_world"
    elif intent in STRUCTURED_INTENTS:
        state.intent = intent
        state.category = category or INTENT_RULES.get(intent, {}).get("category", "general")


def _disk_usage_prompt(state: AgentState) -> str:
    result = _tool_result(state, "disk_usage")
    folders = result.get("folders", [])[:5]
    lines = [f"{index}. {item.get('size_gb')} GB - {item.get('path')} ({item.get('observation')})" for index, item in enumerate(folders, start=1)]
    return (
        "O usuario perguntou quais pastas ocupam mais espaco. "
        "A ferramenta local somente leitura retornou este ranking:\n"
        + "\n".join(lines)
        + "\n\nResponda em portugues, em 5 bullets curtos, citando tamanho, caminho e cuidado de seguranca. "
        "Nao diga para apagar pastas do sistema."
    )


def _folder_size_prompt(state: AgentState) -> str:
    result = _tool_result(state, "folder_size")
    return (
        "O usuario perguntou o tamanho de uma pasta especifica. "
        "Use somente este resultado local de leitura:\n"
        f"{json.dumps(_compact_tool_result('folder_size', result), ensure_ascii=False, indent=2)}\n\n"
        "Responda direto: caminho, tamanho aproximado, arquivos/pastas analisados e aviso se for parcial. "
        "Nao fale sobre espaco livre do disco inteiro."
    )


def _report_prompt(state: AgentState) -> str:
    report = state.local_report or _tool_result(state, "analyze_pc")
    summary = report.get("summary", {})
    cpu = report.get("cpu", {})
    memory = report.get("memory", {})
    disk = report.get("disk", {})
    processes = report.get("top_processes", [])[:5]
    process_lines = [
        f"- {item.get('name')} PID {item.get('pid')}: CPU {item.get('cpu_percent')}%, RAM {item.get('memory_percent')}%"
        for item in processes
    ]
    return (
        "O usuario pediu analise deste PC. Use apenas estes dados reais coletados localmente:\n"
        f"Host: {summary.get('hostname')}; SO: {summary.get('operating_system')}; "
        f"CPU total: {cpu.get('percent')}%; RAM total em uso: {memory.get('percent')}% "
        f"({memory.get('used_gb')} GB de {memory.get('total_gb')} GB); "
        f"Disco: {disk.get('free_gb')} GB livres de {disk.get('total_gb')} GB.\n"
        "Processos principais:\n"
        + "\n".join(process_lines)
        + "\n\nResponda em portugues, ate 5 linhas, com leitura tecnica, gargalos provaveis e proximos testes seguros. "
        "Use estes limiares: abaixo de 70% e normal/moderado; acima de 80% e alto/critico. "
        "Informe que nada foi alterado no PC."
    )


def _web_search_prompt(state: AgentState) -> str:
    result = _tool_result(state, "web_search")
    sources = result.get("sources", [])[:3]
    lines = []
    for index, source in enumerate(sources, start=1):
        title = source.get("title")
        domain = source.get("domain")
        url = source.get("url")
        excerpt = (source.get("excerpt") or source.get("snippet") or "")[:160]
        lines.append(f"{index}. {title} ({domain}) - {url} - {excerpt}")
    if not lines:
        lines.append("Nenhuma fonte citavel retornada.")
    return (
        "O usuario pediu pesquisa web. Use somente estas fontes consultadas/retornadas pelo backend:\n"
        + "\n".join(lines)
        + "\n\nResponda em portugues do Brasil, em ate 6 linhas, com resumo direto e uma secao 'Fontes consultadas'. "
        "Nao invente link nem diga que leu fonte que nao aparece acima."
    )


def _mode_for(provider_name: str, use_web: bool) -> str:
    if provider_name == "local-rules":
        return "WEB_AWARE" if use_web else "OFFLINE"
    return "HYBRID" if use_web else "LOCAL_LLM"


def _should_fast_path(state: AgentState, request) -> bool:
    if not getattr(request, "mode", "auto").lower() in {"auto", "fast"}:
        return False
    text = state.normalized_message.strip().lower()
    if state.web_needed:
        return False
    if tool_for_intent(state.intent):
        return False
    if _asks_memory(text) or _asks_memory_save(text):
        return False
    if state.intent in FAST_PATH_INTENTS:
        return True
    if text in FAST_PATH_MESSAGES:
        return True
    if text.startswith("sem pesquisar") and len(text) <= 280:
        return True
    return False


def _instant_fast_reply(state: AgentState, router: ModelRouter) -> str | None:
    text = state.normalized_message.strip().lower()
    if text not in FAST_PATH_MESSAGES:
        return None
    if text in {"obrigado", "obrigada", "valeu"}:
        return "Fechado. Quando precisar, me chama."
    if text in {"teste"}:
        return "Tô respondendo. Pode mandar."
    if text in {"tudo bem", "tudo bem?", "como voce esta", "como vocÃª estÃ¡"}:
        return "Tudo certo por aqui. E contigo, como está indo?"
    if text in {"kkkk", "top", "gostei"}:
        return "Boa. Manda a próxima."
    return "Fala! Tô online. Manda a boa."


def _call_provider_chat(provider, messages: list[dict[str, str]], *, temperature: float, max_tokens: int, timeout_seconds: float):
    try:
        return provider.chat(messages, temperature=temperature, max_tokens=max_tokens, timeout_seconds=timeout_seconds)
    except TypeError:
        return provider.chat(messages, temperature=temperature, max_tokens=max_tokens)


def _provider_status_payload(provider_name: str, model: str, available: bool, error: str | None = None) -> dict[str, Any]:
    if provider_name == "gemini":
        return {"configured": True, "available": available, "online": available, "gemini_status": "online" if available else "error", "model": model, "last_error": None if available else error}
    if provider_name == "ollama":
        return {"configured": True, "available": available, "online": available, "ollama_status": "online" if available else "offline", "model": model, "last_error": None if available else error}
    if provider_name == "openai-responses":
        return {"configured": True, "available": available, "online": available, "openai_status": "online" if available else "error", "model": model, "last_error": None if available else error}
    return {"configured": True, "available": available, "online": available, "status": "online" if available else "error", "model": model, "last_error": None if available else error}


def _provider_timeout_for(mode: str, provider_name: str) -> float:
    normalized_mode = (mode or "").upper()
    if normalized_mode == "FAST":
        if provider_name == "ollama":
            return settings.ollama_fast_timeout_seconds
        return settings.fast_provider_timeout_seconds
    if normalized_mode == "EXPERT":
        return settings.expert_provider_timeout_seconds
    return settings.balanced_provider_timeout_seconds


def _logical_mode_for(state: AgentState, selected_tools: list[str], providers: list) -> str:
    online_available = any(getattr(provider, "name", "") != "local-rules" for provider in providers)
    return FusionEngine().choose_mode(
        intent=state.intent,
        tools=selected_tools,
        web_needed=state.web_needed,
        online_available=online_available,
    ).mode


def _rag_category(state: AgentState) -> str | None:
    return state.category if state.category not in {"open_world", "web_research", "storage"} else None


def _should_use_rag(state: AgentState) -> bool:
    if state.intent in GENERAL_CONVERSATION_INTENTS or state.intent in {"greeting", "casual_chat", "identity_query", "calculation_query", "time_query", "date_query", "system_metric_query", "pc_diagnostic", "disk_usage", "folder_usage_top", "folder_size"}:
        return False
    if state.intent in TECHNICAL_INTENTS and state.intent not in {"web_research", "deep_web_research"}:
        return True
    if state.category in {"printer", "network", "hardware", "performance", "security", "windows", "technology", "software"}:
        return True
    return False


def _asks_memory(text: str) -> bool:
    return any(word in text for word in ["lembra", "memoria", "memória", "o que voce sabe de mim", "o que voce lembra de mim"])


def _asks_memory_save(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in ["lembre que", "guarde que", "salve que", "memorize que"])


def _memory_note(message: str) -> str:
    lowered = message.strip()
    for prefix in ["lembre que", "guarde que", "salve que", "memorize que"]:
        if lowered.lower().startswith(prefix):
            return lowered[len(prefix):].strip(" :.-")
    return lowered


def _tool_result(state: AgentState, name: str) -> dict[str, Any]:
    for call in state.tool_calls:
        if call["name"] == name:
            return call.get("result", {})
    return {}


def _compact_report_text(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    cpu = report.get("cpu", {})
    memory = report.get("memory", {})
    disk = report.get("disk", {})
    return (
        f"Host {summary.get('hostname')}; SO {summary.get('operating_system')}; "
        f"CPU {cpu.get('percent')}%; RAM {memory.get('percent')}%; Disco {disk.get('percent')}%."
    )


def _report_text(report: dict[str, Any]) -> str:
    if not report:
        return "Nao consegui gerar o relatorio local agora."
    summary = report.get("summary", {})
    cpu = report.get("cpu", {})
    memory = report.get("memory", {})
    disk = report.get("disk", {})
    processes = report.get("top_processes", [])[:5]
    lines = [
        "Analise real deste PC:",
        f"- Host: {summary.get('hostname', 'indisponivel')}",
        f"- Sistema: {summary.get('operating_system', 'indisponivel')}",
        f"- CPU: {cpu.get('percent', 'indisponivel')}%",
        f"- RAM: {memory.get('percent', 'indisponivel')}% em uso",
        f"- Disco {disk.get('path', 'C:')}: {disk.get('free_gb', 'indisponivel')} GB livres de {disk.get('total_gb', 'indisponivel')} GB",
        "",
        "Processos em destaque:",
    ]
    lines.extend(f"- {item.get('name')} (PID {item.get('pid')}): CPU {item.get('cpu_percent')}%, RAM {item.get('memory_percent')}%" for item in processes)
    lines.extend(["", "Nada foi alterado no PC; esta analise e somente leitura."])
    return "\n".join(lines)


def _disk_usage_text(result: dict[str, Any]) -> str:
    if not result:
        return "Nao consegui coletar uso de disco agora."
    folders = result.get("folders", [])
    lines = [
        f"Ranking das pastas que mais ocupam espaco em {result.get('root', 'raiz selecionada')}:",
        "",
    ]
    if not folders:
        lines.append("- Nenhuma pasta retornada dentro do limite de seguranca.")
    for index, item in enumerate(folders, start=1):
        lines.append(f"{index}. {item.get('size_gb')} GB - {item.get('path')}")
        lines.append(f"   Observacao: {item.get('observation')}")
    lines.extend(
        [
            "",
            f"Varredura: {result.get('elapsed_ms', 0)} ms; entradas analisadas: {result.get('scanned_entries', 0)}; ignoradas: {result.get('skipped', 0)}.",
            "Seguranca: ferramenta somente leitura; nada foi apagado.",
        ]
    )
    if result.get("truncated"):
        lines.append("Aviso: resultado truncado por limite de tempo/entradas para proteger o PC.")
    return "\n".join(lines)


def _folder_size_answer(result: dict[str, Any]) -> str:
    path = result.get("path") or "caminho nao identificado"
    if result.get("error"):
        return "\n".join(
            [
                "Nao consegui calcular o tamanho dessa pasta.",
                f"Caminho: {path}",
                f"Motivo: {result.get('error')}",
                "",
                "Nada foi alterado no PC.",
            ]
        )

    lines = [
        f"{path} usa aproximadamente {_size_text(result.get('size_bytes'), result.get('size_gb'))}.",
        "",
        "Resumo:",
        f"- Arquivos analisados: {int(result.get('file_count') or 0):,}".replace(",", "."),
        f"- Pastas analisadas: {int(result.get('folder_count') or 0):,}".replace(",", "."),
        f"- Itens ignorados por permissao: {int(result.get('skipped_count') or 0):,}".replace(",", "."),
    ]
    if result.get("cache_hit"):
        lines.append("- Cache: resultado reutilizado dos ultimos 60 segundos.")
    if result.get("timed_out"):
        lines.append("- Aviso: calculo parcial por limite de tempo.")
    elif result.get("partial"):
        lines.append("- Aviso: nao consegui acessar tudo dentro dessa pasta; resultado pode estar incompleto.")
    lines.extend(["", "Quer que eu veja quais subpastas dentro dela mais ocupam espaco?"])
    return "\n".join(lines)


def _file_count_answer(result: dict[str, Any]) -> str:
    path = result.get("path") or "caminho nao identificado"
    if result.get("error"):
        return "\n".join(
            [
                "Nao consegui contar os arquivos dessa pasta.",
                f"Caminho: {path}",
                f"Motivo: {result.get('error')}",
                "",
                "Nada foi alterado no PC.",
            ]
        )

    lines = [
        f"{path} tem {int(result.get('file_count') or 0):,} arquivos analisados.".replace(",", "."),
        "",
        "Resumo:",
        f"- Pastas analisadas: {int(result.get('folder_count') or 0):,}".replace(",", "."),
        f"- Itens ignorados por permissao: {int(result.get('skipped_count') or 0):,}".replace(",", "."),
    ]
    if result.get("timed_out"):
        lines.append("- Aviso: contagem parcial por limite de tempo.")
    elif result.get("partial"):
        lines.append("- Resultado pode estar incompleto por permissoes.")
    if result.get("cache_hit") or result.get("context_hit"):
        lines.append("- Cache/contexto: usei a contagem local recente.")
    lines.extend(["", f"Bonus: a pasta usa aproximadamente {_size_text(result.get('size_bytes'), result.get('size_gb'))}."])
    return "\n".join(lines)


def _folder_usage_top_answer(result: dict[str, Any]) -> str:
    if result.get("error"):
        return "\n".join(
            [
                "Preciso de um pouco mais de contexto para fazer isso.",
                str(result.get("error")),
            ]
        )

    root = result.get("root") or result.get("path") or "pasta selecionada"
    folders = result.get("folders", [])
    lines = [f"Estas sao as subpastas que mais ocupam espaco em {root}:", ""]
    if not folders:
        lines.append("- Nenhuma subpasta retornada dentro do limite de seguranca.")
    for index, item in enumerate(folders[:10], start=1):
        lines.append(f"{index}. {item.get('name') or item.get('path')} - {_number_br(item.get('size_gb') or 0, 2)} GB")
    if result.get("truncated"):
        lines.extend(["", "Aviso: resultado parcial por limite de tempo/entradas."])
    lines.extend(["", "Quer que eu abra detalhes de alguma delas?"])
    return "\n".join(lines)


def _language_correction_answer(state: AgentState) -> str:
    text = state.normalized_message
    if "sarcasmo" in text or "ironia" in text:
        return "Fechado, vou manter portugues. Entendi que foi sarcasmo/continuacao, nao pedido para mudar de idioma."
    return "Fechado, vou manter portugues do Brasil daqui pra frente nesta conversa."


def _local_metric_answer(intent: str, result: dict[str, Any]) -> str:
    if intent in {"disk_space", "storage_status", "simple_pc_metric"}:
        return _disk_space_answer(result)
    if intent == "ram_status":
        return _ram_status_answer(result)
    if intent == "cpu_status":
        return _cpu_status_answer(result)
    if intent == "local_ip_status":
        return _local_ip_answer(result)
    if intent == "uptime_status":
        return _uptime_answer(result)
    if intent == "spooler_status":
        return _spooler_answer(result)
    return _system_metric_answer(result)


def _disk_space_answer(status: dict[str, Any]) -> str:
    disk = status.get("disk", {})
    memory = status.get("memory", {})
    cpu = status.get("cpu", {})
    label = _drive_label(disk.get("path"))
    free = _gb_text(disk.get("free_gb"))
    total = _gb_text(disk.get("total_gb"))
    percent = _percent_text(disk.get("percent"))
    return "\n".join(
        [
            f"{label}",
            f"{free} livres de {total}.",
            f"Uso aproximado: {percent}.",
            "",
            "Leitura rapida:",
            _disk_interpretation(disk.get("percent")),
            "",
            "Bonus tecnico:",
            f"CPU: {_percent_text(cpu.get('percent'))}",
            f"RAM: {_percent_text(memory.get('percent'))}",
            "",
            "Quer que eu veja tambem quais pastas estao ocupando mais espaco?",
        ]
    )


def _ram_status_answer(status: dict[str, Any]) -> str:
    memory = status.get("memory", {})
    return "\n".join(
        [
            "RAM:",
            f"{_gb_text(memory.get('used_gb'))} em uso de {_gb_text(memory.get('total_gb'))}.",
            f"Uso aproximado: {_percent_text(memory.get('percent'))}.",
            "",
            "Leitura rapida:",
            _usage_interpretation(memory.get("percent"), "A RAM esta com folga agora.", "A RAM esta em uso alto; pode pesar se abrir mais programas."),
        ]
    )


def _cpu_status_answer(status: dict[str, Any]) -> str:
    cpu = status.get("cpu", {})
    return "\n".join(
        [
            "CPU:",
            f"Uso atual aproximado: {_percent_text(cpu.get('percent'))}.",
            "",
            "Leitura rapida:",
            _usage_interpretation(cpu.get("percent"), "O processador esta tranquilo neste momento.", "A CPU esta em uso alto agora; vale olhar processos se isso continuar."),
        ]
    )


def _local_ip_answer(status: dict[str, Any]) -> str:
    ip = status.get("local_ip") or "indisponivel"
    return "\n".join(
        [
            "IP local:",
            str(ip),
            "",
            "Leitura rapida:",
            "Esse e o endereco da maquina dentro da rede local. Para IP publico, eu preciso consultar a internet.",
        ]
    )


def _uptime_answer(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Uptime:",
            f"PC ligado ha {status.get('uptime', 'indisponivel')}.",
            f"Inicializacao: {status.get('boot_time', 'indisponivel')}.",
        ]
    )


def _spooler_answer(result: dict[str, Any]) -> str:
    spooler = result.get("spooler", result)
    status = spooler.get("status", "indisponivel")
    message = spooler.get("message") or ""
    return "\n".join(
        [
            "Spooler de impressao:",
            f"Status: {status}.",
            "",
            "Leitura rapida:",
            message or "Consulta feita em modo somente leitura; nada foi alterado no PC.",
        ]
    )


def _system_metric_answer(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Status rapido do PC:",
            f"CPU: {_percent_text(status.get('cpu', {}).get('percent'))}",
            f"RAM: {_percent_text(status.get('memory', {}).get('percent'))}",
            f"Disco: {_gb_text(status.get('disk', {}).get('free_gb'))} livres de {_gb_text(status.get('disk', {}).get('total_gb'))}",
        ]
    )


def _drive_label(path: Any) -> str:
    text = str(path or "C:").strip()
    if len(text) >= 2 and text[1] == ":":
        return f"Disco {text[0].upper()}:"
    return f"Disco {text}:"


def _gb_text(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{_number_br(value, 2)} GB"
    return str(value or "indisponivel")


def _size_text(size_bytes: Any, size_gb: Any = None) -> str:
    if isinstance(size_bytes, (int, float)):
        if float(size_bytes) < GB:
            return f"{_number_br(float(size_bytes) / (1024**2), 2)} MB"
        return f"{_number_br(float(size_bytes) / GB, 2)} GB"
    if isinstance(size_gb, (int, float)):
        return f"{_number_br(size_gb, 2)} GB"
    return "indisponivel"


def _percent_text(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{_number_br(value, 1)}%"
    return str(value or "indisponivel")


def _number_br(value: int | float, decimals: int) -> str:
    formatted = f"{float(value):.{decimals}f}"
    return formatted.replace(".", ",")


def _disk_interpretation(percent: Any) -> str:
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return "Nao consegui interpretar o percentual, mas a leitura do espaco foi feita."
    if value >= 90:
        return "Seu disco esta praticamente cheio. Eu recomendo ver as maiores pastas antes de apagar qualquer coisa."
    if value >= 80:
        return "Seu disco esta ficando apertado. Ainda da para agir com calma, olhando primeiro as maiores pastas."
    if value >= 70:
        return "Seu disco merece atencao, mas ainda nao parece em emergencia."
    return "Seu disco nao esta cheio. Ainda existe uma margem boa."


def _usage_interpretation(percent: Any, ok_message: str, high_message: str) -> str:
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return "Nao consegui interpretar o percentual, mas a leitura local foi feita."
    if value >= 80:
        return high_message
    return ok_message


def _memory_text(result: dict[str, Any]) -> str:
    items = result.get("results", [])
    if not items:
        return "Ainda nao encontrei memorias relevantes sobre voce no Agente Fino. Posso lembrar preferencias se voce disser, por exemplo: 'lembre que eu prefiro respostas diretas'."
    lines = ["O que encontrei na memoria local:"]
    for item in items[:8]:
        title = item.get("title") or item.get("key") or item.get("user_message") or "Registro"
        content = item.get("content") or item.get("value") or item.get("agent_response") or ""
        lines.append(f"- {title}: {content[:240]}")
    return "\n".join(lines)


def _web_text(result: dict[str, Any]) -> str:
    sources = result.get("sources", [])
    if not sources:
        return "A pergunta pediu web, mas nenhuma fonte citavel foi obtida. Resposta limitada."
    lines = ["Pesquisei na web e encontrei estas fontes:"]
    for source in sources[:5]:
        lines.append(f"- {source.get('title')} ({source.get('domain')}): {source.get('url')}")
    return "\n".join(lines)


def _fallback_open_chat(state: AgentState) -> str:
    text = state.normalized_message
    if state.intent == "time_query":
        now = datetime.now().astimezone()
        return f"Agora sao {now:%H:%M} no horario local deste PC ({now:%d/%m/%Y}, UTC{now:%z})."
    if state.intent == "date_query":
        now = datetime.now().astimezone()
        return f"Hoje e {now:%d/%m/%Y}."
    if state.intent == "greeting":
        return "Oi! Estou por aqui. Pode mandar conversa comum, dúvida, ideia ou diagnóstico que eu acompanho o ritmo."
    if state.intent == "casual_chat":
        if "robotico" in text or "engessado" in text:
            return "Justo. Vou falar de um jeito mais natural, direto e menos preso ao modo técnico; quando for TI eu aprofundo, quando for conversa comum eu respondo normal."
        return "Tudo certo por aqui. E contigo, como está indo?"
    if state.intent == "identity_query":
        return (
            "Eu sou o Agente Fino: converso sobre assuntos gerais e também faço diagnóstico técnico com ferramentas locais, RAG, memória e web com fontes quando você pedir. "
            "Quando precisar mexer no PC, fico no modo seguro e peço confirmação para ações sensíveis."
        )
    if state.intent == "football_opinion":
        return (
            "Sobre Neymar, minha visão geral é: talento e leitura de jogo ele ainda tem de sobra, mas convocação depende muito de físico, ritmo competitivo e encaixe no grupo. "
            "Se estiver inteiro, pode ser peça de decisão; se não estiver em ritmo, faz mais sentido como opção estratégica do que como centro absoluto do time."
        )
    if state.intent in {"life_advice", "emotional_support"}:
        return (
            "Entendo. Quando a vida parece embaralhada, o melhor primeiro passo é reduzir o tamanho do problema: escolha uma área urgente, escreva o que está te drenando e defina uma ação pequena para hoje. "
            "Depois você ajusta plano, rotina e prioridades sem tentar resolver a vida inteira numa tacada."
        )
    if state.intent == "relationship_advice":
        return (
            "Sinto muito que esteja passando por isso. Agora vale cuidar do básico: não tomar decisão no pico da dor, evitar ficar reabrindo ferida em conversa impulsiva e organizar o que você precisa dizer ou encerrar com respeito. "
            "Se quiser, eu te ajudo a montar uma mensagem madura."
        )
    if state.intent == "dating_advice":
        return (
            "Vai pelo simples e respeitoso: puxe um assunto real, observe se a pessoa responde com abertura e faça um convite leve, sem pressão. "
            "A ideia é demonstrar interesse com clareza, não tentar manipular reação."
        )
    if state.intent == "safe_sexual_education":
        return (
            "Pode perguntar. Eu trato esse tema pelo lado educativo e seguro: consentimento, limites, prevenção, saúde e conversa madura entre adultos. "
            "Não entro em descrição explícita, mas consigo te orientar com responsabilidade."
        )
    if state.intent == "safe_refusal":
        return (
            "Não vou ajudar com algo perigoso, ilegal, invasivo ou sexualmente explícito. Posso, porém, transformar isso em uma alternativa segura: análise de risco, prevenção, consentimento, segurança digital defensiva ou explicação educativa."
        )
    if state.intent == "money_advice":
        return (
            "Meu conselho prático: separe dinheiro pessoal do dinheiro do trabalho, monte uma reserva pequena antes de assumir parcela longa e cobre serviço pelo valor entregue, não só pelo tempo gasto. "
            "Sem seus números eu não prometo resultado, mas dá para montar um plano realista."
        )
    if state.intent == "career_advice":
        return (
            "Para carreira, eu iria no tripé: serviço bem definido, prova do que você entrega e comunicação firme com cliente. "
            "Se for cobrança, mostre escopo, risco, tempo e benefício; isso deixa o preço menos emocional e mais profissional."
        )
    if state.intent == "music_opinion":
        return "Trap tem força quando junta identidade, produção boa e frase marcante. Nem tudo me convence, mas o gênero capturou muito bem ritmo, estética e linguagem de uma geração."
    if state.intent == "gaming_opinion":
        return "Entre GTA e Roblox, depende do objetivo: GTA é experiência fechada, cinematográfica e adulta; Roblox é plataforma aberta, social e criativa. Para liberdade e criação, Roblox; para narrativa e impacto, GTA."
    if state.intent == "movie_opinion":
        return "Dá para avaliar por ritmo, atuação, direção, impacto emocional e se o filme cumpre a proposta. Se você me disser qual é o filme, eu te dou um veredito mais afiado."
    if state.intent in {"product_advice", "price_or_product_advice"}:
        return "Dá para analisar por uso, preço, garantia, consumo, desempenho e vida útil. Se você mandar modelo e valor, eu separo o que é bom negócio do que é cilada."
    if state.intent == "tech_support":
        return "Beleza, vamos investigar sem chute. Me diga: é lentidão ao ligar, ao abrir programas, na internet ou em jogos? Se quiser, eu também posso rodar a análise local do PC."
    if state.intent == "clarification_needed":
        return "Consigo te ajudar, mas preciso de um ponto de partida: o que aconteceu, onde apareceu o problema e o que você já tentou?"
    return "Entendi. Me passa um pouco mais de contexto e eu respondo de forma direta, sem puxar diagnóstico técnico sem motivo."


def _local_quality_rewrite(state: AgentState, answer: str) -> str:
    if state.intent in GENERAL_CONVERSATION_INTENTS or state.intent in {"greeting", "casual_chat", "safe_refusal"}:
        return _fallback_open_chat(state)
    return answer.replace("Nao encontrei fontes", "Nao consegui obter fonte citavel agora").replace("não encontrei fontes", "não consegui obter fonte citável agora")
