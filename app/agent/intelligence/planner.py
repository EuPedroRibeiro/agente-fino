from __future__ import annotations


def build_plan(intent: str, tools: list[str]) -> dict:
    steps = ["entender pedido", "coletar contexto"]
    if tools:
        steps.append("executar ferramenta segura")
    steps.extend(["verificar resposta", "responder de forma limpa"])
    return {"intent": intent, "tools_needed": tools, "steps": steps}
