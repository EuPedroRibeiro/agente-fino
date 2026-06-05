from __future__ import annotations


class HallucinationGuard:
    def check(self, *, answer: str, web_used: bool, citations: list, evidence: list) -> dict:
        warnings: list[str] = []
        confidence_delta = 0.0
        if web_used and not citations:
            warnings.append("Resposta usou web, mas nao ha citacoes validas.")
            confidence_delta -= 0.25
        if not evidence and not citations:
            warnings.append("Resposta com pouca evidencia; recomenda-se coletar mais contexto.")
            confidence_delta -= 0.15
        if "pesquisei" in answer.lower() and not web_used:
            warnings.append("Resposta menciona pesquisa sem web_used verdadeiro.")
            confidence_delta -= 0.35
        return {"warnings": warnings, "confidence_delta": confidence_delta}
