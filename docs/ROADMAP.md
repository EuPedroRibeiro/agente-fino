# Roadmap do NexusTI AI

## Fase 1 - MVP local

- API local
- Dashboard
- Status do sistema
- Logs
- Acoes seguras

## Fase 1.1 - Refinamento tecnico

- Healthcheck
- Versao centralizada
- CPU/processos corrigidos
- Relatorio tecnico ampliado
- Logs com campos de seguranca

## Fase 3.0 - Nexus Core

- Agente em `app/agent/`
- Grafo proprio inspirado em LangGraph
- RAG local
- Memoria em SQLite
- Web search com citacoes
- Especialistas internos
- Safety checker
- Tool registry allowlist
- Interface `/agent`
- Observabilidade local

## Fase 3.1 - Inteligencia percebida e IA online

- Roteamento rapido para conversa, calculo e metricas locais
- Correcao de `Analise este PC` para usar relatorio local
- Analise do PC em modo rapido no chat
- Provider OpenAI Responses API
- Provider OpenAI-compatible mantido para OpenRouter/Groq/outros
- Registro de chamadas de modelo em SQLite
- Status de provider/modelo no painel `/agent`

## Fase 3.2 - Catalogo IA e redesign

- Catalogo de providers e bancos/RAG em `app/agent/catalog.py`
- Endpoint `/api/agent/catalog`
- UI `/agent` redesenhada como console tecnico
- Favicon proprio do NexusTI AI
- Conversa local mais natural para interacoes comuns

## Proximas fases

- Autenticacao real por token/QR Code
- Modo mobile seguro em `0.0.0.0`
- Mais ferramentas allowlist com confirmacao
- Integração real ampliada com Ollama
- Configuracao segura de chave via UI local
- Streaming de resposta no chat
- Embeddings locais e vector store
- Adaptador LangGraph
- Langfuse completo
- App mobile Flutter
- Multi-cliente para tecnicos
