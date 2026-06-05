from __future__ import annotations

import ctypes
import os
import sys
from enum import StrEnum
from pathlib import Path


class AllowedAction(StrEnum):
    CLEAN_TEMP = "clean-temp"
    RESTART_SPOOLER = "restart-spooler"
    GENERATE_REPORT = "generate-report"


ALLOWED_ACTIONS = {action.value for action in AllowedAction}


def is_allowed_action(action_name: str) -> bool:
    return action_name in ALLOWED_ACTIONS


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_running_as_admin() -> bool:
    if not is_windows():
        return False

    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_path_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def user_temp_directories() -> list[Path]:
    candidates = [
        os.getenv("TEMP"),
        os.getenv("TMP"),
        str(Path.home() / "AppData" / "Local" / "Temp"),
    ]

    safe_dirs: list[Path] = []
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved.is_dir() and resolved not in safe_dirs:
            safe_dirs.append(resolved)
    return safe_dirs
