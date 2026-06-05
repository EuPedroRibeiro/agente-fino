from __future__ import annotations


class WindowsSpecialist:
    name = "windows"

    def analyze(self, state) -> dict:
        return {
            "specialist": self.name,
            "diagnosis": "Foco em servicos, Event Viewer, Windows Update, SMB/RPC, drivers e permissoes.",
            "signals": ["verificar eventos recentes", "validar servicos relevantes", "priorizar coleta antes de alterar sistema"],
        }

    def suggest_questions(self, state) -> list[str]:
        return ["Qual erro exato aparece?", "Isso comecou apos update, driver ou queda de energia?"]

    def suggest_safe_actions(self, state) -> list[dict]:
        return [{"tool": "generate_report", "reason": "Coletar contexto antes de alterar o Windows."}]

    def risk_assessment(self, state) -> str:
        return "medium" if state.requested_action else "low"
