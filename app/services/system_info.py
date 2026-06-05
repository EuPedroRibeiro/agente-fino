from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # Cloud runtime does not require local diagnostic dependencies.
    psutil = None

from app.core.config import settings
from app.core.production import production_readiness
from app.core.runtime import is_cloud
from app.core.security import is_windows
from app.db import get_database_status


UNAVAILABLE = "indisponível"
IDLE_PROCESS_NAMES = {"system idle process", "idle"}


def _format_uptime(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def _gb(value: int | float) -> float:
    return round(float(value) / (1024**3), 2)


def _round_percent(value: int | float) -> float:
    return round(max(0.0, float(value)), 2)


def _listify(data: Any) -> list[Any]:
    if data in (None, ""):
        return []
    if isinstance(data, list):
        return data
    return [data]


def _run_powershell_json(script: str, timeout: int = 15) -> Any:
    if not is_windows():
        return None

    command = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        f"{script}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def get_local_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except OSError:
            return None


def get_disk_usage() -> dict[str, Any]:
    if psutil is None:
        return {"status": "disabled_in_cloud", "message": "Diagnostico local indisponivel no runtime cloud."}
    root = Path(os.getenv("SystemDrive", "C:") + "\\") if is_windows() else Path("/")
    try:
        usage = psutil.disk_usage(str(root))
    except OSError:
        return {
            "path": str(root),
            "total_gb": UNAVAILABLE,
            "used_gb": UNAVAILABLE,
            "free_gb": UNAVAILABLE,
            "percent": 0.0,
            "status": UNAVAILABLE,
        }

    return {
        "path": str(root),
        "total_gb": _gb(usage.total),
        "used_gb": _gb(usage.used),
        "free_gb": _gb(usage.free),
        "percent": usage.percent,
    }


def get_disk_partitions() -> list[dict[str, Any]] | str:
    if psutil is None:
        return UNAVAILABLE
    try:
        partitions = psutil.disk_partitions(all=False)
    except (OSError, psutil.Error):
        return UNAVAILABLE

    details: list[dict[str, Any]] = []
    for partition in partitions:
        item: dict[str, Any] = {
            "device": partition.device or UNAVAILABLE,
            "mountpoint": partition.mountpoint or UNAVAILABLE,
            "filesystem": partition.fstype or UNAVAILABLE,
            "opts": partition.opts or UNAVAILABLE,
        }
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            item.update(
                {
                    "total_gb": _gb(usage.total),
                    "used_gb": _gb(usage.used),
                    "free_gb": _gb(usage.free),
                    "percent": usage.percent,
                }
            )
        except (OSError, PermissionError):
            item.update({"usage": UNAVAILABLE})
        details.append(item)

    return details


def get_memory_info() -> dict[str, Any]:
    if psutil is None:
        return {"status": "disabled_in_cloud", "message": "RAM local indisponivel no runtime cloud."}
    try:
        memory = psutil.virtual_memory()
    except psutil.Error:
        return {
            "total_gb": UNAVAILABLE,
            "available_gb": UNAVAILABLE,
            "used_gb": UNAVAILABLE,
            "percent": 0.0,
            "status": UNAVAILABLE,
        }

    return {
        "total_gb": _gb(memory.total),
        "available_gb": _gb(memory.available),
        "used_gb": _gb(memory.used),
        "percent": memory.percent,
    }


def get_cpu_info() -> dict[str, Any]:
    if psutil is None:
        return {"status": "disabled_in_cloud", "message": "CPU local indisponivel no runtime cloud."}
    try:
        psutil.cpu_percent(interval=None)
        per_core = psutil.cpu_percent(interval=settings.cpu_measure_interval_seconds, percpu=True)
        percent = sum(per_core) / len(per_core) if per_core else psutil.cpu_percent(interval=0.1)
    except psutil.Error:
        return {
            "percent": 0.0,
            "status": UNAVAILABLE,
            "measurement_interval_seconds": settings.cpu_measure_interval_seconds,
        }

    return {
        "percent": round(percent, 1),
        "physical_cores": psutil.cpu_count(logical=False) or UNAVAILABLE,
        "logical_cores": psutil.cpu_count(logical=True) or UNAVAILABLE,
        "per_core_percent": [round(value, 1) for value in per_core],
        "measurement_interval_seconds": settings.cpu_measure_interval_seconds,
    }


def get_machine_details() -> dict[str, Any]:
    processor = platform.processor() or os.getenv("PROCESSOR_IDENTIFIER") or UNAVAILABLE
    architecture_bits = platform.architecture()[0] or UNAVAILABLE
    machine = platform.machine() or UNAVAILABLE
    return {
        "processor": processor,
        "architecture": {
            "machine": machine,
            "bits": architecture_bits,
        },
        "python_version": sys.version.split()[0],
    }


def get_system_status() -> dict[str, Any]:
    if is_cloud():
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "status": "online",
            "runtime": "cloud",
            "message": "Metricas do computador local ficam indisponiveis no Agente Fino Cloud.",
        }
    boot_time = psutil.boot_time()
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "platform": platform.platform(),
        "uptime": _format_uptime(time.time() - boot_time),
        "boot_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot_time)),
        "local_ip": get_local_ip(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_usage(),
        "machine": get_machine_details(),
    }


