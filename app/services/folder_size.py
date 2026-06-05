from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GB = 1024**3
CACHE_TTL_SECONDS = 60
MAX_SECONDS = 15.0
MAX_ENTRIES = 400_000

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass
class FolderSizeBudget:
    started: float
    max_seconds: float
    max_entries: int
    entries_seen: int = 0
    file_count: int = 0
    folder_count: int = 0
    skipped_count: int = 0
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


def clear_folder_size_cache() -> None:
    _CACHE.clear()


def resolve_folder_target(message: str) -> dict[str, Any]:
    original = (message or "").strip()
    normalized = _normalize_text(original)
    explicit = _extract_windows_path(original)
    if explicit:
        return _target(explicit, source="explicit_path")

    if "%userprofile%" in normalized:
        return _target(os.getenv("USERPROFILE") or str(Path.home()), source="env_userprofile")

    user_profile = os.getenv("USERPROFILE") or str(Path.home())
    system_drive = os.getenv("SystemDrive", "C:")
    requested_drive = _drive_from_message(normalized) or system_drive

    if _looks_like_local_path_context(normalized):
        if "system32" in normalized:
            return _target(f"{requested_drive}\\Windows\\System32", source="natural_language_alias")
        if "windows" in normalized:
            return _target(f"{requested_drive}\\Windows", source="natural_language_alias")

    if _has_any(normalized, ["minha pasta usuario", "minha pasta de usuario", "meu usuario", "meu user", "pasta suporte"]):
        return _target(user_profile, source="user_profile_alias")

    if _has_any(normalized, ["pasta usuarios", "pasta usuario", "pasta users", "usuarios consome", "usuario consome", "users pesa"]):
        return _target(f"{requested_drive}\\Users", source="users_alias")

    alias = _alias_path(normalized, user_profile)
    if alias:
        return _target(alias, source="known_folder_alias")

    return {"path": None, "source": "not_found", "error": "Nao consegui identificar uma pasta especifica na mensagem."}


