from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from modules.darkforest.history import read_scan_history, save_scan_history
from modules.darkforest.parser import find_secrets, highest_risk, public_pattern_catalog
from modules.darkforest.safety import DarkForestConfig, classify_target, ensure_authorized, safe_target_label


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}
TEXT_SUFFIXES = {
    ".env",
    ".ini",
    ".json",
    ".jsonl",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".cfg",
    ".conf",
    ".xml",
    ".html",
    ".css",
    ".sh",
    ".ps1",
    ".bat",
    ".dockerfile",
}


class DarkForestService:
    def __init__(self, config: DarkForestConfig | None = None) -> None:
        self.config = config or DarkForestConfig.from_env()

    def status(self) -> dict[str, Any]:
        external = Path(self.config.external_path)
        return {
            "enabled": self.config.enabled,
            "name": "DarkForest Hunter",
            "label": "Scanner de Vazamento de Chaves",
            "external_path": self.config.external_path,
            "external_available": external.exists(),
            "max_runtime_seconds": self.config.max_runtime_seconds,
            "mask_secrets": self.config.mask_secrets,
            "save_history": self.config.save_history,
            "allow_remote_targets": self.config.allow_remote_targets,
            "patterns": public_pattern_catalog(),
        }

    def history(self, limit: int = 30) -> list[dict[str, Any]]:
        return read_scan_history(limit)

    def scan(
        self,
        *,
        target: str,
        accepted_notice: bool,
        confirmed_authorization: bool,
        user: str = "local",
    ) -> dict[str, Any]:
        if not self.config.enabled:
            raise RuntimeError("Modulo DarkForest desativado.")
        ensure_authorized(accepted_notice=accepted_notice, confirmed_authorization=confirmed_authorization)

        clean_target = (target or "").strip().strip("\"'")
        target_type = classify_target(clean_target)
        started = time.perf_counter()
        findings: list[dict[str, Any]] = []
        scanned_files = 0
        skipped_files = 0
        status = "completed"
        warnings: list[str] = []

        if target_type == "empty":
            raise ValueError("Informe um caminho local ou texto autorizado para analise.")
        if target_type == "remote_url" and not self.config.allow_remote_targets:
            status = "blocked_remote"
            warnings.append("Alvo remoto bloqueado. Clone ou baixe o repositorio autorizado e informe o caminho local.")
        elif target_type == "text":
            findings.extend(find_secrets(clean_target, source="texto informado"))
            scanned_files = 1
        else:
            root = Path(clean_target).expanduser()
            if not root.exists():
                raise FileNotFoundError(f"Caminho nao encontrado: {clean_target}")
            if root.is_file():
                found, skipped = self._scan_file(root, root.name)
                findings.extend(found)
                scanned_files += 0 if skipped else 1
                skipped_files += 1 if skipped else 0
            else:
                for file_path in self._iter_files(root, started):
                    rel = str(file_path.relative_to(root)) if file_path.is_relative_to(root) else str(file_path)
                    found, skipped = self._scan_file(file_path, rel)
                    if skipped:
                        skipped_files += 1
                    else:
                        scanned_files += 1
                        findings.extend(found)
                    if time.perf_counter() - started >= self.config.max_runtime_seconds:
                        status = "partial_timeout"
                        warnings.append("Calculo parcial por limite de tempo.")
                        break

        risk_level = highest_risk([finding["risk"] for finding in findings])
        report = {
            "module": "darkforest",
            "status": status,
            "target_type": target_type,
            "target": safe_target_label(clean_target),
            "findings_count": len(findings),
            "risk_level": risk_level,
            "findings": sorted(findings, key=lambda item: (self._risk_sort(item.get("risk")), item.get("source", "")), reverse=True),
            "scanned_files": scanned_files,
            "skipped_files": skipped_files,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "recommendation": self._summary_recommendation(risk_level, len(findings)),
        }
        report = mask_secrets(report)
        if self.config.save_history:
            save_scan_history(
                user=user,
                target=clean_target,
                findings_count=len(findings),
                risk_level=risk_level,
                status=status,
            )
        return report

    def _iter_files(self, root: Path, started: float):
        for path in root.rglob("*"):
            if time.perf_counter() - started >= self.config.max_runtime_seconds:
                break
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file():
                yield path

    def _scan_file(self, path: Path, source: str) -> tuple[list[dict[str, Any]], bool]:
        if not self._looks_text(path):
            return [], True
        try:
            if path.stat().st_size > 2_000_000:
                return [], True
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], True
        return find_secrets(content, source=source), False

    @staticmethod
    def _looks_text(path: Path) -> bool:
        name = path.name.lower()
        if name.startswith(".env") or name in {"dockerfile", "makefile"}:
            return True
        return path.suffix.lower() in TEXT_SUFFIXES

    @staticmethod
    def _risk_sort(risk: str | None) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get((risk or "").lower(), 0)

    @staticmethod
    def _summary_recommendation(risk_level: str, findings_count: int) -> str:
        if findings_count <= 0:
            return "Nenhum padrao sensivel encontrado. Continue usando variaveis de ambiente e cofres de segredo."
        if risk_level == "critical":
            return "Revogue os segredos criticos imediatamente, gere novos valores e revise historico de exposicao."
        if risk_level == "high":
            return "Restrinja, rotacione e mova os segredos para armazenamento seguro."
        return "Revise os achados e remova valores hardcoded."

