from __future__ import annotations


class PerformanceSpecialist:
    name = "performance"

    def analyze(self, state) -> dict:
        return {
            "specialist": self.name,
            "diagnosis": "Foco em processos, inicializacao, disco 100%, RAM e navegador pesado.",
            "signals": ["top_processes", "uso de disco", "memoria disponivel", "eventos de erro"],
        }

    def suggest_questions(self, state) -> list[str]:
        return ["A lentidao ocorre ao iniciar, abrir navegador ou o tempo todo?"]

    def suggest_safe_actions(self, state) -> list[dict]:
        return [{"tool": "generate_report", "reason": "Identificar processos e gargalos atuais."}]

    def risk_assessment(self, state) -> str:
        return "low"
