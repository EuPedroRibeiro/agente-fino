from __future__ import annotations

import time
from datetime import datetime
from uuid import uuid4

from app.agent import rag
from app.agent.catalog import get_ai_catalog
from app.agent import conversation_logs
from app.agent.executor import confirm_action
from app.agent.graph import AgentGraph
from app.agent.memory import AgentMemory
from app.agent.memory_store import SmartMemoryStore
from app.agent.memory_stores.sqlite_memory import init_agent_storage, list_sources
from app.agent.nodes import perform_web_research
from app.agent.observability import langfuse_status, record_run
from app.agent.orchestrator import AgentOrchestrator
from app.agent.personality import get_personality, reset_personality, update_personality
from app.agent.providers.model_router import ModelRouter
from app.agent.router import classify_message
from app.agent.schemas.evidence import EvidenceItem, SourceCitation
from app.agent.schemas.agent_response import AgentResponse
from app.agent.schemas.messages import AgentChatRequest, DeepResearchRequest, ResearchRequest
from app.agent.security.sanitizer import mask_secrets
from app.agent.state import AgentState
from app.agent.tools_registry import list_tools
from app.core.config import settings
from app.core.production import production_config_errors
from app.core.runtime import is_cloud
from app.db import get_database_status
from app.services.document_lookup import DocumentLookupService
from app.services.public_data import PublicDataService
from app.intelligence import FinoIntelligenceEngine
from app.intelligence.response_builder import apply_decision, decision_metadata
from modules.mcp_brasil import MCPBrasilService


CLOUD_BLOCKED_LOCAL_INTENTS = {
    "pc_diagnostic",
    "analyze_pc",
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
    "folder_usage_top",
    "disk_usage",
    "printer_status",
    "network_info",
}


