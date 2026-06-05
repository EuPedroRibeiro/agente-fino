# Arquitetura do Nexus Core

O Nexus Core roda dentro do FastAPI principal, em `app/agent/`.

Fluxo do grafo:

```text
START -> normalize_input -> classify_intent -> load_context -> decide_mode
-> retrieve_memory -> retrieve_knowledge -> decide_web_need
-> web_research_if_needed -> specialist_analysis -> select_tools
-> safety_check -> create_plan -> generate_draft -> verify_evidence
-> critic_review -> format_final -> END
```

Componentes:

- `state.py`: modelo Pydantic do estado do agente
- `graph.py`: execucao sequencial com tempos por etapa
- `nodes.py`: nos de execucao
- `planner.py`: plano reversivel primeiro
- `tools_registry.py`: ferramentas permitidas
- `executor.py`: confirmacao e execucao allowlist
- `providers/`: Ollama, OpenAI Responses API, OpenAI-compatible e fallback local
- `specialists/`: especialistas internos
- `evaluators/`: safety, critic e verificadores

O desenho foi feito para aceitar adaptador LangGraph no futuro sem prender o MVP a esse framework.

## Nexus Core 3.2

A camada rapida classifica perguntas simples antes de acionar RAG, web ou modelos. Isso evita que `5*5`, "que horas sao?", "tudo bem?" ou "quanto de espaco tenho no C:" passem pelo fluxo pesado.

`report_analysis` usa relatorio local em modo rapido no chat. O relatorio completo continua disponivel em `/api/report`, mas o agente nao deve bloquear a conversa coletando Event Viewer e detalhes demorados sem necessidade.

Providers de modelo:

1. `openai-responses`
2. `openai-compatible`
3. `ollama`
4. `litellm`
5. `local-rules`

Chamadas reais de modelo sao registradas em `agent_model_calls` para observabilidade.

`catalog.py` registra a matriz de integracoes para providers, bancos vetoriais/RAG, motores de busca web e capacidades futuras. A decisao atual e preparar adapters e configuracao antes de instalar dependencias pesadas.

O `AgentOrchestrator` executa ferramentas de leitura antes de chamar o modelo: `analyze_pc`, `disk_usage`, `printer_status`, `network_info`, `web_search`, `rag_search`, `memory_search` e `memory_save`.
