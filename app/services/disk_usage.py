from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.security import is_windows


GB = 1024**3
MAX_LIMIT = 30
MAX_DEPTH = 5
MAX_SECONDS = 20
MAX_ENTRIES = 250_000


@dataclass
class ScanBudget:
    started: float
    max_seconds: float
    max_entries: int
    entries_seen: int = 0
    skipped: int = 0
    timed_out: bool = False

    def allow_next(self) -> bool:
        if self.entries_seen >= self.max_entries:
            self.timed_out = True
            return False
        if time.perf_counter() - self.started > self.max_seconds:
            self.timed_out = True
            return False
        self.entries_seen += 1
        return True


def get_disk_usage_ranking(
    root: str | None = None,
    *,
    limit: int = 10,
    max_depth: int = 3,
    max_seconds: float = 8,
    max_entries: int = 80_000,
) -> dict[str, Any]:
    safe_limit = min(max(1, int(limit)), MAX_LIMIT)
    safe_depth = min(max(1, int(max_depth)), MAX_DEPTH)
    safe_seconds = min(max(1.0, float(max_seconds)), MAX_SECONDS)
    safe_entries = min(max(500, int(max_entries)), MAX_ENTRIES)
    scan_root = _resolve_root(root)
    budget = ScanBudget(started=time.perf_counter(), max_seconds=safe_seconds, max_entries=safe_entries)

    direct_dirs = []
    try:
        with os.scandir(scan_root) as iterator:
            for entry in iterator:
                if not budget.allow_next():
                    break
                if not entry.is_dir(follow_symlinks=False):
                    continue
                direct_dirs.append(entry)
    except (OSError, PermissionError) as exc:
        return {
            "root": str(scan_root),
            "limit": safe_limit,
            "max_depth": safe_depth,
            "elapsed_ms": int((time.perf_counter() - budget.started) * 1000),
            "folders": [],
            "skipped": budget.skipped,
            "truncated": True,
            "error": str(exc),
            "safety_note": "Ferramenta somente leitura; nenhum arquivo foi apagado ou alterado.",
        }

    children = []
    per_folder_seconds = min(4.0, max(0.5, safe_seconds / max(1, len(direct_dirs))))
    per_folder_entries = max(500, safe_entries // max(1, len(direct_dirs)))
    for entry in direct_dirs:
        if time.perf_counter() - budget.started > safe_seconds:
            budget.timed_out = True
            break
        folder_budget = ScanBudget(started=time.perf_counter(), max_seconds=per_folder_seconds, max_entries=per_folder_entries)
        size_bytes = _folder_size(Path(entry.path), depth=safe_depth - 1, budget=folder_budget)
        budget.entries_seen += folder_budget.entries_seen
        budget.skipped += folder_budget.skipped
        budget.timed_out = budget.timed_out or folder_budget.timed_out
        complete = not folder_budget.timed_out
        children.append(
            {
                "path": str(Path(entry.path)),
                "name": entry.name,
                "size_bytes": size_bytes,
                "size_gb": round(size_bytes / GB, 2),
                "complete": complete,
                "observation": _observation(entry.path, complete=complete),
            }
        )

    children.sort(key=lambda item: item["size_bytes"], reverse=True)
    return {
        "root": str(scan_root),
        "limit": safe_limit,
        "max_depth": safe_depth,
        "elapsed_ms": int((time.perf_counter() - budget.started) * 1000),
        "folders": children[:safe_limit],
        "scanned_entries": budget.entries_seen,
        "skipped": budget.skipped,
        "truncated": budget.timed_out,
        "safety_note": "Ferramenta somente leitura; nenhum arquivo foi apagado ou alterado.",
    }


def _resolve_root(root: str | None) -> Path:
    if root:
        candidate = Path(root).expanduser()
    elif is_windows():
        candidate = Path(os.getenv("SystemDrive", "C:") + "\\")
    else:
        candidate = Path.home()

    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"Raiz de varredura invalida: {resolved}")
    if str(resolved).startswith("\\\\"):
        raise ValueError("Caminhos de rede/UNC nao sao permitidos nesta ferramenta.")
    return resolved


def _folder_size(path: Path, *, depth: int, budget: ScanBudget) -> int:
    total = 0
    if depth < 0 or not budget.allow_next():
        return total
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                if not budget.allow_next():
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False) and depth > 0:
                        total += _folder_size(Path(entry.path), depth=depth - 1, budget=budget)
                except (OSError, PermissionError):
                    budget.skipped += 1
                    continue
    except (OSError, PermissionError):
        budget.skipped += 1
    return total


def _observation(path: str, *, complete: bool = True) -> str:
    lowered = path.lower()
    suffix = "" if complete else " Estimativa parcial por limite de seguranca."
    if "windows" in lowered:
        return "Pasta do sistema; nao apague manualmente." + suffix
    if "program files" in lowered or "arquivos de programas" in lowered:
        return "Programas instalados; remova apenas pelo desinstalador/configuracoes." + suffix
    if "users" in lowered or "usuarios" in lowered:
        return "Perfil de usuario; analisar Downloads, Videos, Desktop e caches com cuidado." + suffix
    if "$recycle.bin" in lowered:
        return "Lixeira; pode ocupar espaco, mas confirme antes de esvaziar." + suffix
    return "Somente leitura; revisar conteudo antes de qualquer limpeza." + suffix