class NexusCore:
    def __init__(self) -> None:
        if not production_config_errors():
            if not is_cloud() or settings.db_engine in {"sqlite", "memory"}:
                init_agent_storage()
            conversation_logs.init_conversation_logs()
            if settings.memory_enabled:
                SmartMemoryStore().init()
            if settings.rag_enabled:
                rag.init_knowledge_base()
        self.graph = AgentGraph()
        self.orchestrator = AgentOrchestrator()
        self.memory = AgentMemory()
        self.model_router = ModelRouter()
        self.mcp_brasil = MCPBrasilService()
        self.document_lookup = DocumentLookupService()
        self.public_data = PublicDataService()
        self.intelligence = FinoIntelligenceEngine()

    def chat(self, request: AgentChatRequest) -> AgentResponse:
        started = time.perf_counter()
        state = AgentState(
            conversation_id=request.conversation_id or str(uuid4()),
            user_id=request.user_id,
            user_message=request.message,
        )
        success = True
        error = None
        decision = None
        try:
            config_errors = production_config_errors()
            if config_errors:
                state.intent = "configuration_error"
                state.category = "system"
                state.mode = "CONFIG"
                state.final_answer = (
                    "O Agente Fino esta em modo producao cloud, mas a configuracao obrigatoria ainda esta incompleta. "
                    "Configure Postgres, session secret e senha admin antes de usar o chat em producao."
                )
                state.confidence = 1.0
                state.model_used = {
                    "provider": "cloud-policy",
                    "model": "production-config-guard",
                    "used_model": False,
                    "mode": "CONFIG",
                    "llm_used": False,
                    "fallback": False,
                    "fallback_reason": "; ".join(config_errors),
                }
                return self._to_response(state)
            decision = self.intelligence.decide(request.message)
            apply_decision(state, decision)
            if decision.answer_directly:
                return self._chat_with_intelligence_direct(request, decision, started)
            if decision.execution_intent == "public_data_query":
                response = self._chat_with_public_data(request, started)
                response.intelligence = decision_metadata(decision)
                return response
            if decision.execution_intent in {"cpf_lookup", "cpf_validate", "cpf_lab_lookup", "cnpj_lookup"}:
                document_result = self.document_lookup.handle(request.message, user_id=request.user_id)
                if document_result:
                    response = self._chat_with_document_lookup(request, document_result, started)
                    response.intelligence = decision_metadata(decision)
                    return response
            if decision.execution_intent == "mcp_brasil":
                response = self._chat_with_mcp_brasil(request, started)
                response.intelligence = decision_metadata(decision)
                return response
            route = decision.route or classify_message(request.message)
            if is_cloud() and route.get("intent") in CLOUD_BLOCKED_LOCAL_INTENTS:
                state.intent = route.get("intent") or "cloud_local_tool_blocked"
                state.category = route.get("category") or "cloud"
                state.mode = "CLOUD"
                state.final_answer = _cloud_local_tool_answer(request.message)
                state.confidence = 0.94
                state.rag_status = {"used": False, "skipped": "cloud_runtime"}
                state.web_status = {"used": False, "skipped": "local_tool_blocked_in_cloud"}
                state.model_used = {
                    "provider": "cloud-policy",
                    "model": "local-tool-guard",
                    "used_model": False,
                    "mode": "CLOUD",
                    "llm_used": False,
                    "used_web": False,
                    "used_rag": False,
                    "used_verifier": False,
                    "fallback": False,
                    "fallback_reason": "Ferramenta local bloqueada no runtime cloud.",
                }
                apply_decision(state, decision)
                conversation_logs.add_message(conversation_id=state.conversation_id, role="user", content=state.user_message)
                conversation_logs.add_message(
                    conversation_id=state.conversation_id,
                    role="assistant",
                    content=state.final_answer,
                    provider=state.model_used["provider"],
                    model=state.model_used["model"],
                    intent=state.intent,
                    tools_used=[],
                    web_sources_count=0,
                    latency_ms=0,
                )
                return self._to_response(state)
            state = self.orchestrator.run(request, decision=decision)
            apply_decision(state, decision)
            model = state.model_used or {}
            conversation_logs.add_message(
                conversation_id=state.conversation_id,
                role="user",
                content=state.user_message,
            )
            conversation_logs.add_message(
                conversation_id=state.conversation_id,
                role="assistant",
                content=state.final_answer,
                provider=model.get("provider"),
                model=model.get("model"),
                intent=state.intent,
                tools_used=state.selected_tools,
                web_sources_count=len(state.citations),
                latency_ms=state.timings_ms.get("total"),
            )
            self.memory.remember_interaction(
                user_id=state.user_id,
                conversation_id=state.conversation_id,
                user_message=state.user_message,
                agent_response=state.final_answer,
                category=state.category,
                confidence=state.confidence,
                risk_level=state.risk_level,
                web_used=state.web_used,
            )
        except Exception as exc:
            success = False
            error = str(exc)
            state.errors.append(error)
            if decision is None:
                decision = self.intelligence.decide(request.message)
            apply_decision(state, decision)
            state.intent = decision.intent
            state.category = decision.category
            state.mode = "SAFE_ERROR"
            state.final_answer = decision.fallback_answer
            state.confidence = max(0.2, min(decision.confidence, 0.6))
        latency_ms = int((time.perf_counter() - started) * 1000)
        record_run(state, latency_ms=latency_ms, success=success, error=error)
        return self._to_response(state)

    def _chat_with_intelligence_direct(self, request: AgentChatRequest, decision, started: float) -> AgentResponse:
        latency_ms = int((time.perf_counter() - started) * 1000)
        state = AgentState(
            conversation_id=request.conversation_id or str(uuid4()),
            user_id=request.user_id,
            user_message=request.message,
            intent=decision.intent,
            category=decision.category,
            mode=decision.mode,
            final_answer=decision.direct_answer or decision.fallback_answer,
            plan=decision.plan,
            selected_tools=[],
            web_used=False,
            web_status={"used": False, "skipped": "fino_intelligence_direct"},
            rag_status={"used": False, "skipped": "fino_intelligence_direct"},
            model_used={
                "provider": "fino-local",
                "model": "intelligence-direct",
                "used_model": False,
                "llm_used": False,
                "used_web": False,
                "used_rag": False,
                "used_verifier": False,
                "router": decision.router,
                "reason": decision.reason,
            },
            risk_level=decision.risk_level,
            confidence=decision.confidence,
            timings_ms={"total": latency_ms, "router": latency_ms},
        )
        apply_decision(state, decision)
        conversation_logs.add_message(conversation_id=state.conversation_id, role="user", content=state.user_message)
        conversation_logs.add_message(
            conversation_id=state.conversation_id,
            role="assistant",
            content=state.final_answer,
            provider=state.model_used["provider"],
            model=state.model_used["model"],
            intent=state.intent,
            tools_used=[],
            web_sources_count=0,
            latency_ms=latency_ms,
        )
        record_run(state, latency_ms=latency_ms, success=True, error=None)
        return self._to_response(state)

    def _chat_with_document_lookup(self, request: AgentChatRequest, result: dict, started: float) -> AgentResponse:
        latency_ms = int((time.perf_counter() - started) * 1000)
        tool = result.get("tool") or "document_lookup"
        state = AgentState(
            conversation_id=request.conversation_id or str(uuid4()),
            user_id=request.user_id,
            user_message=request.message,
            intent=result.get("intent") or "document_lookup",
            category=result.get("category") or "authorized_document_lookup",
            mode="AUTHORIZED_LOOKUP",
            final_answer=result.get("answer") or "Nao consegui concluir a consulta documental.",
            selected_tools=[tool],
            tool_calls=[
                {
                    "name": tool,
                    "status": result.get("status") or "error",
                    "arguments": {"documents": result.get("documents") or []},
                    "latency_ms": result.get("latency_ms") or latency_ms,
                    "result": {"status": result.get("status"), "documents": result.get("documents") or []},
                }
            ],
            web_used=False,
            web_status={"used": False, "skipped": "authorized_document_provider"},
            rag_status={"used": False, "skipped": "authorized_document_provider"},
            model_used={
                "provider": "local" if tool in {"cpf_validate_local", "cpf_lab_simulation"} else "document-lookup",
                "model": tool,
                "used_model": False,
                "llm_used": False,
                "mode": "AUTHORIZED_LOOKUP",
                "documents": result.get("documents") or [],
            },
            risk_level="low",
            confidence=0.98 if result.get("status") == "ok" else 0.7,
            warnings=[] if result.get("status") == "ok" else ["A consulta documental nao foi concluida integralmente."],
            timings_ms={"total": latency_ms, "document_lookup": int(result.get("latency_ms") or latency_ms)},
        )
        conversation_logs.add_message(conversation_id=state.conversation_id, role="user", content=state.user_message)
        conversation_logs.add_message(
            conversation_id=state.conversation_id,
            role="assistant",
            content=result.get("history_summary") or state.final_answer,
            provider=state.model_used["provider"],
            model=state.model_used["model"],
            intent=state.intent,
            tools_used=state.selected_tools,
            web_sources_count=0,
            latency_ms=latency_ms,
        )
        record_run(state, latency_ms=latency_ms, success=result.get("status") == "ok", error=None)
        return self._to_response(state)

    def _chat_with_mcp_brasil(self, request: AgentChatRequest, started: float) -> AgentResponse:
        result = self.mcp_brasil.ask(request.message, user=request.user_id or settings.admin_user)
        latency_ms = int((time.perf_counter() - started) * 1000)
        tool_name = result.get("tool") or "mcp_brasil"
        tool_call = result.get("tool_call") or {}
        state = AgentState(
            conversation_id=request.conversation_id or str(uuid4()),
            user_id=request.user_id,
            user_message=request.message,
            intent=result.get("intent") or "mcp_brasil",
            category="public_data_br",
            mode="MCP_BRASIL",
            final_answer=result.get("answer") or "Nao consegui concluir a consulta no MCP Brasil.",
            selected_tools=[tool_name] if tool_name else [],
            tool_calls=[
                {
                    "name": tool_name,
                    "status": tool_call.get("status") or result.get("status"),
                    "arguments": result.get("arguments") or {},
                    "latency_ms": tool_call.get("latency_ms") or result.get("latency_ms"),
                    "result": {"summary": str(tool_call.get("result") or "")[:600]},
                }
            ],
            evidence=[
                EvidenceItem(
                    source_type="mcp_brasil",
                    title="MCP Brasil",
                    content=str(tool_call.get("result") or result.get("answer") or "")[:1200],
                    score=0.92,
                    metadata={"tool": tool_name, "status": result.get("status")},
                )
            ],
            citations=[
                SourceCitation(
                    title="MCP Brasil",
                    url="https://github.com/Mcp-Brasil/mcp-brasil",
                    domain="github.com",
                    reliability="high",
                    used_for="dados publicos brasileiros",
                    excerpt="MCP Brasil acionado pelo wrapper cloud-safe do Agente Fino.",
                )
            ],
            web_used=bool(result.get("web_used", True)),
            web_status={"used": True, "provider": "mcp_brasil", "sources_read": 1},
            rag_status={"used": False, "skipped": "mcp_brasil"},
            model_used={
                "provider": "mcp-brasil",
                "model": "public-data-wrapper",
                "used_model": False,
                "llm_used": False,
                "mode": "MCP_BRASIL",
                "tool": tool_name,
            },
            risk_level="low",
            confidence=0.9 if result.get("status") == "ok" else 0.55,
            warnings=[] if result.get("status") == "ok" else ["Consulta MCP Brasil retornou limitacao ou erro."],
            timings_ms={"total": latency_ms, "mcp_brasil": int(result.get("latency_ms") or latency_ms)},
        )
        conversation_logs.add_message(conversation_id=state.conversation_id, role="user", content=state.user_message)
        conversation_logs.add_message(
            conversation_id=state.conversation_id,
            role="assistant",
            content=state.final_answer,
            provider="mcp-brasil",
            model="public-data-wrapper",
            intent=state.intent,
            tools_used=state.selected_tools,
            web_sources_count=1,
            latency_ms=latency_ms,
        )
        self.memory.remember_interaction(
            user_id=state.user_id,
            conversation_id=state.conversation_id,
            user_message=state.user_message,
            agent_response=state.final_answer,
            category=state.category,
            confidence=state.confidence,
            risk_level=state.risk_level,
            web_used=state.web_used,
        )
        record_run(state, latency_ms=latency_ms, success=True, error=None)
        return self._to_response(state)

    def _chat_with_public_data(self, request: AgentChatRequest, started: float) -> AgentResponse:
        result = self.public_data.ask(request.message, user=request.user_id or settings.admin_user)
        latency_ms = int((time.perf_counter() - started) * 1000)
        tool_name = result.get("tool") or "public_data"
        source_url = result.get("source_url") or "https://github.com/GusFurtado/DadosAbertosBrasil"
        state = AgentState(
            conversation_id=request.conversation_id or str(uuid4()),
            user_id=request.user_id,
            user_message=request.message,
            intent="public_data_query",
            category="public_data",
            mode="PUBLIC_DATA",
            final_answer=result.get("answer") or "Nao consegui concluir a consulta de dados publicos.",
            selected_tools=[tool_name] if tool_name else [],
            tool_calls=[
                {
                    "name": tool_name,
                    "status": result.get("status"),
                    "arguments": result.get("arguments") or {},
                    "latency_ms": result.get("latency_ms") or latency_ms,
                    "result": {"topic": result.get("topic"), "status": result.get("status")},
                }
            ],
            evidence=[
                EvidenceItem(
                    source_type="public_data",
                    title="DadosAbertosBrasil/PublicDataProvider",
                    content=str(result.get("answer") or "")[:1200],
                    score=0.94,
                    metadata={"tool": tool_name, "topic": result.get("topic"), "status": result.get("status")},
                )
            ],
            citations=[
                SourceCitation(
                    title="Fonte publica oficial",
                    url=source_url,
                    domain=source_url.split("/")[2] if "://" in source_url else "dados-publicos",
                    reliability="high",
                    used_for="dados publicos brasileiros",
                    excerpt="Consulta executada por adaptador publico sem chave de API.",
                )
            ] if result.get("web_used") else [],
            web_used=bool(result.get("web_used")),
            web_status={
                "used": bool(result.get("web_used")),
                "provider": "public-data",
                "sources_read": 1 if result.get("web_used") else 0,
            },
            rag_status={"used": False, "skipped": "public_data_provider"},
            model_used={
                "provider": "public-data",
                "model": "DadosAbertosBrasil/PublicDataProvider",
                "used_model": False,
                "llm_used": False,
                "mode": "PUBLIC_DATA",
                "tool": tool_name,
            },
            risk_level="low",
            confidence=0.94 if result.get("status") == "ok" else 0.65,
            warnings=[] if result.get("status") == "ok" else ["A fonte publica nao concluiu integralmente a consulta."],
            timings_ms={"total": latency_ms, "public_data": int(result.get("latency_ms") or latency_ms)},
        )
        conversation_logs.add_message(conversation_id=state.conversation_id, role="user", content=state.user_message)
        conversation_logs.add_message(
            conversation_id=state.conversation_id,
            role="assistant",
            content=state.final_answer,
            provider="public-data",
            model="DadosAbertosBrasil/PublicDataProvider",
            intent=state.intent,
            tools_used=state.selected_tools,
            web_sources_count=len(state.citations),
            latency_ms=latency_ms,
        )
        record_run(state, latency_ms=latency_ms, success=result.get("status") == "ok", error=result.get("error"))
        return self._to_response(state)

    def research(self, request: ResearchRequest) -> dict:
        research = perform_web_research(request.query, official_first=request.official_first, max_results=request.max_results)
        return {
            "query": request.query,
            "web_used": research["web_used"],
            "searched_at": research["searched_at"],
            "results": research["results"],
            "sources": [source.model_dump() for source in research["sources"]],
            "warnings": research["warnings"],
        }

    def deep_research(self, request: DeepResearchRequest) -> dict:
        derived = self._derive_queries(request.query, request.depth)
        max_results = 12 if request.depth == "deep" else 5
        all_sources = []
        all_results = []
        warnings = []
        seen_urls = set()
        for query in derived:
            research = perform_web_research(query, official_first=request.official_first, max_results=max_results)
            warnings.extend(research["warnings"])
            for result in research["results"]:
                url = result.get("url") or result.get("final_url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(result)
            for source in research["sources"]:
                if source.url not in seen_urls:
                    seen_urls.add(source.url)
                all_sources.append(source.model_dump())
        summary = self._summarize_sources(request.query, all_sources)
        return {
            "query": request.query,
            "depth": request.depth,
            "derived_queries": derived,
            "web_used": bool(all_results or all_sources),
            "searched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "summary": summary,
            "results": all_results[:max_results],
            "sources": all_sources[: max_results],
            "warnings": list(dict.fromkeys(warnings)),
        }

    def analyze_pc(self, user_id: str = "local-user") -> AgentResponse:
        request = AgentChatRequest(
            message="Analise este PC",
            use_web=False,
            include_system_context=True,
            mode="OFFLINE",
            user_id=user_id,
        )
        return self.chat(request)

    def status(self) -> dict:
        catalog = get_ai_catalog()
        db_status = get_database_status()
        return {
            "product": settings.app_name,
            "version": settings.app_version,
            "agent": "Agente Fino",
            "runtime": "cloud" if is_cloud() else "local_legacy",
            "web_enabled": settings.web_enabled,
            "rag_enabled": settings.rag_enabled,
            "rag_status": rag.status() if settings.rag_enabled else {"enabled": False, "honest_status": "disabled_in_cloud_preview", "message": "RAG local desativado no cloud preview."},
            "memory_enabled": settings.memory_enabled,
            "database": {
                "engine": db_status.engine,
                "configured": db_status.configured,
                "persistent": db_status.persistent,
                "message": db_status.message,
            },
            "catalog_summary": catalog["summary"],
            "provider": self.model_router.status(),
            "mcp_brasil": self.mcp_brasil.status(),
            "public_data": self.public_data.status(),
            "document_lookup": self.document_lookup.status(),
            "tools": list_tools(),
            "observability": langfuse_status(),
        }

    def catalog(self) -> dict:
        return get_ai_catalog()

    def providers_status(self) -> dict:
        status = self.model_router.status()
        status["document_lookup"] = self.document_lookup.status()
        status["public_data"] = self.public_data.status()
        return status

    def retest_gemini(self) -> dict:
        return self.model_router.retest_gemini()

    def retest_openai(self) -> dict:
        return self.model_router.retest_openai()

    def create_conversation(self, title: str | None = None) -> dict:
        return conversation_logs.create_conversation(title)

    def list_conversations(self, query: str | None = None) -> list[dict]:
        return conversation_logs.list_conversations(query=query)

    def get_conversation(self, conversation_id: str) -> dict | None:
        return conversation_logs.get_conversation(conversation_id)

    def update_conversation(self, conversation_id: str, title: str) -> dict:
        return conversation_logs.update_conversation(conversation_id, title)

    def delete_conversation(self, conversation_id: str) -> bool:
        return conversation_logs.delete_conversation(conversation_id)

    def conversation_messages(self, conversation_id: str) -> list[dict]:
        return conversation_logs.list_messages(conversation_id)

    def list_memory(self, user_id: str = "local-user") -> list[dict]:
        return self.memory.list(user_id)

    def create_memory(self, payload: dict) -> dict:
        return SmartMemoryStore().create(
            category=payload.get("category"),
            key=payload.get("key"),
            value=payload["value"],
            source=payload.get("source", "user"),
            confidence=float(payload.get("confidence", 0.9)),
            pinned=bool(payload.get("pinned", False)),
        )

    def search_memory(self, user_id: str, query: str, limit: int = 10) -> list[dict]:
        return self.memory.search(user_id, query, limit)

    def search_smart_memory(self, query: str, limit: int = 10) -> list[dict]:
        return SmartMemoryStore().search(query, limit=limit)

    def update_memory(self, memory_id: int, payload: dict) -> dict:
        return SmartMemoryStore().update(memory_id, payload)

    def pin_memory(self, memory_id: int, pinned: bool = True) -> dict:
        return SmartMemoryStore().pin(memory_id, pinned)

    def archive_memory(self, memory_id: int, archived: bool = True) -> dict:
        return SmartMemoryStore().archive(memory_id, archived)

    def delete_memory(self, memory_id: int) -> bool:
        return self.memory.delete(memory_id)

    def personality(self) -> dict:
        return get_personality()

    def update_personality(self, payload: dict) -> dict:
        return update_personality(payload)

    def reset_personality(self) -> dict:
        return reset_personality()

    def sources(self) -> list[dict]:
        return list_sources()

    def confirm_action(self, pending_action_id: str, confirm: bool) -> dict:
        return confirm_action(pending_action_id, confirm)

    def _to_response(self, state: AgentState) -> AgentResponse:
        return AgentResponse(
            conversation_id=state.conversation_id,
            answer=state.final_answer,
            final_answer=state.final_answer,
            intent=state.intent,
            category=state.category,
            mode=state.mode,
            web_used=state.web_used,
            searched_at=state.searched_at,
            sources=state.citations,
            evidence=state.evidence,
            plan=state.plan,
            safe_actions=state.system_context.get("specialist_safe_actions", []),
            selected_tools=state.selected_tools,
            tool_calls=state.tool_calls,
            model_used=state.model_used,
            rag_status=state.rag_status,
            web_status=state.web_status,
            risk_level=state.risk_level,
            confidence=state.confidence,
            needs_confirmation=state.needs_confirmation,
            pending_actions=state.pending_actions,
            warnings=state.warnings,
            errors=mask_secrets(state.errors),
            timings_ms=state.timings_ms,
            intelligence=state.system_context.get("intelligence", {}),
        )

    def _derive_queries(self, query: str, depth: str) -> list[str]:
        base = [query, f"{query} documentacao oficial", f"{query} troubleshooting"]
        if depth == "deep":
            base.extend([f"{query} GitHub issue", f"{query} comparativo fontes oficiais"])
        return list(dict.fromkeys(base))[:5]

    def _summarize_sources(self, query: str, sources: list[dict]) -> str:
        if not sources:
            return "Nao encontrei fontes citaveis suficientes. Use modo local/RAG e refine a consulta."
        official = [source for source in sources if source.get("reliability") == "high"]
        return (
            f"Pesquisa tecnica sobre '{query}' encontrou {len(sources)} fontes, "
            f"com {len(official)} fonte(s) de alta confiabilidade. Prefira as fontes oficiais listadas."
        )


def _cloud_local_tool_answer(message: str) -> str:
    return (
        "Essa funcao existia no modo local, mas a versao web/cloud nao tem acesso ao seu computador. "
        "Posso te orientar a verificar isso manualmente ou analisar um relatorio, texto, print ou arquivo que voce enviar."
    )