def get_folder_size(
    path: str | os.PathLike[str],
    *,
    max_seconds: float = 10.0,
    max_entries: int = 160_000,
    use_cache: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        safe_seconds = min(max(1.0, float(max_seconds)), MAX_SECONDS)
        safe_entries = min(max(100, int(max_entries)), MAX_ENTRIES)
        target = _normalize_path_for_scan(path)
    except Exception as exc:
        return _error_result(str(path), started, "invalid_path", str(exc))

    cache_key = str(target).lower()
    now = time.time()
    if use_cache:
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] <= CACHE_TTL_SECONDS:
            payload = dict(cached[1])
            payload["cache_hit"] = True
            payload["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            return payload

    if not target.exists():
        return _error_result(str(target), started, "not_found", f"Nao encontrei esse caminho: {target}")
    if not target.is_dir():
        return _error_result(str(target), started, "not_directory", f"O caminho nao e uma pasta: {target}")

    budget = FolderSizeBudget(started=time.perf_counter(), max_seconds=safe_seconds, max_entries=safe_entries)
    size_bytes = _scan_folder(target, budget)
    result = {
        "path": str(target),
        "size_bytes": size_bytes,
        "size_gb": round(size_bytes / GB, 2),
        "file_count": budget.file_count,
        "folder_count": budget.folder_count,
        "skipped_count": budget.skipped_count,
        "entries_seen": budget.entries_seen,
        "timed_out": budget.timed_out,
        "partial": budget.timed_out or budget.skipped_count > 0,
        "cache_hit": False,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "safety_note": "Ferramenta somente leitura; nenhum arquivo foi apagado ou alterado.",
    }
    if use_cache:
        _CACHE[cache_key] = (now, dict(result))
    return result


def _scan_folder(path: Path, budget: FolderSizeBudget) -> int:
    total = 0
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                if not budget.allow_next():
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        budget.file_count += 1
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        budget.folder_count += 1
                        total += _scan_folder(Path(entry.path), budget)
                except (OSError, PermissionError):
                    budget.skipped_count += 1
                    continue
    except (OSError, PermissionError):
        budget.skipped_count += 1
    return total


def _target(path: str, *, source: str) -> dict[str, Any]:
    normalized = str(path).strip().strip('"').strip("'").replace("/", "\\")
    if re.match(r"^[a-zA-Z]:", normalized):
        normalized = normalized[0].upper() + normalized[1:]
    return {"path": normalized.rstrip(" .;,"), "source": source}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("/", "\\")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _drive_from_message(normalized: str) -> str | None:
    patterns = [
        r"\b(?:disco|unidade)\s+([a-z])\b",
        r"\b(?:no|na|do|da)\s+([a-z])\b",
        r"\b([a-z]):\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return f"{match.group(1).upper()}:"
    return None


def _looks_like_local_path_context(normalized: str) -> bool:
    if not any(term in normalized for term in ["windows", "system32"]):
        return False
    context_terms = [
        "pasta",
        "diretorio",
        "folder",
        "disco",
        "unidade",
        "arquivos",
        "conta",
        "contar",
        "quantos",
        "tamanho",
        "ocupa",
        "usa",
        "verifica",
        "espaco",
    ]
    return _has_any(normalized, context_terms) or _drive_from_message(normalized) is not None


def _extract_windows_path(message: str) -> str | None:
    quoted = re.search(r'["\']([a-zA-Z]:[\\/][^"\']+)["\']', message)
    if quoted:
        return _clean_path_candidate(quoted.group(1))

    drive_match = re.search(r"(?i)\b([a-z]:[\\/][^\r\n]+)", message)
    if drive_match:
        return _clean_path_candidate(drive_match.group(1))
    return None


def _clean_path_candidate(candidate: str) -> str:
    path = candidate.strip().strip('"').strip("'").replace("/", "\\")
    normalized = _normalize_text(path)
    tail_patterns = [
        r"\s+usa\s+quanto.*$",
        r"\s+consome.*$",
        r"\s+pesa.*$",
        r"\s+ocupa.*$",
        r"\s+o\s+espaco\s+usado.*$",
        r"\s+espaco\s+usado.*$",
        r"\s+quanto\s+de\s+espaco.*$",
        r"\s+quanto.*$",
        r"\s+verifica.*$",
    ]
    for pattern in tail_patterns:
        match = re.search(pattern, normalized)
        if match:
            path = path[: match.start()].strip()
            break
    path = re.sub(r"[?.!,;:]+$", "", path).strip()
    if re.match(r"^[a-zA-Z]:", path):
        path = path[0].upper() + path[1:]
    return path.rstrip("\\") if len(path) > 3 else path


def _alias_path(normalized: str, user_profile: str) -> str | None:
    aliases = [
        (["area de trabalho", "desktop"], "Desktop"),
        (["downloads", "download"], "Downloads"),
        (["documentos", "documents"], "Documents"),
        (["appdata"], "AppData"),
    ]
    for terms, folder in aliases:
        if _has_any(normalized, terms):
            return str(Path(user_profile) / folder)
    return None


def _normalize_path_for_scan(path: str | os.PathLike[str]) -> Path:
    expanded = os.path.expandvars(str(path)).strip().strip('"').strip("'").replace("/", "\\")
    if not expanded:
        raise ValueError("Caminho vazio.")
    if expanded.startswith("\\\\"):
        raise ValueError("Caminhos de rede/UNC nao sao permitidos nesta ferramenta.")
    return Path(expanded)


def _error_result(path: str, started: float, error_type: str, message: str) -> dict[str, Any]:
    return {
        "path": path,
        "size_bytes": 0,
        "size_gb": 0.0,
        "file_count": 0,
        "folder_count": 0,
        "skipped_count": 0,
        "entries_seen": 0,
        "timed_out": False,
        "partial": True,
        "cache_hit": False,
        "error": message,
        "error_type": error_type,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "safety_note": "Ferramenta somente leitura; nenhum arquivo foi apagado ou alterado.",
    }
