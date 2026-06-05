from __future__ import annotations


BLOCKED_PATTERNS = [
    "baixa e executa",
    "baixar e executar",
    "download and run",
    "powershell -",
    "cmd /c",
    "regedit",
    "desativar antivirus",
    "desativar firewall",
    "ativador",
    "crack",
    "bypass de licenca",
    "roubar senha",
    "coletar senha",
    "ocultar malware",
    "invadir",
    "exfiltrar",
    "formatar",
]

MEDIUM_ACTIONS = ["reiniciar", "limpar", "reset", "flush dns", "renovar ip", "restart"]


class SafetyChecker:
    def check(self, message: str, selected_tools: list[str]) -> dict:
        text = message.lower()
        for pattern in BLOCKED_PATTERNS:
            if pattern in text:
                return {
                    "allowed": False,
                    "risk_level": "blocked",
                    "needs_confirmation": False,
                    "reason": f"Pedido bloqueado por politica de seguranca: {pattern}",
                }
        risky_tool = any(tool in {"restart_spooler", "clean_temp", "flush_dns", "renew_ip", "clear_print_queue"} for tool in selected_tools)
        medium_text = any(pattern in text for pattern in MEDIUM_ACTIONS)
        if risky_tool or medium_text:
            return {
                "allowed": True,
                "risk_level": "medium",
                "needs_confirmation": True,
                "reason": "Acao de impacto medio exige confirmacao antes de executar.",
            }
        return {"allowed": True, "risk_level": "low", "needs_confirmation": False, "reason": "Diagnostico permitido."}
