from __future__ import annotations

from dataclasses import dataclass, field


SIMPLE_INTENTS = {
    "greeting",
    "casual_chat",
    "general_question",
    "general_opinion",
    "football_opinion",
    "sports_opinion",
    "music_opinion",
    "movie_opinion",
    "gaming_opinion",
    "calculation_query",
    "time_query",
    "date_query",
}

EXPERT_INTENTS = {
    "pc_diagnostic",
    "analyze_pc",
    "folder_size",
    "folder_usage_top",
    "file_count",
    "followup_accept_offer",
    "disk_usage",
    "printer_support",
    "printer_status",
    "network_support",
    "network_info",
    "tech_support",
    "software_support",
    "cybersecurity_learning",
    "report_analysis",
}

WEB_INTENTS = {"web_research", "deep_web_research", "price_or_product_advice"}
SENSITIVE_INTENTS = {"safe_refusal", "health_general", "safe_sexual_education"}


@dataclass
class FusionDecision:
    mode: str
    reason: str
    max_models: int = 1
    use_verifier: bool = False
    use_web: bool = False
    tools: list[str] = field(default_factory=list)


class FusionEngine:
    """Decide o modo logico do Nexus sem acoplar isso ao provider real.

    Provider offline pode trocar o motor para Ollama/local-rules, mas nao deve
    transformar uma saudacao em OFFLINE nem um diagnostico em OFFLINE.
    """

    def choose_mode(
        self,
        *,
        intent: str,
        tools: list[str] | None = None,
        web_needed: bool = False,
        online_available: bool = True,
        allow_verifier: bool = True,
    ) -> FusionDecision:
        tools = list(dict.fromkeys(tools or []))
        if intent in SIMPLE_INTENTS and not tools and not web_needed:
            reason = "Conversa simples; uma resposta rapida basta."
            if not online_available:
                reason += " Provider real indisponivel, usando fallback sem mudar o modo logico."
            return FusionDecision(mode="FAST", reason=reason, max_models=1, tools=tools)

        if intent in WEB_INTENTS or web_needed:
            reason = "Pedido depende de informacao atual ou pesquisa."
            return FusionDecision(
                mode="BALANCED",
                reason=reason,
                max_models=1,
                use_verifier=allow_verifier and online_available,
                use_web=True,
                tools=tools,
            )

        if intent in EXPERT_INTENTS or tools:
            reason = "Pedido tecnico ou com ferramenta; requer estrategia EXPERT."
            if not online_available:
                reason += " Provider real indisponivel, mantendo EXPERT com fallback local."
            return FusionDecision(
                mode="EXPERT",
                reason=reason,
                max_models=2 if online_available else 1,
                use_verifier=allow_verifier,
                use_web=web_needed,
                tools=tools,
            )

        if intent in SENSITIVE_INTENTS:
            return FusionDecision(
                mode="SELF_CHECK",
                reason="Tema sensivel; responder com verificacao de seguranca.",
                max_models=2 if online_available else 1,
                use_verifier=allow_verifier,
                tools=tools,
            )

        return FusionDecision(
            mode="BALANCED",
            reason="Pergunta geral; usar contexto quando fizer sentido.",
            max_models=1,
            use_verifier=allow_verifier and online_available,
            use_web=web_needed,
            tools=tools,
        )
