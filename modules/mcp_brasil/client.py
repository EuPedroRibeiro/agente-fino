from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any


class MCPBrasilClient:
    def __init__(self, *, base_url: str, timeout: float = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self.get_json(f"{self.base_url}/health")

    def is_port_open(self, host: str, port: int, timeout: float = 0.35) -> bool:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except OSError:
            return False

    def get_json(self, url: str) -> dict[str, Any] | list[Any]:
        request = urllib.request.Request(url, headers={"User-Agent": "AgenteFino-MCPBrasil/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code} ao consultar fonte publica.") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falha de rede ao consultar fonte publica: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("Tempo limite ao consultar fonte publica.") from exc

    def brasilapi_cep(self, cep: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for url in (
            f"https://brasilapi.com.br/api/cep/v2/{cep}",
            f"https://brasilapi.com.br/api/cep/v1/{cep}",
            f"https://viacep.com.br/ws/{cep}/json/",
        ):
            try:
                data = dict(self.get_json(url))
                if str(data.get("erro", "")).lower() == "true":
                    continue
                data.setdefault("source_url", url)
                return data
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise RuntimeError("CEP nao encontrado nas fontes publicas consultadas.")

    def brasilapi_cnpj(self, cnpj: str) -> dict[str, Any]:
        return dict(self.get_json(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"))

    def ibge_municipios(self, nome: str) -> list[dict[str, Any]]:
        municipios = self.get_json("https://servicodados.ibge.gov.br/api/v1/localidades/municipios")
        normalized = _ascii_lower(nome)
        results: list[dict[str, Any]] = []
        for item in municipios if isinstance(municipios, list) else []:
            if normalized in _ascii_lower(str(item.get("nome", ""))):
                results.append(item)
        return results[:8]

    def bacen_serie(self, code: int, months: int = 12) -> list[dict[str, Any]]:
        end = date.today()
        start = end - timedelta(days=max(30, int(months) * 31))
        params = urllib.parse.urlencode(
            {
                "formato": "json",
                "dataInicial": start.strftime("%d/%m/%Y"),
                "dataFinal": end.strftime("%d/%m/%Y"),
            }
        )
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?{params}"
        data = self.get_json(url)
        return list(data[-36:] if isinstance(data, list) else [])


def _ascii_lower(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))
