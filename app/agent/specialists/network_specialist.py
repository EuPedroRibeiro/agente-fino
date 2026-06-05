from __future__ import annotations


class NetworkSpecialist:
    name = "network"

    def analyze(self, state) -> dict:
        return {
            "specialist": self.name,
            "diagnosis": "Foco em IP, gateway, DNS, rota, SMB, DHCP e impressoras em rede.",
            "signals": ["validar IP/gateway/DNS", "identificar APIPA 169.254", "separar falha de nome e falha de conectividade"],
        }

    def suggest_questions(self, state) -> list[str]:
        return ["Outros PCs acessam a rede?", "O problema e por IP, nome ou ambos?"]

    def suggest_safe_actions(self, state) -> list[dict]:
        return [{"tool": "get_network_info", "reason": "Coletar rede atual sem modificar configuracao."}]

    def risk_assessment(self, state) -> str:
        return "medium" if "renew" in state.normalized_message or "renovar" in state.normalized_message else "low"
