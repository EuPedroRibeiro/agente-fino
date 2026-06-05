# RAG e Memoria

O RAG local usa SQLite.

Tabelas:

- `knowledge_documents`
- `knowledge_chunks`

Se SQLite FTS5 estiver disponivel, a busca usa FTS. Caso contrario, cai para busca por palavras-chave.

A memoria usa:

- `agent_conversations`
- `agent_memory`
- `machine_profiles`
- `web_research_cache`

O agente pode lembrar problemas resolvidos, diagnosticos de maquinas, impressoras encontradas, comandos que funcionaram e erros recorrentes.

Nao deve salvar senhas, tokens, chaves, dados bancarios ou dados privados desnecessarios.
