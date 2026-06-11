from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from app.redlab.models import TargetScanResult


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in os.getenv(name, "").split(",") if item.strip())


@dataclass(frozen=True)
class TargetConfig:
    enabled: bool
    allowlist: tuple[str, ...]
    allow_private: bool

    @classmethod
    def from_env(cls) -> "TargetConfig":
        return cls(
            enabled=_env_bool("REDLAB_TARGET_MODE_ENABLED", False),
            allowlist=_env_list("REDLAB_TARGET_ALLOWLIST"),
            allow_private=_env_bool("REDLAB_TARGET_ALLOW_PRIVATE", False),
        )


class RedLabTargetEngine:
    """Controlled target preflight. It never fires exploit payloads."""

    TECHNIQUES = ("sqli", "xss", "idor", "upload", "cmdi", "ssti", "ssrf", "redirect", "traversal")

    def __init__(self, config: TargetConfig | None = None) -> None:
        self.config = config or TargetConfig.from_env()

    def status(self) -> dict:
        return {
            "enabled": self.config.enabled,
            "mode": "allowlist_passive_preflight",
            "allowlist_count": len(self.config.allowlist),
            "allow_private": self.config.allow_private,
            "techniques": list(self.TECHNIQUES),
        }

    def validate_target(self, url: str, confirmed: bool) -> tuple[bool, str, str | None]:
        if not self.config.enabled:
            return False, "Target Mode esta desativado. Defina REDLAB_TARGET_MODE_ENABLED=true.", None
        if not confirmed:
            return False, "Confirme a autorizacao antes de preparar o alvo.", None
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False, "Informe uma URL HTTP ou HTTPS valida.", None
        host = parsed.hostname.lower()
        if not self._allowed_host(host):
            return False, "O host nao esta em REDLAB_TARGET_ALLOWLIST.", host
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
        except OSError:
            return False, "Nao foi possivel resolver o host allowlisted.", host
        if not self.config.allow_private and any(self._unsafe_ip(address) for address in addresses):
            return False, "Destino privado, local ou reservado bloqueado pela politica do Target Mode.", host
        return True, "Alvo allowlisted validado para preflight passivo.", host

    def scan(self, url: str, techniques: list[str], confirmed: bool) -> list[TargetScanResult]:
        valid, message, host = self.validate_target(url, confirmed)
        if not valid:
            raise PermissionError(message)
        selected = [item for item in techniques if item in self.TECHNIQUES] or list(self.TECHNIQUES)
        return [
            TargetScanResult(
                technique=technique,
                status="manual_review_ready",
                evidence=f"Preflight passivo preparado para {host}; nenhum payload foi disparado.",
                recommendation=self._recommendation(technique),
            )
            for technique in selected[:9]
        ]

    def _allowed_host(self, host: str) -> bool:
        return any(host == allowed or host.endswith(f".{allowed}") for allowed in self.config.allowlist)

    @staticmethod
    def _unsafe_ip(address: str) -> bool:
        ip = ipaddress.ip_address(address)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved

    @staticmethod
    def _recommendation(technique: str) -> str:
        recommendations = {
            "sqli": "Revise queries parametrizadas, privilegios do banco e tratamento de erros.",
            "xss": "Revise escaping contextual, sanitizacao e CSP.",
            "idor": "Revise autorizacao por objeto em todos os endpoints com identificadores.",
            "upload": "Revise allowlist, assinatura, MIME e armazenamento fora do webroot.",
            "cmdi": "Revise chamadas de processo e elimine concatenacao de entrada.",
            "ssti": "Revise uso de templates e impeça avaliacao de entrada nao confiavel.",
            "ssrf": "Revise allowlist de destinos, DNS e bloqueio de redes internas.",
            "redirect": "Revise destinos permitidos e normalize URLs antes de redirecionar.",
            "traversal": "Revise normalizacao de caminho e confinamento no diretorio permitido.",
        }
        return recommendations[technique]
