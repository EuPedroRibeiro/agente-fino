from __future__ import annotations

from app.agent.schemas.plans import Plan, PlanStep


def create_plan(state) -> Plan:
    tools_needed = list(state.selected_tools)
    steps = [
        PlanStep(order=1, title="Coletar contexto", detail="Usar relatorio local, memoria e base RAG antes de sugerir mudancas.", tool="generate_report" if state.local_report else None),
        PlanStep(order=2, title="Cruzar evidencias", detail="Comparar sintomas com base local e, se necessario, fontes web citaveis.", tool="search_knowledge"),
        PlanStep(order=3, title="Diagnosticar causa provavel", detail="Separar certeza, hipotese e proximo teste seguro."),
        PlanStep(order=4, title="Sugerir acao reversivel", detail="Priorizar verificacoes e acoes de baixo impacto antes de qualquer mudanca."),
    ]
    if state.web_needed:
        steps.insert(2, PlanStep(order=3, title="Pesquisar fontes atuais", detail="Preferir documentacao oficial e citar somente fontes lidas.", tool="search_web"))
    if state.requested_action:
        steps.append(PlanStep(order=len(steps) + 1, title="Pedir confirmacao", detail="Acao solicitada exige confirmacao humana e allowlist.", reversible=False))
    return Plan(
        objective=f"Resolver ou orientar: {state.user_message[:180]}",
        assumptions=["Ambiente Windows local", "Acoes destrutivas nao serao executadas sem confirmacao"],
        required_context=["status do PC", "RAG local", "memoria tecnica"],
        web_needed=state.web_needed,
        tools_needed=tools_needed,
        risks=[state.risk_level],
        reversible_first=True,
        user_confirmation_required=state.needs_confirmation,
        steps=steps,
    )
