from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from app.core.paths import log_dir


HOST = "127.0.0.1"
PORT = 8765
LOGIN_URL = f"http://{HOST}:{PORT}/login"
HEALTH_PATH = f"http://{HOST}:{PORT}/api/health"


def _server_ready() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_PATH, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def _start_backend() -> subprocess.Popen | None:
    if _server_ready():
        return None
    logs = log_dir()
    stdout = open(logs / "desktop.log", "a", encoding="utf-8")
    stderr = open(logs / "desktop.err.log", "a", encoding="utf-8")
    return subprocess.Popen([sys.executable, "main.py"], cwd=Path(__file__).resolve().parent, stdout=stdout, stderr=stderr)


def main() -> None:
    process = _start_backend()
    for _ in range(40):
        if _server_ready():
            break
        time.sleep(0.25)
    import webview

    webview.create_window("NexusTI AI", LOGIN_URL, width=1280, height=820)
    try:
        webview.start()
    finally:
        if process and process.poll() is None:
            process.terminate()


if __name__ == "__main__":
    main()
