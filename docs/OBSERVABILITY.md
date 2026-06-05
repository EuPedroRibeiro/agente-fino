# Observabilidade

O Nexus Core registra execucoes em `agent_runs`.

Campos principais:

- modo
- intencao
- categoria
- web usada
- ferramentas usadas
- confianca
- risco
- latencia
- sucesso/erro
- tempos por etapa

Chamadas para providers de modelo sao registradas em `agent_model_calls`:

- provider
- modelo
- se um modelo real respondeu
- latencia
- sucesso/erro

Isso ajuda a separar lentidao do grafo local, coleta do Windows e latencia da IA online.

Adapter futuro para Langfuse:

```text
NEXUSTI_LANGFUSE_ENABLED=false
NEXUSTI_LANGFUSE_PUBLIC_KEY=
NEXUSTI_LANGFUSE_SECRET_KEY=
NEXUSTI_LANGFUSE_HOST=
```

Nesta versao, o adapter esta preparado, mas nao envia dados para Langfuse.
