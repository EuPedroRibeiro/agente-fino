from __future__ import annotations

import json
import time
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.agent.core import NexusCore
from app.agent.fusion.engine import FusionEngine
from app.agent.intelligence.autonomy import autonomy_status
from app.agent.intelligence.learning_store import LearningStore
from app.agent.intelligence.task_manager import create_task, list_tasks
from app.agent.memory_graph import add_node, search_nodes
from app.agent.router import classify_message
from app.agent.security.sanitizer import mask_secrets
from app.agent.schemas.messages import (
    AgentChatRequest,
    ConfirmActionRequest,
    ConversationCreateRequest,
    ConversationUpdateRequest,
    DeepResearchRequest,
    DiskUsageRequest,
    MemoryArchiveRequest,
    MemoryPinRequest,
    MemorySearchRequest,
    PersonalityPatchRequest,
    ResearchRequest,
    SmartMemoryCreateRequest,
    SmartMemoryUpdateRequest,
)
from app.agent.schemas.agent_response import AgentResponse
from app.core.config import settings
from app.core.runtime import is_cloud
from app.db import get_database_status
from app.core.auth import can_login_with_payload, clear_local_session, create_local_session, csrf_payload, get_auth_status
from app.security.audit import audit_event, read_audit_events
from app.security.config import security_settings
from app.security.input_validation import validate_chat_message, validate_path_text, validate_title
from app.services.disk_usage import get_disk_usage_ranking
from modules.mcp_brasil import MCPBrasilRouter


router = APIRouter(tags=["agent"])
templates = Jinja2Templates(directory="app/templates")
core = NexusCore()
RUNS: dict[str, dict] = {}
RUN_TTL_SECONDS = 300
MAX_RUNS = 200


UTF8_HTML = "text/html; charset=utf-8"


def _cleanup_runs() -> None:
    now = time.time()
    expired = [run_id for run_id, run in RUNS.items() if now - float(run.get("created_at", now)) > RUN_TTL_SECONDS]
    for run_id in expired:
        RUNS.pop(run_id, None)
    if len(RUNS) <= MAX_RUNS:
        return
    oldest = sorted(RUNS.items(), key=lambda item: float(item[1].get("created_at", now)))
    for run_id, _run in oldest[: max(0, len(RUNS) - MAX_RUNS)]:
        RUNS.pop(run_id, None)


def _sse(event: str, data: dict) -> str:
    safe_data = json.loads(mask_secrets(json.dumps(data, ensure_ascii=False, default=str)))
    return f"event: {event}\ndata: {json.dumps(safe_data, ensure_ascii=False)}\n\n"


def _activity_message_for_route(route: dict) -> str:
    intent = route.get("intent")
    path = route.get("path")
    if intent == "file_count":
        return f"Contando arquivos em {path}..." if path else "Contando arquivos..."
    if intent == "folder_size":
        return f"Verificando {path}..." if path else "Verificando pasta..."
    if intent == "folder_usage_top":
        return "Analisando pastas..."
    if intent in {"web_research", "deep_web_research"}:
        return "Pesquisando na web..."
    if intent == "mcp_brasil":
        return "Consultando dados publicos brasileiros..."
    return "Analisando pedido..."


def _elapsed_label(elapsed_ms: int) -> str:
    seconds = max(0, int(round(elapsed_ms / 1000)))
    if seconds < 1:
        return "menos de 1s"
    if seconds < 60:
        return f"{seconds}s"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes}min {rest}s"


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {"app_name": settings.app_name, "app_version": settings.app_version},
        media_type=UTF8_HTML,
    )


@router.post("/api/auth/login")
def auth_login(request: Request, response: Response, payload: dict | None = Body(default=None)) -> dict:
    if not can_login_with_payload(payload):
        audit_event("login_failed", request=request, details={"reason": "admin_password_required"})
        raise HTTPException(status_code=401, detail="Login cloud exige senha admin configurada.")
    session_payload = create_local_session(response)
    audit_event("login_success", request=request, details={"mode": session_payload.get("mode")})
    return session_payload


