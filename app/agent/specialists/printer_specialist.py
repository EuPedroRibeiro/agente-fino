from __future__ import annotations


class PrinterSpecialist:
    name = "printer"

    def analyze(self, state) -> dict:
        return {
            "specialist": self.name,
            "diagnosis": "Foco em spooler, fila, porta, driver, consumivel, Brother/Epson/HP e impressao em rede.",
            "signals": ["confirmar modelo da impressora", "verificar status do spooler", "checar fila e driver"],
        }

    def suggest_questions(self, state) -> list[str]:
        return ["Qual modelo exato da impressora?", "Ela e USB, rede cabeada ou Wi-Fi?", "A mensagem aparece no painel ou no Windows?"]

    def suggest_safe_actions(self, state) -> list[dict]:
        return [
            {"tool": "check_spooler", "reason": "Verificar spooler sem alterar nada."},
            {"tool": "list_printers", "reason": "Listar impressoras instaladas para correlacionar porta/driver."},
        ]

    def risk_assessment(self, state) -> str:
        return "medium" if any(word in state.normalized_message for word in ["reiniciar", "limpar fila", "reset"]) else "low"