def _is_useful_process(pid: int | None, name: str | None) -> bool:
    if not pid or pid == 0:
        return False
    clean_name = (name or "").strip()
    if not clean_name:
        return False
    return clean_name.lower() not in IDLE_PROCESS_NAMES


def get_processes(limit: int | None = None) -> list[dict[str, Any]]:
    if is_cloud():
        return []
    if psutil is None:
        return []
    process_limit = limit or settings.process_limit
    logical_cores = psutil.cpu_count(logical=True) or 1
    candidates: list[psutil.Process] = []

    for process in psutil.process_iter(["pid", "name"]):
        try:
            info = process.info
            if not _is_useful_process(info.get("pid"), info.get("name")):
                continue
            process.cpu_percent(interval=None)
            candidates.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.Error):
            continue

    if candidates:
        time.sleep(settings.process_measure_interval_seconds)

    processes: list[dict[str, Any]] = []
    for process in candidates:
        try:
            name = process.name()
            pid = process.pid
            if not _is_useful_process(pid, name):
                continue
            raw_cpu = _round_percent(process.cpu_percent(interval=None))
            # psutil pode retornar acima de 100 para processos usando varios nucleos.
            # Para exibicao tecnica, normalizamos para uma escala 0-100 e mantemos o valor bruto.
            normalized_cpu = min(100.0, raw_cpu / logical_cores)
            processes.append(
                {
                    "pid": pid,
                    "name": name,
                    "cpu_percent": round(normalized_cpu, 2),
                    "raw_cpu_percent": raw_cpu,
                    "memory_percent": round(float(process.memory_percent() or 0), 2),
                    "cpu_normalized": True,
                    "normalization_note": "cpu_percent normalizado por nucleos logicos; raw_cpu_percent preserva o valor bruto do psutil.",
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.Error, PermissionError):
            continue

    processes.sort(key=lambda item: (item["cpu_percent"], item["memory_percent"]), reverse=True)
    return processes[:process_limit]


def get_service_status(service_name: str) -> dict[str, Any]:
    if not is_windows():
        return {
            "service": service_name,
            "status": "unsupported",
            "message": "Consulta de servico disponivel apenas no Windows.",
        }

    try:
        result = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True,
            encoding="oem",
            errors="replace",
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"service": service_name, "status": "error", "message": str(exc)}

    output = f"{result.stdout}\n{result.stderr}".strip()
    normalized = output.upper()
    if result.returncode != 0:
        return {"service": service_name, "status": "error", "message": output or "Servico nao encontrado."}
    if "RUNNING" in normalized:
        status = "running"
    elif "STOPPED" in normalized:
        status = "stopped"
    elif "START_PENDING" in normalized:
        status = "starting"
    elif "STOP_PENDING" in normalized:
        status = "stopping"
    else:
        status = "unknown"

    return {"service": service_name, "status": status, "message": f"Servico {service_name} esta com status {status}."}


def get_network_adapters() -> list[dict[str, Any]] | str:
    if psutil is None:
        return UNAVAILABLE
    try:
        addresses = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
    except psutil.Error:
        return UNAVAILABLE

    adapters: list[dict[str, Any]] = []
    link_family = getattr(psutil, "AF_LINK", None)
    for name, entries in addresses.items():
        stat = stats.get(name)
        adapter = {
            "name": name,
            "is_up": stat.isup if stat else UNAVAILABLE,
            "speed_mbps": stat.speed if stat else UNAVAILABLE,
            "mac": UNAVAILABLE,
            "ipv4": [],
            "ipv6": [],
        }
        for entry in entries:
            if entry.family == socket.AF_INET:
                adapter["ipv4"].append({"address": entry.address, "netmask": entry.netmask or UNAVAILABLE})
            elif entry.family == socket.AF_INET6:
                adapter["ipv6"].append({"address": entry.address, "netmask": entry.netmask or UNAVAILABLE})
            elif link_family is not None and entry.family == link_family:
                adapter["mac"] = entry.address or UNAVAILABLE
        adapters.append(adapter)

    return adapters


