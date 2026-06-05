# Integracoes do Agente Fino

## DarkForest

- Projeto original mantido fora do repositorio de producao, no backup local de experimentos.
- Wrapper defensivo em `modules/darkforest`.
- Interface sensivel separada em `/security`.
- Uso: scanner de chaves, tokens e credenciais em alvos autorizados.
- Nao executa varredura publica ampla automaticamente.
- Nao mostra segredos completos.

## MCP Brasil

- Projeto original mantido fora do repositorio de producao, no backup local de experimentos.
- Wrapper do Agente Fino em `modules/mcp_brasil`.
- Funcionamento principal: chat do Agente Fino.
- Painel tecnico opcional: `/mcp-brasil`.
- Status: `/api/mcp-brasil/status`.
- Uso: dados publicos brasileiros, IBGE, Banco Central, BrasilAPI, CEP, CNPJ, Camara, Senado, transparencia, educacao, saude, seguranca publica e outras fontes suportadas.

O Agente Fino e o orquestrador. DarkForest continua sendo modulo sensivel de seguranca. MCP Brasil continua sendo modulo de dados publicos brasileiros.

Os wrappers em `modules/` permanecem no runtime. Os repositorios externos completos nao sao enviados para GitHub/Vercel.
