from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.agent.public_data_router import PublicDataRouter
from app.agent.router import classify_message, normalize_for_intent, web_needed
from app.security.documents import classify_document_request
from modules.mcp_brasil import MCPBrasilRouter


class IntentRoute(BaseModel):
    intent: str
    execution_intent: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    router: str = "fino-rule-router"
    route: dict[str, Any] = Field(default_factory=dict)


CANONICAL_INTENTS = {
    "deep_web_research": "deep_research",
    "pc_diagnostic": "pc_analysis",
    "disk_space": "local_metric",
    "storage_status": "local_metric",
    "ram_status": "local_metric",
    "cpu_status": "local_metric",
    "local_ip_status": "local_metric",
    "uptime_status": "local_metric",
    "spooler_status": "local_metric",
    "simple_pc_metric": "local_metric",
    "folder_size": "local_metric",
    "file_count": "local_metric",
    "folder_usage_top": "local_metric",
    "tech_support": "technical_question",
    "software_support": "technical_question",
    "printer_support": "technical_question",
    "network_support": "technical_question",
    "cybersecurity_learning": "technical_question",
    "routine_planning": "planning",
    "decision_support": "planning",
}


class FinoIntentRouter:
    """Deterministic first-pass router; it never calls a model or provider."""

    def route(self, message: str) -> IntentRoute:
        normalized = normalize_for_intent(message)
        if not normalized:
            return self._result("unknown", "clarification_needed", "general", 0.4, "Mensagem vazia.")

        # Public parliamentary expenses keep precedence over generic document lookup.
        if PublicDataRouter.is_parliamentary_expense_query(message):
            plan = PublicDataRouter.plan_query(message)
            return self._result(
                "public_data_query",
                "public_data_query",
                "public_data",
                0.98,
                "Despesa parlamentar publica solicitada.",
                {"tool": plan.tool_name, "arguments": plan.arguments, "topic": plan.topic},
            )

        # Sensitive document tools only enter the pipeline after the strict document parser.
        document_route = classify_document_request(message)
        if document_route:
            return self._from_route(document_route, 0.99, "Documento e finalidade explicitos.")

        if normalized.startswith("/sherlock") or "abrir sherlock" in normalized:
            return self._result(
                "sherlock_query",
                "sherlock_query",
                "sherlock",
                0.98,
                "Comando Sherlock explicito.",
                {"tool": "sherlock"},
            )

        if normalized.startswith("/mcp") or "mcp brasil" in normalized:
            plan = MCPBrasilRouter.plan_query(message)
            return self._result(
                "public_data_query",
                "mcp_brasil",
                "public_data_br",
                0.96,
                "MCP Brasil solicitado explicitamente.",
                {"tool": plan.tool_name, "arguments": plan.arguments},
            )

        if PublicDataRouter.should_use_public_data(message):
            plan = PublicDataRouter.plan_query(message)
            return self._result(
                "public_data_query",
                "public_data_query",
                "public_data",
                0.94,
                "Consulta compativel com fonte publica.",
                {"tool": plan.tool_name, "arguments": plan.arguments, "topic": plan.topic},
            )

        if MCPBrasilRouter.should_use_mcp_brasil(message):
            plan = MCPBrasilRouter.plan_query(message)
            return self._result(
                "public_data_query",
                "mcp_brasil",
                "public_data_br",
                0.9,
                "Consulta compativel com fonte publica brasileira.",
                {"tool": plan.tool_name, "arguments": plan.arguments},
            )

        if any(term in normalized for term in ("nao era isso", "voce entendeu errado", "corrige isso", "resposta errada")):
            return self._result(
                "error_recovery",
                "casual_chat",
                "behavior",
                0.94,
                "Correcao de comportamento solicitada.",
                {"intent": "casual_chat", "category": "behavior", "web_needed": False},
            )

        if any(term in normalized for term in ("crie uma estrategia", "criar uma estrategia", "monte uma estrategia")):
            return self._result(
                "strategy",
                "routine_planning",
                "planning",
                0.9,
                "Pedido explicito de estrategia.",
                {"intent": "routine_planning", "category": "planning", "web_needed": False},
            )

        route = classify_message(message)
        if route["intent"] == "casual_chat" and re.search(r"\b\d{8,16}\b", normalized):
            route = {"intent": "general_question", "category": "general"}
        confidence = self._confidence_for(route["intent"], normalized)
        reason = self._reason_for(route["intent"])
        route = dict(route)
        route["web_needed"] = web_needed(message, route["intent"])
        canonical = CANONICAL_INTENTS.get(route["intent"], route["intent"])
        return self._result(canonical, route["intent"], route["category"], confidence, reason, route)

    def _from_route(self, route: dict[str, Any], confidence: float, reason: str) -> IntentRoute:
        return self._result(
            route["intent"],
            route["intent"],
            route.get("category") or "general",
            confidence,
            reason,
            route,
        )

    @staticmethod
    def _result(
        intent: str,
        execution_intent: str,
        category: str,
        confidence: float,
        reason: str,
        route: dict[str, Any] | None = None,
    ) -> IntentRoute:
        return IntentRoute(
            intent=intent,
            execution_intent=execution_intent,
            category=category,
            confidence=confidence,
            reason=reason,
            route=route or {},
        )

    @staticmethod
    def _confidence_for(intent: str, normalized: str) -> float:
        if intent in {"greeting", "time_query", "date_query", "identity_query", "language_correction"}:
            return 0.99
        if intent in {"web_research", "deep_web_research", "memory_search", "memory_save"}:
            return 0.96
        if intent in {
            "disk_space",
            "storage_status",
            "ram_status",
            "cpu_status",
            "local_ip_status",
            "uptime_status",
            "spooler_status",
            "folder_size",
            "file_count",
            "folder_usage_top",
            "pc_diagnostic",
        }:
            return 0.95
        if intent in {"general_question", "casual_chat", "general_opinion"}:
            return 0.78 if len(normalized) > 3 else 0.68
        return 0.82

    @staticmethod
    def _reason_for(intent: str) -> str:
        if intent == "greeting":
            return "Saudacao simples reconhecida; resposta local imediata."
        if intent in {"web_research", "deep_web_research"}:
            return "Pesquisa web solicitada explicitamente."
        if intent in {"cpf_lookup", "cpf_validate", "cnpj_lookup"}:
            return "Documento e finalidade explicitos."
        if intent in CANONICAL_INTENTS:
            return "Metrica ou ferramenta local reconhecida."
        return f"Regra deterministica classificou a mensagem como {intent}."