def get_network_configuration() -> dict[str, Any]:
    script = """
    Get-NetIPConfiguration |
      ForEach-Object {
        [PSCustomObject]@{
          interface = $_.InterfaceAlias
          ipv4 = @($_.IPv4Address | ForEach-Object { $_.IPAddress })
          gateway = @($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })
          dns = @($_.DNSServer.ServerAddresses)
        }
      } | ConvertTo-Json -Depth 4
    """
    data = _run_powershell_json(script)
    if data is None:
        return {"gateway": UNAVAILABLE, "dns": UNAVAILABLE, "interfaces": []}

    interfaces = _listify(data)
    gateways: list[str] = []
    dns_servers: list[str] = []
    normalized: list[dict[str, Any]] = []
    for item in interfaces:
        gateway_values = [value for value in _listify(item.get("gateway")) if value]
        dns_values = [value for value in _listify(item.get("dns")) if value]
        gateways.extend(gateway_values)
        dns_servers.extend(dns_values)
        normalized.append(
            {
                "interface": item.get("interface") or UNAVAILABLE,
                "ipv4": _listify(item.get("ipv4")),
                "gateway": gateway_values or UNAVAILABLE,
                "dns": dns_values or UNAVAILABLE,
            }
        )

    unique_gateways = sorted(set(gateways))
    unique_dns = sorted(set(dns_servers))
    return {
        "gateway": unique_gateways or UNAVAILABLE,
        "dns": unique_dns or UNAVAILABLE,
        "interfaces": normalized,
    }


def get_installed_printers() -> list[dict[str, Any]] | str:
    script = """
    $printers = @(Get-CimInstance Win32_Printer |
      Select-Object Name,Default,WorkOffline,PrinterStatus,DriverName,PortName)
    $printers | ConvertTo-Json -Depth 3
    """
    data = _run_powershell_json(script)
    if data is None:
        return UNAVAILABLE

    printers: list[dict[str, Any]] = []
    for item in _listify(data):
        printers.append(
            {
                "name": item.get("Name") or UNAVAILABLE,
                "default": bool(item.get("Default")),
                "work_offline": bool(item.get("WorkOffline")),
                "status": item.get("PrinterStatus", UNAVAILABLE),
                "driver": item.get("DriverName") or UNAVAILABLE,
                "port": item.get("PortName") or UNAVAILABLE,
            }
        )
    return printers


def get_recent_windows_critical_errors(limit: int = 5) -> list[dict[str, Any]] | str:
    script = f"""
    Get-WinEvent -FilterHashtable @{{LogName='System'; Level=1,2; StartTime=(Get-Date).AddDays(-7)}} -MaxEvents {limit} -ErrorAction Stop |
      Select-Object @{{Name='TimeCreated';Expression={{$_.TimeCreated.ToString('yyyy-MM-ddTHH:mm:ss')}}}},Id,ProviderName,LevelDisplayName,@{{Name='Message';Expression={{$_.Message.Substring(0, [Math]::Min($_.Message.Length, 500))}}}} |
      ConvertTo-Json -Depth 3
    """
    data = _run_powershell_json(script, timeout=20)
    if data is None:
        return UNAVAILABLE

    events: list[dict[str, Any]] = []
    for item in _listify(data):
        events.append(
            {
                "time_created": item.get("TimeCreated") or UNAVAILABLE,
                "event_id": item.get("Id", UNAVAILABLE),
                "provider": item.get("ProviderName") or UNAVAILABLE,
                "level": item.get("LevelDisplayName") or UNAVAILABLE,
                "message": item.get("Message") or UNAVAILABLE,
            }
        )
    return events


def get_health_payload() -> dict[str, Any]:
    readiness = production_readiness()
    db_status = get_database_status()
    return {
        "status": readiness.status,
        "product": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runtime": "cloud" if is_cloud() else "local_legacy",
        "local_only": not is_cloud(),
        "storage_status": {
            "engine": db_status.engine,
            "configured": db_status.configured,
            "persistent": db_status.persistent,
        },
        "configuration_errors": readiness.errors,
        "configuration_warnings": readiness.warnings,
    }
