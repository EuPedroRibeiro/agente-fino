from __future__ import annotations

import importlib
import importlib.util
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.agent.public_data_router import PublicDataPlan
from app.agent.security.sanitizer import mask_secrets
from app.core.config import settings
from app.security.documents import mask_cnpj, mask_cpf, sanitize_document_payload


class PublicDataError(RuntimeError):
    pass


class PublicDataProvider:
    name = "DadosAbertosBrasil/PublicDataProvider"
    CAMARA_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
    LIBRARY_TOOLS = {
        "camara_deputies",
        "camara_deputy_expenses",
        "camara_parties",
        "camara_propositions",
        "camara_votes",
        "senate_members",
        "bacen_series",
        "ibge_population",
        "ipea_series",
    }

    def __init__(self) -> None:
        self.last_library_error: str | None = None

    def status(self) -> dict[str, Any]:
        library_installed = importlib.util.find_spec("DadosAbertosBrasil") is not None
        return {
            "name": self.name,
            "enabled": settings.public_data_enabled,
            "active": settings.public_data_enabled,
            "available": settings.public_data_enabled,
            "requires_api_key": False,
            "library_installed": library_installed,
            "mode": "library_with_direct_fallback" if library_installed else "direct_official_adapters",
            "timeout_seconds": settings.public_data_timeout_seconds,
            "sources": ["Camara", "Senado", "BACEN", "IBGE", "IPEA", "UF"],
            "supports_free_cpf_lookup": False,
            "last_library_error": self.last_library_error,
        }

    def query(self, plan: PublicDataPlan) -> dict[str, Any]:
        if not settings.public_data_enabled:
            raise PublicDataError("A integracao de dados publicos esta desativada.")
        if plan.tool_name in self.LIBRARY_TOOLS and importlib.util.find_spec("DadosAbertosBrasil") is not None:
            try:
                return sanitize_public_data(self._query_library(plan))
            except Exception as exc:
                self.last_library_error = mask_secrets(str(exc))
        tool = plan.tool_name
        args = plan.arguments
        if tool == "camara_deputies":
            return self._camara_deputies(args.get("name"))
        if tool == "camara_deputy_expenses":
            return self._camara_deputy_expenses(args.get("deputy_name"), args.get("supplier"))
        if tool == "camara_parties":
            return self._camara_collection("partidos", {"itens": 10, "ordem": "ASC", "ordenarPor": "sigla"})
        if tool == "camara_propositions":
            params = {"itens": 10, "ordem": "DESC", "ordenarPor": "id"}
            if args.get("keyword"):
                params["keywords"] = args["keyword"]
            return self._camara_collection("proposicoes", params)
        if tool == "camara_votes":
            return self._camara_collection("votacoes", {"itens": 10, "ordem": "DESC", "ordenarPor": "dataHoraRegistro"})
        if tool == "senate_members":
            return self._senate_members(args.get("name"))
        if tool == "bacen_series":
            return self._bacen_series(args.get("code"))
        if tool == "ibge_population":
            return self._get_json("https://servicodados.ibge.gov.br/api/v1/projecoes/populacao")
        if tool == "ipea_series":
            query = args.get("query")
            params = {"$top": 10}
            if query:
                escaped_query = str(query).replace("'", "''")
                params["$filter"] = f"contains(SERNOME,'{escaped_query}')"
            return self._get_json(f"http://www.ipeadata.gov.br/api/odata4/Metadados?{urllib.parse.urlencode(params)}")
        if tool == "uf_data":
            uf = str(args.get("uf") or "").upper()
            if not re_fullmatch_uf(uf):
                raise PublicDataError("Informe a sigla da UF, por exemplo: RJ, SP ou MG.")
            return self._get_json(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}")
        if tool == "public_data_help":
            return {"status": "ok", "sources": self.status()["sources"]}
        raise PublicDataError("Essa consulta publica ainda nao possui adaptador.")

    def _query_library(self, plan: PublicDataPlan) -> Any:
        dab = importlib.import_module("DadosAbertosBrasil")
        tool = plan.tool_name
        args = plan.arguments
        if tool == "camara_deputies":
            return dab.camara.lista_deputados(nome=args.get("name"), itens=10, formato="json")
        if tool == "camara_deputy_expenses":
            name = args.get("deputy_name")
            if not name:
                raise PublicDataError("Informe o nome do deputado para consultar despesas parlamentares.")
            deputies = _rows(dab.camara.lista_deputados(nome=name, itens=5, formato="json"))
            if not deputies:
                raise PublicDataError(f"Nao encontrei deputado com o nome {name}.")
            deputy = deputies[0]
            supplier = args.get("supplier")
            expenses = dab.camara.Deputado(int(deputy["id"])).despesas(
                fornecedor=int(supplier) if supplier else None,
                itens=10,
                formato="json",
            )
            return {"deputy": deputy, "expenses": _rows(expenses)}
        if tool == "camara_parties":
            return dab.camara.lista_partidos(itens=10, formato="json")
        if tool == "camara_propositions":
            return dab.camara.lista_proposicoes(keyword=args.get("keyword"), itens=10, formato="json")
        if tool == "camara_votes":
            return dab.camara.lista_votacoes(itens=10, formato="json")
        if tool == "senate_members":
            return dab.senado.lista_senadores(contendo=args.get("name"), formato="json")
        if tool == "bacen_series":
            code = args.get("code")
            if not code:
                raise PublicDataError("Informe o codigo da serie do Banco Central, ou peca especificamente a Selic.")
            return dab.bacen.serie(int(code), ultimos=12, formato="json")
        if tool == "ibge_population":
            return dab.ibge.populacao()
        if tool == "ipea_series":
            return dab.ipea.lista_series(contendo=args.get("query"), formato="json")
        raise PublicDataError("Consulta nao suportada diretamente pela biblioteca; usando fonte oficial.")

    def _camara_deputies(self, name: str | None) -> dict[str, Any] | list[Any]:
        params: dict[str, Any] = {"itens": 10, "ordem": "ASC", "ordenarPor": "nome"}
        if name:
            params["nome"] = name
        return self._camara_collection("deputados", params)

    def _camara_deputy_expenses(self, deputy_name: str | None, supplier: str | None) -> dict[str, Any]:
        if not deputy_name:
            raise PublicDataError("Informe o nome do deputado para consultar despesas parlamentares.")
        deputies = _rows(self._camara_deputies(deputy_name))
        if not deputies:
            raise PublicDataError(f"Nao encontrei deputado com o nome {deputy_name}.")
        deputy = deputies[0]
        deputy_id = deputy.get("id")
        params: dict[str, Any] = {"itens": 10, "ordem": "DESC", "ordenarPor": "dataDocumento"}
        if supplier:
            params["cnpjCpfFornecedor"] = supplier
        result = self._camara_collection(f"deputados/{deputy_id}/despesas", params)
        return {"deputy": deputy, "expenses": _rows(result)}

    def _camara_collection(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        url = f"{self.CAMARA_BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
        return self._get_json(url)

    def _senate_members(self, name: str | None) -> dict[str, Any]:
        data = self._get_json("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json")
        if not name:
            return data
        normalized = _normalize(name)
        members = _find_nested_records(data, {"NomeParlamentar", "NomeCompletoParlamentar"})
        filtered = [row for row in members if normalized in _normalize(str(row))]
        return {"members": filtered[:10]}

    def _bacen_series(self, code: int | None) -> list[Any]:
        if not code:
            raise PublicDataError("Informe o codigo da serie do Banco Central, ou peca especificamente a Selic.")
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{int(code)}/dados/ultimos/12?formato=json"
        data = self._get_json(url)
        return list(data) if isinstance(data, list) else []

    def _get_json(self, url: str) -> dict[str, Any] | list[Any]:
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AgenteFino-PublicData/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=settings.public_data_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
        except urllib.error.HTTPError as exc:
            raise PublicDataError(f"A fonte publica retornou HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise PublicDataError("Nao foi possivel conectar a fonte publica agora.") from exc
        except TimeoutError as exc:
            raise PublicDataError("A consulta de dados publicos excedeu o tempo limite.") from exc
        except json.JSONDecodeError as exc:
            raise PublicDataError("A fonte publica retornou uma resposta invalida.") from exc
        except Exception as exc:
            raise PublicDataError(mask_secrets(f"Falha ao consultar dados publicos: {exc}")) from exc
        return sanitize_public_data(payload)


def sanitize_public_data(value: Any, key: str = "") -> Any:
    normalized_key = _normalize(key)
    if isinstance(value, dict):
        return {str(item_key): sanitize_public_data(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_public_data(item, key) for item in value[:50]]
    if isinstance(value, tuple):
        return tuple(sanitize_public_data(item, key) for item in value[:50])
    if value is None:
        return None
    text = str(value)
    digits = "".join(char for char in text if char.isdigit())
    if "cpf" in normalized_key and len(digits) == 11:
        return mask_cpf(digits)
    if "cnpj" in normalized_key and len(digits) == 14:
        return mask_cnpj(digits)
    return sanitize_document_payload(value)


def _rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("dados", "value", "rows", "members"):
        items = data.get(key)
        if isinstance(items, list):
            return [dict(item) for item in items if isinstance(item, dict)]
    return []


def _find_nested_records(value: Any, expected_keys: set[str]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if expected_keys.intersection(value):
            found.append(value)
        for item in value.values():
            found.extend(_find_nested_records(item, expected_keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_nested_records(item, expected_keys))
    return found


def _normalize(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", (value or "").lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def re_fullmatch_uf(value: str) -> bool:
    return bool(len(value) == 2 and value.isalpha())
