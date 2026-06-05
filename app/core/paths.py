from __future__ import annotations

import sys
from pathlib import Path


APP_DATA_NAME = "NexusTI AI"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    return base / relative_path


def app_data_dir() -> Path:
    import os

    base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = base / APP_DATA_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    path = app_data_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
