# NexusTI AI - Nexus Core 3.4

NexusTI AI e uma plataforma local para diagnostico tecnico em Windows. A versao **3.4.1** transforma o Nexus Core em um agente hibrido: **Gemini** como inteligencia principal online, **Ollama qwen2.5:3b** como fallback local e `local-rules` apenas como emergencia.

## Rodar

```powershell
pip install -r requirements.txt
python main.py
```

Acesse:

```text
http://127.0.0.1:8765/login
http://127.0.0.1:8765/agent
```

O dashboard classico continua em:

```text
http://127.0.0.1:8765
```

## O que existe no Nexus Core 3.4

- Grafo proprio em `app/agent/graph.py`
- Estado Pydantic em `app/agent/state.py`
- Roteamento rapido para conversa simples, hora, data, calculo e metricas do PC
- Analise local do PC em modo rapido para o chat
- RAG local em SQLite com base inicial tecnica
- Memoria de conversas e casos
- Pesquisa web read-only com SearxNG opcional e DuckDuckGo/Bing HTML fallback
- Cache web em SQLite
- Citacoes com fonte, dominio, confiabilidade e status de leitura
- Especialistas internos de Windows, impressora, rede, hardware, performance, seguranca e pesquisa web
- Registry de ferramentas allowlist
- Safety checker bloqueando comando livre e execucao de scripts da internet
- Critico e hallucination guard
- Providers: Gemini, Ollama, OpenAI Responses API, OpenAI-compatible e fallback local rules
- Gemini via `GEMINI_API_KEY`, sem chave hardcoded
- Roteamento estruturado por JSON para selecionar ferramentas locais quando o provider principal esta online
- Fallback automatico Gemini -> Ollama -> local-rules
- Deteccao real do Ollama via `GET /api/tags` e chat via `POST /api/chat`
- `local-rules` usado somente como fallback quando o provider real falha
- Ferramenta `disk_usage` somente leitura com ranking das maiores pastas
- Catalogo de IA com providers, bancos/RAG, buscas web e capacidades futuras
- Observabilidade local em `agent_runs` e `agent_model_calls`

## Rotas principais

- `GET /agent` - interface do Nexus Core
- `GET /api/agent/status` - status de web, RAG, memoria, provider e ferramentas
- `GET /api/agent/providers/status` - status real de OpenAI, OpenAI-compatible, Ollama, LiteLLM e fallback
- `GET /api/agent/catalog` - catalogo de providers, bancos/RAG, busca web e capacidades
- `POST /api/agent/chat` - conversa com o agente
- `POST /api/agent/tools/disk-usage` - ranking somente leitura das pastas que mais ocupam disco
- `POST /api/agent/research` - pesquisa web com fontes
- `POST /api/agent/deep-research` - pesquisa tecnica profunda
- `POST /api/agent/analyze-pc` - gera relatorio local e analisa
- `POST /api/agent/confirm-action` - confirma uma acao pendente
- `GET /api/agent/memory` - lista memoria
- `POST /api/agent/memory/search` - busca memoria
- `DELETE /api/agent/memory/{id}` - remove memoria
- `GET /api/agent/sources` - historico de fontes pesquisadas

## Web

Configuracao no `.env.example`:

```text
NEXUSTI_WEB_ENABLED=true
NEXUSTI_SEARXNG_URL=
NEXUSTI_WEB_MAX_RESULTS=8
NEXUSTI_WEB_MAX_PAGES_FETCH=5
```

Se `NEXUSTI_SEARXNG_URL` existir, o agente usa SearxNG. Sem SearxNG, tenta busca HTML. A web e somente leitura: o Nexus Core nunca executa scripts, instaladores ou comandos vindos da internet.

## Modelos

Configuracao recomendada:

```text
DEFAULT_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
LOCAL_RULES_ONLY_FALLBACK=true
```

Ordem principal:

1. Gemini, se `GEMINI_API_KEY` estiver valida
2. Ollama local (`qwen2.5:3b`)
3. `local-rules`

Nenhuma chave real deve ser colocada no repositorio. O status mostra apenas se a chave existe e se o provider respondeu; o valor de `GEMINI_API_KEY` nao aparece no frontend, logs ou respostas.

Config opcional para IA online:

```text
NEXUSTI_MODEL_PROVIDER=openai
NEXUSTI_OPENAI_ENABLED=true
NEXUSTI_OPENAI_API_KEY=
NEXUSTI_OPENAI_MODEL=gpt-5-mini
```

Para OpenRouter, Groq ou outro endpoint compativel com Chat Completions:

```text
NEXUSTI_MODEL_PROVIDER=openrouter
NEXUSTI_OPENAI_COMPAT_ENABLED=true
NEXUSTI_OPENAI_COMPAT_BASE_URL=https://openrouter.ai/api/v1
NEXUSTI_OPENAI_COMPAT_API_KEY=
NEXUSTI_OPENAI_COMPAT_MODEL=
```

O Nexus Core continua funcionando sem chave externa. Sem Gemini, ele tenta Ollama; sem Ollama, cai para `local-rules`.

## Banco de dados

O SQLite em `data/nexusti.db` armazena:

- logs de acoes seguras
- conversas do agente
- memoria tecnica
- cache de pesquisa web
- perfis de maquina
- execucoes do agente
- chamadas de modelo em `agent_model_calls`

## Catalogo de IA

O Nexus Core nao instala todos os bancos e APIs de uma vez. Ele mantem uma matriz de integracoes em `app/agent/catalog.py` para preparar o projeto sem deixar o MVP pesado.

Inclui:

- Providers locais e gateways: Ollama, llama.cpp server, vLLM, LocalAI, LM Studio, TGI e LiteLLM Proxy
- Providers/API: OpenAI Responses, OpenAI-compatible, Anthropic, Gemini, Mistral e Cohere
- Bancos/RAG: SQLite FTS5, Chroma, Qdrant, FAISS, pgvector, Milvus, Weaviate, LanceDB, OpenSearch, Elasticsearch, Redis e Neo4j
- Capacidades planejadas: streaming, hybrid RAG, reranking, semantic cache, failover, rate limits, token budgeting e PWA mobile

## Seguranca

Nao existem endpoints genericos como `/run`, `/cmd`, `/exec` ou `/powershell`.

Ferramentas sensiveis exigem confirmacao. Acoes bloqueadas incluem execucao arbitraria, scripts baixados, alteracao de registro, bypass de licenca, coleta de senhas e desativacao indevida de protecoes.

## Mobile

Por padrao, o servidor fica em `127.0.0.1`. Nao exponha em `0.0.0.0` antes de ativar token/QR Code.

## Documentacao

- `docs/AGENT_ARCHITECTURE.md`
- `docs/WEB_RESEARCH.md`
- `docs/RAG_MEMORY.md`
- `docs/SECURITY.md`
- `docs/OBSERVABILITY.md`
- `docs/ROADMAP.md`
