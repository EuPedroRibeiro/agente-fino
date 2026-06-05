# MCP Brasil no Agente Fino

Integracao de dados publicos brasileiros no chat principal do Agente Fino.

## Estrutura

- Projeto original: opcional e mantido fora do repositorio de producao.
- Wrapper do Agente Fino: `modules/mcp_brasil`
- Endpoint de status: `/api/mcp-brasil/status`
- Painel tecnico opcional: `/mcp-brasil`

## Separacao dos projetos

O `mcp-brasil` original permanece preservado. O Agente Fino chama uma camada wrapper propria e nao mistura arquivos internos do projeto original no nucleo do chat.

O DarkForest continua separado como modulo sensivel de seguranca em `modules/darkforest`.

## Configuracao

```env
MCP_BRASIL_ENABLED=true
MCP_BRASIL_PATH=C:\caminho\externo\mcp-brasil
MCP_BRASIL_TRANSPORT=http
MCP_BRASIL_HOST=127.0.0.1
MCP_BRASIL_PORT=8766
MCP_BRASIL_AUTH_MODE=none
MCP_BRASIL_AUTO_START=true
MCP_BRASIL_TIMEOUT=60
MCP_BRASIL_ALLOWED_FEATURES=
MCP_BRASIL_DATASETS=
TRANSPARENCIA_API_KEY=
DATAJUD_API_KEY=
META_ACCESS_TOKEN=
```

As chaves sao opcionais e so sao usadas pelas fontes que exigirem credencial.

## Uso no chat

Exemplos:

- `/mcp status`
- `/mcp features`
- `/mcp brasilapi cep 27200-000`
- `/mcp ibge municipio Volta Redonda`
- `/mcp bacen selic`
- `Consulta o CEP 27200-000`
- `Me mostra informacoes do municipio de Volta Redonda pelo IBGE`
- `Qual a tendencia da Selic?`

## Servidor MCP original

Quando as dependencias estiverem instaladas, o servidor original pode rodar com:

```powershell
cd C:\caminho\externo\mcp-brasil
fastmcp run mcp_brasil.server:mcp --transport http --port 8766
```

O wrapper tambem possui `start_server()` e `stop_server()`, mas nao tenta instalar dependencias nem misturar ambientes automaticamente.

## Logs

Logs seguros ficam em `data/mcp_brasil/queries.jsonl`. Eles salvam apenas data, usuario, preview mascarado da mensagem, tool, status e tempo.
