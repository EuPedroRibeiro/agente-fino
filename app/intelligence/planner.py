from __future__ import annotations

from app.agent.schemas.plans import Plan, PlanStep


def build_safe_plan(intent: str, tools: list[str], *, web_needed: bool, requires_confirmation: bool) -> Plan | None:
    if intent in {"greeting", "casual_chat", "identity_query", "time_query", "date_query"} and not tools:
        return None
    steps: list[PlanStep] = [
        PlanStep(order=1, title="Entender", detail=f"Classificar o pedido como {intent}.", reversible=True),
    ]
    if tools:
        steps.append(
            PlanStep(
                order=len(steps) + 1,
                title="Consultar",
                detail="Usar somente as ferramentas autorizadas para este pedido.",
                reversible=True,
                tool=tools[0],
            )
        )
    steps.append(PlanStep(order=len(steps) + 1, title="Responder", detail="Entregar a resposta direta e verificada.", reversible=True))
    return Plan(
        objective="Atender ao pedido com o menor caminho seguro.",
        web_needed=web_needed,
        tools_needed=tools,
        risks=["Confirmacao necessaria antes de executar."] if requires_confirmation else [],
        user_confirmation_required=requires_confirmation,
        steps=steps,
    )
