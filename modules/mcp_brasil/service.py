from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.core.runtime import is_cloud

from .client import MCPBrasilClient
from .prompts import FEATURES, format_features, format_tool_result
from .router import MCPBrasilPlan, MCPBrasilRouter


_PROCESS: subprocess.Popen | None = None


@dataclass
class MCPBrasilConfig:
    enabled: bool
    path: str
    transport: str
    host: str
    port: int
    auth_mode: str
    auto_start: bool
    timeout: int
    allowed_features: str = ""
    datasets: str = ""

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def mcp_url(self) -> str:
        return f"{self.url}/mcp"


class MCPBrasilService:
    def __init__(self, config: MCPBrasilConfig | None = None, client: MCPBrasilClient | None = None) -> None:
        self.config = config or MCPBrasilConfig(
            enabled=settings.mcp_brasil_enabled,
            path=settings.mcp_brasil_path,
            transport=settings.mcp_brasil_transport,
            host=settings.mcp_brasil_host,
            port=settings.mcp_brasil_port,
            auth_mode=settings.mcp_brasil_auth_mode,
            auto_start=settings.mcp_brasil_auto_start,
            timeout=settings.mcp_brasil_timeout,
            allowed_features=settings.mcp_brasil_allowed_features,
            datasets=settings.mcp_brasil_datasets,
        )
        self.client = client or MCPBrasilClient(base_url=self.config.url, timeout=min(30, self.config.timeout))
        self.last_error: str | None = None

    def is_enabled(self) -> bool:
        return bool(self.config.enabled)

    def status(self) -> dict[str, Any]:
        path = Path(self.config.path)
        installed = path.exists()
        running = self.client.is_port_open(self.config.host, self.config.port)
        health = None
        if running:
            try:
                health = self.client.health()
            except Exception as exc:
                self.last_error = mask_secrets(str(exc))
        return {
            "enabled": self.config.enabled,
            "installed": installed,
            "available": bool(self.config.enabled),
            "running": running,
            "transport": self.config.transport,
            "url": self.config.mcp_url,
            "health_url": f"{self.config.url}/health",
            "features_available": bool(self.config.enabled),
            "chat_active": bool(self.config.enabled),
            "external_server_available": installed,
            "direct_adapters": ["brasilapi_cep", "brasilapi_cnpj", "ibge_municipio", "bacen_selic", "bacen_ipca"],
            "features_count": len(FEATURES),
            "last_error": self.last_error,
            "health": health,
        }

    def start_server(self) -> dict[str, Any]:
        global _PROCESS
        if not self.config.enabled:
            return {"status": "disabled", "message": "MCP Brasil desativado por configuracao."}
        if is_cloud():
            return {"status": "skipped", "message": "Runtime cloud nao inicia processo local. Use o servidor externo ou adaptadores diretos."}
        if self.client.is_port_open(self.config.host, self.config.port):
            return {"status": "running", "url": self.config.mcp_url}
        path = Path(self.config.path)
        if not path.exists():
            self.last_error = f"Projeto mcp-brasil nao encontrado em {self.config.path}."
            return {"status": "missing", "message": self.last_error}
        fastmcp = self._find_fastmcp(path)
        if not fastmcp:
            self.last_error = "fastmcp nao encontrado. Instale as dependencias no projeto externo configurado ou no PATH."
            return {"status": "missing_dependency", "message": self.last_error}
        env = os.environ.copy()
        env["PYTHONPATH"] = str(path / "src")
        env["MCP_BRASIL_AUTH_MODE"] = self.config.auth_mode
        env["MCP_BRASIL_DATASETS"] = self.config.datasets
        command = [
            fastmcp,
            "run",
            "mcp_brasil.server:mcp",
            "--transport",
            self.config.transport,
            "--port",
            str(self.config.port),
        ]
        _PROCESS = subprocess.Popen(
            command,
            cwd=str(path),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(1.2)
        running = self.client.is_port_open(self.config.host, self.config.port)
        return {"status": "running" if running else "starting", "pid": _PROCESS.pid if _PROCESS else None, "url": self.config.mcp_url}

    def stop_server(self) -> dict[str, Any]:
        global _PROCESS
        if _PROCESS and _PROCESS.poll() is None:
            _PROCESS.terminate()
            _PROCESS = None
            return {"status": "stopped"}
        return {"status": "not_started_by_agente_fino"}

    def ensure_running(self) -> dict[str, Any]:
        status = self.status()
        if status["running"] or not self.config.auto_start:
            return status
        started = self.start_server()
        refreshed = self.status()
        refreshed["start_attempt"] = started
        return refreshed

    def list_features(self) -> dict[str, Any]:
        return {"status": "ok", "features": FEATURES, "text": format_features()}

    def recommend_tools(self, user_message: str) -> dict[str, Any]:
        plan = MCPBrasilRouter.plan_query(user_message)
        return {"status": "ok", "plan": asdict(plan), "recommended_tool": plan.tool_name}

    def plan_query(self, user_message: str) -> MCPBrasilPlan:
        return MCPBrasilRouter.plan_query(user_message)

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        started = time.perf_counter()
        try:
            if tool_name == "status":
                result = self.status()
            elif tool_name == "listar_features":
                result = self.list_features()
            elif tool_name == "recomendar_tools":
                result = self.recommend_tools(str(args.get("query") or ""))
            elif tool_name == "planejar_consulta":
                result = self._manual_plan(str(args.get("query") or ""))
            elif tool_name == "brasilapi_cep":
                result = self.client.brasilapi_cep(str(args["cep"]))
            elif tool_name == "brasilapi_cnpj":
                result = self.client.brasilapi_cnpj(str(args["cnpj"]))
            elif tool_name == "ibge_municipio":
                result = {"matches": self.client.ibge_municipios(str(args.get("municipio") or ""))}
            elif tool_name == "bacen_selic":
                result = {"rows": self.client.bacen_serie(432, int(args.get("months") or 12))}
            elif tool_name == "bacen_ipca":
                result = {"rows": self.client.bacen_serie(433, int(args.get("months") or 12))}
            else:
                result = {
                    "status": "unsupported_tool",
                    "message": f"A tool `{tool_name}` ainda nao tem adaptador direto no Agente Fino. Use `/mcp features` para ver opcoes.",
                }
            status = "ok" if result.get("status") not in {"error", "unsupported_tool"} else result.get("status")
            return {"status": status, "tool": tool_name, "arguments": args, "result": result, "latency_ms": int((time.perf_counter() - started) * 1000)}
        except Exception as exc:
            error = mask_secrets(str(exc))
            self.last_error = error
            return {"status": "error", "tool": tool_name, "arguments": args, "message": error, "latency_ms": int((time.perf_counter() - started) * 1000)}

    def ask(self, user_message: str, *, user: str = "local-user") -> dict[str, Any]:
        started = time.perf_counter()
        if not self.config.enabled:
            answer = "O modulo MCP Brasil esta desativado por configuracao."
            return self._response(user_message, MCPBrasilPlan("disabled"), None, answer, started, "disabled")
        plan = self.plan_query(user_message)
        self._log(user=user, message=user_message, tool=plan.tool_name, status="planned")
        if plan.tool_name == "status":
            status = self.status()
            answer = (
                "MCP Brasil esta disponivel no Agente Fino.\n\n"
                f"Servidor HTTP: {'online' if status['running'] else 'offline'}\n"
                f"Projeto externo local: {'disponivel' if status['external_server_available'] else 'isolado do pacote de producao'}\n"
                f"URL MCP: {status['url']}\n"
                f"Chat ativo: {'sim' if status['chat_active'] else 'nao'}\n"
                f"Adaptadores gratuitos: {', '.join(status['direct_adapters'])}"
            )
            return self._response(user_message, plan, {"status": "ok", "result": status, "tool": "status", "latency_ms": 0}, answer, started)
        tool_call = self.call_tool(plan.tool_name or "recomendar_tools", plan.arguments)
        if tool_call["status"] == "error":
            answer = (
                "O modulo MCP Brasil esta instalado, mas nao consegui acessar a fonte publica agora. "
                "Verifique conexao, porta configurada ou disponibilidade da API publica.\n\n"
                f"Erro: {tool_call.get('message')}"
            )
        else:
            answer = format_tool_result(tool_call["tool"], tool_call.get("result") or {})
        self._log(user=user, message=user_message, tool=tool_call.get("tool"), status=tool_call.get("status"), latency_ms=tool_call.get("latency_ms"))
        return self._response(user_message, plan, tool_call, answer, started)

    def _response(self, user_message: str, plan: MCPBrasilPlan, tool_call: dict[str, Any] | None, answer: str, started: float, status: str = "ok") -> dict[str, Any]:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "status": status,
            "answer": answer,
            "intent": plan.intent,
            "tool": plan.tool_name,
            "arguments": plan.arguments,
            "tool_call": tool_call,
            "latency_ms": latency_ms,
            "web_used": True,
            "source": "MCP Brasil",
        }

    def _manual_plan(self, query: str) -> dict[str, Any]:
        plan = MCPBrasilRouter.plan_query(query)
        steps = [
            "Identificar a fonte publica brasileira adequada.",
            f"Usar a tool recomendada: {plan.tool_name or 'recomendar_tools'}.",
            "Conferir se a resposta retornou dados suficientes.",
            "Responder com fonte, limite e proximos passos.",
        ]
        return {"status": "ok", "query": query, "steps": steps, "plan": asdict(plan)}

    def _find_fastmcp(self, path: Path) -> str | None:
        candidates = [
            path / ".venv" / "Scripts" / "fastmcp.exe",
            path / ".venv" / "bin" / "fastmcp",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return shutil.which("fastmcp")

    def _log(self, *, user: str, message: str, tool: str | None, status: str | None, latency_ms: int | None = None) -> None:
        try:
            log_dir = Path("data/mcp_brasil")
            log_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "user": user,
                "message_preview": mask_secrets((message or "")[:240]),
                "tool": tool,
                "status": status,
                "latency_ms": latency_ms,
            }
            with (log_dir / "queries.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
