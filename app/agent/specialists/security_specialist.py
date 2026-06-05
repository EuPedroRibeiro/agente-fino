from __future__ import annotations


class SecuritySpecialist:
    name = "security"

    def analyze(self, state) -> dict:
        return {
            "specialist": self.name,
            "diagnosis": "Foco em antivirus, firewall, permissoes, logs suspeitos e boas praticas.",
            "signals": ["bloquear execucao arbitraria", "nao coletar segredos", "evitar desativar protecoes"],
        }

    def suggest_questions(self, state) -> list[str]:
        return ["Qual alerta apareceu?", "Ha arquivo suspeito ou comportamento anormal?"]

    def suggest_safe_actions(self, state) -> list[dict]:
        return [{"tool": "generate_report", "reason": "Coleta local sem alterar protecoes."}]

    def risk_assessment(self, state) -> str:
        return "high" if state.requested_action else "medium"
