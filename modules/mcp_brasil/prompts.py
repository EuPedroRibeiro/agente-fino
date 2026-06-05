from __future__ import annotations

from typing import Any


FEATURES = [
    "IBGE/localidades e indicadores municipais",
    "Banco Central/Bacen: Selic, IPCA, cambio e series SGS",
    "BrasilAPI: CEP, CNPJ, bancos, feriados e dados publicos simples",
    "Camara e Senado: deputados, senadores, proposicoes e votacoes",
    "Portal da Transparencia, TCU, compras publicas e PNCP",
    "DataSUS, ANVISA, educacao/INEP e seguranca publica quando habilitados",
]


def format_features() -> str:
    lines = "\n".join(f"- {feature}" for feature in FEATURES)
    return (
        "Consigo consultar dados publicos brasileiros via MCP Brasil quando o modulo estiver ativo.\n\n"
        f"{lines}\n\n"
        "Exemplos: `/mcp brasilapi cep 27200-000`, `/mcp ibge municipio Volta Redonda`, "
        "`/mcp bacen selic`."
    )


def format_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    if result.get("status") == "error":
        return str(result.get("message") or "Nao consegui concluir a consulta no MCP Brasil.")
    if tool_name == "brasilapi_cep":
        return _format_cep(result)
    if tool_name == "brasilapi_cnpj":
        return _format_cnpj(result)
    if tool_name == "ibge_municipio":
        return _format_ibge(result)
    if tool_name in {"bacen_selic", "bacen_ipca"}:
        return _format_bacen(tool_name, result)
    if tool_name == "listar_features":
        return format_features()
    if tool_name == "planejar_consulta":
        return _format_plan(result)
    return _format_generic(tool_name, result)


def _format_cep(data: dict[str, Any]) -> str:
    return (
        "Consultei fontes publicas via MCP Brasil/BrasilAPI.\n\n"
        f"CEP: {data.get('cep', '--')}\n"
        f"Logradouro: {data.get('street') or data.get('logradouro') or '--'}\n"
        f"Bairro: {data.get('neighborhood') or data.get('bairro') or '--'}\n"
        f"Cidade/UF: {data.get('city') or data.get('cidade') or '--'}/{data.get('state') or data.get('uf') or '--'}\n\n"
        "Quer que eu use esse endereco como base para outra consulta publica?"
    )


def _format_cnpj(data: dict[str, Any]) -> str:
    razao = data.get("razao_social") or data.get("nome") or data.get("name") or "--"
    cnpj = data.get("cnpj") or "--"
    cidade = data.get("municipio") or data.get("cidade") or "--"
    uf = data.get("uf") or "--"
    situacao = data.get("descricao_situacao_cadastral") or data.get("situacao_cadastral") or "--"
    return (
        "Consultei fontes publicas via MCP Brasil/BrasilAPI.\n\n"
        f"CNPJ: {cnpj}\n"
        f"Razao social: {razao}\n"
        f"Situacao cadastral: {situacao}\n"
        f"Municipio/UF: {cidade}/{uf}\n\n"
        "Dados cadastrais publicos podem mudar. Para decisao formal, confirme tambem na Receita Federal."
    )


def _format_ibge(data: dict[str, Any]) -> str:
    matches = data.get("matches") or []
    if not matches:
        return "Nao encontrei esse municipio nos dados publicos consultados pelo MCP Brasil/IBGE."
    first = matches[0]
    uf = (((first.get("microrregiao") or {}).get("mesorregiao") or {}).get("UF") or {})
    regiao = uf.get("regiao") or {}
    return (
        "Consultei dados publicos via MCP Brasil/IBGE.\n\n"
        f"Municipio encontrado: {first.get('nome', '--')}/{uf.get('sigla', '--')}\n"
        f"Codigo IBGE: {first.get('id', '--')}\n"
        f"Estado: {uf.get('nome', '--')}\n"
        f"Regiao: {regiao.get('nome', '--')}\n\n"
        "Posso consultar tambem populacao, indicadores, agregados estatisticos e comparacoes municipais quando a fonte estiver disponivel."
    )


def _format_bacen(tool_name: str, data: dict[str, Any]) -> str:
    serie = "Selic" if tool_name == "bacen_selic" else "IPCA"
    rows = data.get("rows") or []
    if not rows:
        return f"Nao recebi dados recentes de {serie} pela consulta publica do Banco Central."
    last = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    trend = ""
    if previous:
        try:
            current_value = float(str(last.get("valor", "0")).replace(",", "."))
            previous_value = float(str(previous.get("valor", "0")).replace(",", "."))
            if current_value > previous_value:
                trend = "Tendencia recente: alta em relacao ao dado anterior."
            elif current_value < previous_value:
                trend = "Tendencia recente: queda em relacao ao dado anterior."
            else:
                trend = "Tendencia recente: estabilidade em relacao ao dado anterior."
        except ValueError:
            trend = "Tendencia recente: nao consegui comparar numericamente."
    return (
        f"Consultei dados publicos via MCP Brasil/Banco Central.\n\n"
        f"Serie: {serie}\n"
        f"Ultimo dado retornado: {last.get('data', '--')} - {last.get('valor', '--')}\n"
        f"Amostras analisadas: {len(rows)}\n"
        f"{trend}\n\n"
        "Posso montar uma tabela comparando os ultimos meses se voce quiser."
    )


def _format_plan(data: dict[str, Any]) -> str:
    steps = data.get("steps") or []
    rendered = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(steps))
    return "Plano MCP Brasil para consulta publica:\n\n" + rendered


def _format_generic(tool_name: str, data: dict[str, Any]) -> str:
    preview = data.get("summary") or data.get("message") or str(data)[:1200]
    return f"Com base no MCP Brasil usando `{tool_name}`:\n\n{preview}"
