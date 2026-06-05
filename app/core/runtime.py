from __future__ import annotations

import os


CLOUD_RUNTIME = "cloud"
LOCAL_LEGACY_RUNTIME = "local_legacy"


def get_runtime() -> str:
    if os.getenv("VERCEL", "").strip() == "1":
        return CLOUD_RUNTIME
    configured = os.getenv("AGENTE_FINO_RUNTIME", CLOUD_RUNTIME).strip().lower().replace("-", "_")
    if configured in {"local", "legacy", "local_legacy", "windows_local"}:
        return LOCAL_LEGACY_RUNTIME
    return CLOUD_RUNTIME


def is_cloud() -> bool:
    return get_runtime() == CLOUD_RUNTIME


def is_local_legacy() -> bool:
    return get_runtime() == LOCAL_LEGACY_RUNTIME


def cloud_blocks_local_tools() -> bool:
    return is_cloud()