@router.post("/api/auth/logout")
def auth_logout(request: Request, response: Response) -> dict:
    payload = clear_local_session(request, response)
    audit_event("logout", request=request)
    return payload


@router.get("/api/auth/status")
def auth_status() -> dict:
    return get_auth_status()


@router.get("/api/auth/csrf")
def auth_csrf(request: Request) -> dict:
    return csrf_payload(request)


@router.get("/api/security/status")
def security_status() -> dict:
    db_status = get_database_status()
    return {
        "enabled": security_settings.enabled,
        "release": security_settings.release_name,
        "runtime": "cloud" if is_cloud() else "local_legacy",
        "environment": security_settings.environment,
        "public_mode": security_settings.public_mode,
        "require_login": security_settings.require_login,
        "csrf_enabled": security_settings.csrf_enabled,
        "csp_allow_blob_script": security_settings.csp_allow_blob_script,
        "rate_limit_enabled": security_settings.rate_limit_enabled,
        "security_headers_enabled": security_settings.security_headers_enabled,
        "audit_log_enabled": security_settings.audit_log_enabled,
        "uploads_enabled": security_settings.uploads_enabled,
        "max_upload_mb": security_settings.max_upload_mb,
        "auth": get_auth_status(),
        "database": {
            "engine": db_status.engine,
            "configured": db_status.configured,
            "persistent": db_status.persistent,
            "message": db_status.message,
        },
    }


@router.get("/api/security/audit")
def security_audit(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"events": read_audit_events(limit)}


@router.get("/agent", response_class=HTMLResponse)
def agent_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "agent.html",
        {"app_name": settings.app_name, "app_version": settings.app_version},
        media_type=UTF8_HTML,
    )


@router.get("/api/agent/status")
def agent_status() -> dict:
    return core.status()


@router.get("/api/agent/providers/status")
def agent_providers_status() -> dict:
    return core.providers_status()


@router.post("/api/agent/providers/gemini/retest")
def agent_gemini_retest() -> dict:
    return core.retest_gemini()


@router.post("/api/agent/providers/openai/retest")
def agent_openai_retest() -> dict:
    return core.retest_openai()


@router.get("/api/agent/catalog")
def agent_catalog() -> dict:
    return core.catalog()


@router.post("/api/agent/chat")
def agent_chat(payload: AgentChatRequest) -> dict:
    validate_chat_message(payload.message)
    if _is_darkforest_command(payload.message):
        return _darkforest_redirect_response(payload).model_dump()
    return core.chat(payload).model_dump()


@router.post("/api/agent/runs")
def agent_run_create(payload: AgentChatRequest) -> dict:
    validate_chat_message(payload.message)
    _cleanup_runs()
    run_id = str(uuid4())
    RUNS[run_id] = {"payload": payload, "created_at": time.time(), "status": "queued"}
    return {"run_id": run_id, "status": "queued"}


