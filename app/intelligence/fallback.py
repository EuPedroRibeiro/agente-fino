from __future__ import annotations

from app.intelligence.local_responses import safe_answer_local_intent


def fallback_answer(intent: str, message: str = "") -> str:
    local_answer = safe_answer_local_intent(intent, message)
    if local_answer:
        return local_answer
    if intent in {"cpf_lookup", "cnpj_lookup", "cpf_validate"}:
        return "Nao consegui concluir a consulta documental agora. Tente novamente em instantes."
    if intent in {"web_research", "deep_research", "deep_web_research"}:
        return "Nao consegui consultar fontes confiaveis agora. Posso seguir com uma analise geral sem pesquisa."
    if intent in {"local_metric", "pc_analysis", "pc_diagnostic"}:
        return "Nao consegui ler essa informacao local agora. Tente novamente ou informe o alvo com mais detalhe."
    return "Nao consegui concluir esse pedido agora. Tente novamente em instantes."
