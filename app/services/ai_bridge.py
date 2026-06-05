from __future__ import annotations

import shutil
import subprocess
from typing import Any


class LocalAIBridge:
    """Ponte preparada para integrar o NexusTI AI com Ollama futuramente."""

    fallback_message = "IA local ainda nao configurada. O relatorio foi gerado e esta pronto para analise futura."

    def is_ollama_available(self) -> bool:
        if not shutil.which("ollama"):
            return False

        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False

        return result.returncode == 0

    def analyze_report(self, report: dict[str, Any]) -> dict[str, Any]:
        if not self.is_ollama_available():
            return {
                "available": False,
                "provider": "ollama",
                "message": self.fallback_message,
            }

        return {
            "available": True,
            "provider": "ollama",
            "message": "Ollama detectado. A analise real sera ativada em uma fase futura do projeto.",
        }

    def explain_error(self, error_text: str) -> dict[str, Any]:
        if not self.is_ollama_available():
            return {
                "available": False,
                "provider": "ollama",
                "message": "IA local ainda nao configurada. Erro registrado para analise futura.",
                "error_text": error_text,
            }

        return {
            "available": True,
            "provider": "ollama",
            "message": "Ollama detectado. Explicacao automatica sera implementada em fase futura.",
            "error_text": error_text,
        }