def _is_darkforest_command(message: str) -> bool:
    normalized = (
        (message or "")
        .lower()
        .replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("õ", "o")
        .replace("ô", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    return any(
        term in normalized
        for term in (
            "scanner de vazamento",
            "verificar possiveis chaves",
            "chaves expostas",
            "abrir scanner",
            "darkforest",
        )
    )


def _darkforest_redirect_response(payload: AgentChatRequest) -> AgentResponse:
    conversation_id = payload.conversation_id or f"conv-{uuid4().hex[:10]}"
    answer = (
        "Vou abrir o modulo Scanner de Vazamento de Chaves. "
        "Por seguranca, ele fica separado do chat e so executa depois do aviso sensivel e da confirmacao de autorizacao. "
        "Acesse: /security"
    )
    return AgentResponse(
        conversation_id=conversation_id,
        answer=answer,
        final_answer=answer,
        intent="darkforest_scanner",
        category="security",
        mode="SAFE_REDIRECT",
        web_used=False,
        selected_tools=[],
        model_used={"provider": "local", "model": "darkforest-router", "used_model": False, "redirect_url": "/security"},
        risk_level="medium",
        confidence=0.94,
        warnings=["Modulo sensivel exige confirmacao explicita antes de qualquer analise."],
        timings_ms={"total": 1},
    )


@router.get("/api/agent/runs/{run_id}/events")
def agent_run_events(run_id: str) -> StreamingResponse:
    _cleanup_runs()
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")

    def stream():
        started = time.perf_counter()
        payload: AgentChatRequest = run["payload"]
        try:
            if MCPBrasilRouter.should_use_mcp_brasil(payload.message):
                plan = MCPBrasilRouter.plan_query(payload.message)
                route = {"intent": "mcp_brasil", "category": "public_data_br", "tool": plan.tool_name}
            else:
                route = classify_message(payload.message)
            yield _sse("run_started", {"run_id": run_id, "message": "Pensando..."})
            yield _sse(
                "route_detected",
                {
                    "run_id": run_id,
                    "intent": route.get("intent"),
                    "category": route.get("category"),
                    "path": route.get("path"),
                    "message": _activity_message_for_route(route),
                },
            )
            if route.get("intent") in {"folder_size", "file_count", "folder_usage_top"}:
                yield _sse("local_tool_started", {"run_id": run_id, "message": _activity_message_for_route(route)})
            if route.get("intent") in {"web_research", "deep_web_research"}:
                yield _sse("web_search_started", {"run_id": run_id, "message": "Pesquisando na web..."})
            if route.get("intent") == "mcp_brasil":
                yield _sse(
                    "web_search_started",
                    {"run_id": run_id, "message": "Consultando dados publicos brasileiros via MCP Brasil...", "tool": route.get("tool")},
                )

            response = core.chat(payload)
            data = response.model_dump()
            if data.get("web_used"):
                sources = data.get("sources") or []
                first_source = sources[0] if sources else {}
                if first_source:
                    yield _sse(
                        "web_source_found",
                        {
                            "run_id": run_id,
                            "message": f"Consultando {first_source.get('domain') or first_source.get('title') or 'fonte'}...",
                            "source": first_source,
                        },
                    )
                yield _sse("web_search_done", {"run_id": run_id, "sources_count": len(sources), "message": "Fontes analisadas."})
            yield _sse("finalizing", {"run_id": run_id, "message": "Finalizando..."})
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            data["activity"] = {
                "elapsed_ms": elapsed_ms,
                "elapsed_label": _elapsed_label(elapsed_ms),
            }
            run.update({"status": "done", "final": data, "elapsed_ms": elapsed_ms})
            yield _sse("run_done", {"run_id": run_id, "elapsed_ms": elapsed_ms, "elapsed_label": _elapsed_label(elapsed_ms), "response": data})
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            error = mask_secrets(str(exc))
            run.update({"status": "error", "error": error, "elapsed_ms": elapsed_ms})
            yield _sse("run_error", {"run_id": run_id, "elapsed_ms": elapsed_ms, "error": error, "message": "Nao consegui concluir a execucao."})

    return StreamingResponse(stream(), media_type="text/event-stream; charset=utf-8")


@router.get("/api/agent/runs/{run_id}")
def agent_run_get(run_id: str) -> dict:
    _cleanup_runs()
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")
    return {key: value for key, value in run.items() if key != "payload"}


@router.post("/api/agent/tools/disk-usage")
def agent_disk_usage(payload: DiskUsageRequest) -> dict:
    if is_cloud():
        return {
            "status": "disabled_in_cloud",
            "message": "Varredura de disco local fica desativada no Agente Fino Cloud.",
            "folders": [],
        }
    if payload.root:
        validate_path_text(payload.root)
    return get_disk_usage_ranking(
        payload.root,
        limit=payload.limit,
        max_depth=payload.max_depth,
        max_seconds=payload.max_seconds,
    )


@router.post("/api/agent/research")
def agent_research(payload: ResearchRequest) -> dict:
    validate_chat_message(payload.query)
    return core.research(payload)


@router.post("/api/agent/deep-research")
def agent_deep_research(payload: DeepResearchRequest) -> dict:
    validate_chat_message(payload.query)
    return core.deep_research(payload)


@router.post("/api/agent/analyze-pc")
def agent_analyze_pc() -> dict:
    if is_cloud():
        return core.chat(AgentChatRequest(message="Analise este PC")).model_dump()
    return core.analyze_pc().model_dump()


@router.post("/api/agent/confirm-action")
def agent_confirm_action(payload: ConfirmActionRequest) -> dict:
    return core.confirm_action(payload.pending_action_id, payload.confirm)


@router.get("/api/agent/memory")
def agent_memory() -> dict:
    return {"memory": core.list_memory()}


@router.post("/api/agent/memory")
def agent_memory_create(payload: SmartMemoryCreateRequest) -> dict:
    return core.create_memory(payload.model_dump())


@router.post("/api/agent/memory/search")
def agent_memory_search(payload: MemorySearchRequest) -> dict:
    return {"results": core.search_smart_memory(payload.query, payload.limit)}


@router.patch("/api/agent/memory/{memory_id}")
def agent_memory_update(memory_id: int, payload: SmartMemoryUpdateRequest) -> dict:
    try:
        return core.update_memory(memory_id, payload.model_dump(exclude_unset=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="Memoria nao encontrada.")


@router.post("/api/agent/memory/{memory_id}/pin")
def agent_memory_pin(memory_id: int, payload: MemoryPinRequest) -> dict:
    try:
        return core.pin_memory(memory_id, payload.pinned)
    except KeyError:
        raise HTTPException(status_code=404, detail="Memoria nao encontrada.")


@router.post("/api/agent/memory/{memory_id}/archive")
def agent_memory_archive(memory_id: int, payload: MemoryArchiveRequest) -> dict:
    try:
        return core.archive_memory(memory_id, payload.archived)
    except KeyError:
        raise HTTPException(status_code=404, detail="Memoria nao encontrada.")


@router.delete("/api/agent/memory/{memory_id}")
def agent_memory_delete(memory_id: int) -> dict:
    deleted = core.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memoria nao encontrada.")
    return {"deleted": True}


@router.get("/api/agent/personality")
def agent_personality() -> dict:
    return core.personality()


@router.patch("/api/agent/personality")
def agent_personality_update(payload: PersonalityPatchRequest) -> dict:
    return core.update_personality(payload.model_dump(exclude_unset=True))


@router.post("/api/agent/personality/reset")
def agent_personality_reset() -> dict:
    return core.reset_personality()


@router.get("/api/agent/conversations")
def agent_conversations(query: str | None = Query(default=None)) -> dict:
    return {"conversations": core.list_conversations(query)}


@router.post("/api/agent/conversations")
def agent_conversation_create(payload: ConversationCreateRequest) -> dict:
    title = validate_title(payload.title) if payload.title else None
    return core.create_conversation(title)


@router.get("/api/agent/conversations/{conversation_id}")
def agent_conversation_get(conversation_id: str) -> dict:
    conversation = core.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada.")
    return conversation


@router.patch("/api/agent/conversations/{conversation_id}")
def agent_conversation_update(conversation_id: str, payload: ConversationUpdateRequest) -> dict:
    try:
        return core.update_conversation(conversation_id, validate_title(payload.title))
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada.")


@router.delete("/api/agent/conversations/{conversation_id}")
def agent_conversation_delete(conversation_id: str) -> dict:
    deleted = core.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada.")
    return {"deleted": True}


@router.get("/api/agent/conversations/{conversation_id}/messages")
def agent_conversation_messages(conversation_id: str) -> dict:
    return {"messages": core.conversation_messages(conversation_id)}


@router.get("/api/agent/sources")
def agent_sources() -> dict:
    return {"sources": core.sources()}


@router.get("/api/agent/fusion/status")
def agent_fusion_status() -> dict:
    provider = core.providers_status()
    return {
        "enabled": settings.fusion_enabled,
        "mode_default": settings.fusion_default_mode,
        "active_mode": settings.fusion_default_mode,
        "active_provider": provider.get("selected_provider"),
        "fallback_provider": "local-rules" if is_cloud() else ("ollama" if provider.get("selected_provider") != "ollama" else "local-rules"),
        "gemini_status": provider.get("gemini_status"),
        "openai_status": provider.get("openai_status", "not_configured"),
        "ollama_status": provider.get("ollama_status"),
        "rag_status": "disabled_in_cloud" if is_cloud() and not settings.rag_enabled else ("on" if settings.rag_enabled else "off"),
        "memory_status": "on" if settings.memory_enabled else "off",
        "web_status": "on" if settings.web_enabled else "off",
        "verifier_enabled": settings.fusion_allow_verifier,
        "engine": FusionEngine().__class__.__name__,
    }


@router.get("/api/agent/autonomy/status")
def agent_autonomy_status() -> dict:
    return autonomy_status()


@router.patch("/api/agent/autonomy/settings")
def agent_autonomy_update(payload: dict) -> dict:
    current = autonomy_status()
    level = int(payload.get("level", current["level"]))
    return {"enabled": bool(payload.get("enabled", current["enabled"])), "level": max(0, min(level, 5)), "dangerous_actions_auto_execute": False}


@router.get("/api/agent/tasks")
def agent_tasks() -> dict:
    return {"tasks": list_tasks()}


@router.post("/api/agent/tasks")
def agent_task_create(payload: dict) -> dict:
    title = validate_title(payload.get("title", "Tarefa Agente Fino"))
    description = validate_chat_message(payload.get("description", ""))
    return create_task(title, description)


@router.get("/api/agent/memory/graph")
def agent_memory_graph() -> dict:
    return {"nodes": search_nodes("", 50), "edges": []}


@router.post("/api/agent/memory/graph/search")
def agent_memory_graph_search(payload: dict) -> dict:
    query = validate_chat_message(payload.get("query", ""))
    return {"nodes": search_nodes(query, int(payload.get("limit", 20)))}


@router.post("/api/agent/memory/extract")
def agent_memory_extract(payload: dict) -> dict:
    raw_text = validate_chat_message(payload.get("text", ""))
    value = mask_secrets(raw_text)
    sensitive = value != payload.get("text", "")
    return {"candidate": {"value": value, "requires_confirmation": sensitive}, "sensitive": sensitive}


@router.post("/api/agent/memory/confirm-save")
def agent_memory_confirm_save(payload: dict) -> dict:
    if not payload.get("confirm", False):
        return {"saved": False}
    value = validate_chat_message(payload.get("value", "")) or "memoria"
    node = add_node(mask_secrets(value), validate_title(payload.get("type", "entity")))
    return {"saved": True, "node": node}


@router.post("/api/agent/feedback")
def agent_feedback(payload: dict) -> dict:
    if payload.get("comment"):
        payload["comment"] = validate_chat_message(str(payload["comment"]))
    return LearningStore().save_feedback(payload)


@router.get("/api/agent/feedback")
def agent_feedback_list() -> dict:
    return {"feedback": []}


@router.post("/api/agent/learning/rule")
def agent_learning_rule(payload: dict) -> dict:
    return LearningStore().save_rule(validate_chat_message(payload.get("rule", "")))


@router.get("/api/agent/learning/rules")
def agent_learning_rules() -> dict:
    return {"rules": []}


@router.get("/api/agent/replay/{message_id}")
def agent_replay(message_id: str) -> dict:
    return {
        "message_id": message_id,
        "summary": "Replay seguro da ultima resposta.",
        "chain_of_thought_hidden": True,
        "items": ["intent detectado", "provider/modelo", "ferramentas", "verificador"],
    }


@router.post("/api/agent/lens/analyze")
def agent_lens_analyze(payload: dict) -> dict:
    if not settings.enable_lens:
        return {"enabled": False, "message": "Lens desativado."}
    if not payload.get("confirmed", False):
        return {"enabled": True, "requires_confirmation": True, "message": "Confirme antes de enviar imagem; prints podem conter dados sensiveis."}
    return {"enabled": True, "analysis": "Imagem recebida para analise quando provider multimodal estiver disponivel."}


@router.post("/api/agent/training/export")
def agent_training_export(payload: dict | None = None) -> dict:
    return {"exported": False, "path": "data/training/nexus_sft.jsonl", "sanitized": True, "requires_review": True}


@router.get("/api/agent/training/status")
def agent_training_status() -> dict:
    return {"enabled": settings.enable_training_export, "path": "data/training/nexus_sft.jsonl"}
