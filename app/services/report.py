from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.logging_db import log_action
from app.core.security import AllowedAction
from app.services.ai_bridge import LocalAIBridge
from app.services.system_info import (
    get_disk_partitions,
    get_installed_printers,
    get_network_adapters,
    get_network_configuration,
    get_processes,
    get_recent_windows_critical_errors,
    get_service_status,
    get_system_status,
)


def _build_observations(status: dict[str, Any], spooler_status: dict[str, Any]) -> list[str]:
    observations: list[str] = []

    cpu_percent = status["cpu"]["percent"]
    ram_percent = status["memory"]["percent"]
    disk_percent = status["disk"]["percent"]

    if cpu_percent >= 90:
        observations.append("CPU com uso muito alto no momento da coleta.")
    elif cpu_percent >= 75:
        observations.append("CPU em uso elevado; verificar processos em destaque.")

    if ram_percent >= 90:
        observations.append("Memoria RAM em nivel critico; avaliar consumo por processo.")
    elif ram_percent >= 75:
        observations.append("Memoria RAM com uso elevado.")

    if disk_percent >= 90:
        observations.append("Disco quase cheio; liberar espaco e revisar arquivos temporarios.")
    elif disk_percent >= 80:
        observations.append("Disco com uso alto; monitorar crescimento.")

    if spooler_status["status"] == "stopped":
        observations.append("Spooler de impressao parado; impressoras podem falhar.")
    elif spooler_status["status"] == "error":
        observations.append("Nao foi possivel consultar o spooler de impressao.")

    if not observations:
        observations.append("Nenhum alerta critico detectado no momento da coleta.")

    return observations


def generate_technical_report(register_log: bool = True, deep: bool = True) -> dict[str, Any]:
    status = get_system_status()
    processes = get_processes(limit=15)
    spooler_status = get_service_status("Spooler")
    bridge = LocalAIBridge()
    unavailable_fast = "indisponivel no modo rapido"

    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "product": settings.app_name,
        "version": settings.app_version,
        "summary": {
            "hostname": status["hostname"],
            "operating_system": status["os"],
            "uptime": status["uptime"],
            "boot_time": status["boot_time"],
            "local_ip": status["local_ip"],
            "processor": status["machine"]["processor"],
            "architecture": status["machine"]["architecture"],
            "python_version": status["machine"]["python_version"],
        },
        "cpu": status["cpu"],
        "memory": status["memory"],
        "disk": status["disk"],
        "disk_partitions": get_disk_partitions(),
        "network": {
            "adapters": get_network_adapters(),
            "configuration": get_network_configuration() if deep else unavailable_fast,
        },
        "top_processes": processes,
        "services": {
            "print_spooler": spooler_status,
        },
        "printers": get_installed_printers() if deep else unavailable_fast,
        "windows_event_viewer": {
            "recent_critical_errors": get_recent_windows_critical_errors() if deep else unavailable_fast,
        },
        "observations": _build_observations(status, spooler_status),
        "collection_mode": "deep" if deep else "fast",
    }
    report["ai_analysis"] = bridge.analyze_report(report)

    if register_log:
        log_action(AllowedAction.GENERATE_REPORT.value, "success", f"Relatorio tecnico gerado com sucesso em modo {report['collection_mode']}.")

    return report
