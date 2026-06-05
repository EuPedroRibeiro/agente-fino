from __future__ import annotations


class WebResearchSpecialist:
    name = "web_research"

    def analyze(self, state) -> dict:
        return {
            "specialist": self.name,
            "diagnosis": "Foco em informacao atual, documentacao oficial, drivers, compatibilidade, versoes, frameworks, CVEs e fontes.",
            "signals": ["preferir fonte oficial", "citar somente paginas lidas", "marcar incerteza quando fonte for fraca"],
        }

    def suggest_questions(self, state) -> list[str]:
        return ["Qual modelo, versao ou fabricante exato deve ser pesquisado?"]

    def suggest_safe_actions(self, state) -> list[dict]:
        return [{"tool": "search_web", "reason": "Pesquisar fonte atual e citavel."}]

    def risk_assessment(self, state) -> str:
        return "low"
