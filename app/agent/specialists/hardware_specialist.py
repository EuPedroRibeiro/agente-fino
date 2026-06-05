from __future__ import annotations


class HardwareSpecialist:
    name = "hardware"

    def analyze(self, state) -> dict:
        return {
            "specialist": self.name,
            "diagnosis": "Foco em CPU, RAM, disco, temperatura, bateria, GPU e drivers.",
            "signals": ["correlacionar lentidao com CPU/RAM/disco", "avaliar sintomas fisicos e temperatura"],
        }

    def suggest_questions(self, state) -> list[str]:
        return ["O equipamento esquenta?", "E HD ou SSD?", "Ha desligamento ou travamento?"]

    def suggest_safe_actions(self, state) -> list[dict]:
        return [{"tool": "generate_report", "reason": "Coletar gargalos de hardware pelo relatorio local."}]

    def risk_assessment(self, state) -> str:
        return "low"
