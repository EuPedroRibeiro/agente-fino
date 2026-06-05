from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging_db import log_action
from app.core.security import AllowedAction, is_path_inside, is_running_as_admin, is_windows, user_temp_directories


def _remove_file(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except OSError:
        return False


def _remove_empty_directory(path: Path) -> bool:
    try:
        path.rmdir()
        return True
    except OSError:
        return False


def clean_temp_files() -> dict[str, Any]:
    action_name = AllowedAction.CLEAN_TEMP.value
    now = time.time()
    min_age = settings.temp_file_min_age_seconds
    deleted_files = 0
    deleted_dirs = 0
    skipped = 0
    errors = 0
    temp_dirs = user_temp_directories()

    for temp_dir in temp_dirs:
        for current_root, directories, files in os.walk(temp_dir, topdown=False):
            root = Path(current_root)
            if not is_path_inside(root, temp_dir):
                skipped += 1
                continue

            for filename in files:
                file_path = root / filename
                if not is_path_inside(file_path, temp_dir):
                    skipped += 1
                    continue

                try:
                    if now - file_path.stat().st_mtime < min_age:
                        skipped += 1
                        continue
                except OSError:
                    skipped += 1
                    continue

                if _remove_file(file_path):
                    deleted_files += 1
                else:
                    errors += 1

            for directory in directories:
                directory_path = root / directory
                if not is_path_inside(directory_path, temp_dir):
                    skipped += 1
                    continue
                if _remove_empty_directory(directory_path):
                    deleted_dirs += 1

    message = (
        f"Limpeza concluida. Arquivos removidos: {deleted_files}. "
        f"Pastas vazias removidas: {deleted_dirs}. Ignorados: {skipped}. Erros: {errors}."
    )
    status = "success" if errors == 0 else "partial"
    log = log_action(action_name, status, message, technical_error=None if errors == 0 else f"{errors} item(ns) nao removidos.")
    return {
        "action": action_name,
        "status": status,
        "message": message,
        "deleted_files": deleted_files,
        "deleted_directories": deleted_dirs,
        "skipped": skipped,
        "errors": errors,
        "temp_directories": [str(path) for path in temp_dirs],
        "log": log,
    }


def restart_spooler() -> dict[str, Any]:
    action_name = AllowedAction.RESTART_SPOOLER.value

    if not is_windows():
        message = "Reinicio do spooler esta disponivel apenas no Windows."
        log = log_action(action_name, "error", message, requires_admin=True, technical_error="Sistema operacional nao suportado.")
        return {"action": action_name, "status": "error", "requires_admin": True, "message": message, "log": log}

    if not is_running_as_admin():
        message = "Permissao elevada necessaria. Execute o terminal como administrador para reiniciar o spooler."
        log = log_action(
            action_name,
            "error",
            message,
            requires_admin=True,
            technical_error="Processo atual nao esta elevado.",
        )
        return {
            "action": action_name,
            "status": "error",
            "requires_admin": True,
            "message": message,
            "log": log,
        }

    commands = [
        ["net", "stop", "spooler"],
        ["net", "start", "spooler"],
    ]
    outputs: list[str] = []

    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                encoding="oem",
                errors="replace",
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            message = f"Falha ao executar acao permitida {command[0]}: {exc}"
            log = log_action(action_name, "error", message, requires_admin=True, technical_error=str(exc))
            return {"action": action_name, "status": "error", "requires_admin": True, "message": message, "log": log}

        output = f"{result.stdout}\n{result.stderr}".strip()
        outputs.append(output)
        if result.returncode != 0 and "nao foi iniciado" not in output.lower():
            message = f"Falha ao reiniciar spooler: {output or 'erro desconhecido'}"
            log = log_action(
                action_name,
                "error",
                message,
                requires_admin=True,
                technical_error=output or f"Codigo de saida {result.returncode}",
            )
            return {
                "action": action_name,
                "status": "error",
                "requires_admin": True,
                "message": message,
                "details": outputs,
                "log": log,
            }

    message = "Spooler de impressao reiniciado com sucesso."
    log = log_action(action_name, "success", message, requires_admin=True)
    return {"action": action_name, "status": "success", "requires_admin": True, "message": message, "details": outputs, "log": log}
