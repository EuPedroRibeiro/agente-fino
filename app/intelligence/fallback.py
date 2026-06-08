from __future__ import annotations

from app.agent.router import normalize_for_intent


def greeting_reply(message: str) -> str:
    text = normalize_for_intent(message)
    if text in {"bom dia"}:
        return "Bom dia! Tô online. Manda a boa."
    if text in {"boa tarde"}:
        return "Boa tarde! Tô online. Manda a boa."
    if text in {"boa noite"}:
        return "Boa noite! Tô online. Manda a boa."
    return "Fala! Tô online. Manda a boa."


def casual_reply(message: str) -> str | None:
    text = normalize_for_intent(message).strip(" .!?")
    if text in {"obrigado", "obrigada", "valeu"}:
        return "Fechado. Quando precisar, me chama."
    if text in {"teste"}:
        return "Tô respondendo. Pode mandar."
    if text in {"kkkk", "top", "gostei"}:
        return "Boa. Manda a próxima."
    return None


def fallback_answer(intent: str, message: str = "") -> str:
    if intent == "greeting":
        return greeting_reply(message)
    casual = casual_reply(message)
    if casual:
        return casual
    if intent in {"cpf_lookup", "cnpj_lookup", "cpf_validate"}:
        return "Nao consegui concluir a consulta documental agora. Tente novamente em instantes."
    if intent in {"web_research", "deep_research", "deep_web_research"}:
        return "Não consegui consultar fontes confiáveis agora. Posso seguir com uma análise geral sem pesquisa."
    if intent in {"local_metric", "pc_analysis", "pc_diagnostic"}:
        return "Não consegui ler essa informação local agora. Tente novamente ou informe o alvo com mais detalhe."
    return "Não consegui concluir esse pedido agora. Tente novamente em instantes."
