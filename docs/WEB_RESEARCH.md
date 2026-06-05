# Pesquisa Web

A web e ativada por padrao, mas e somente leitura.

Ordem de busca:

1. SearxNG, se `NEXUSTI_SEARXNG_URL` estiver configurado
2. DuckDuckGo HTML
3. Bing HTML fallback
4. Fallback curado para alguns fabricantes/frameworks quando buscadores bloqueiam a automacao

O fetch bloqueia SSRF:

- `127.0.0.1`
- `localhost`
- `0.0.0.0`
- `169.254.*`
- `10.*`
- `172.16-31.*`
- `192.168.*`
- `file://`
- `ftp://`

Quando uma pagina e lida, a citacao recebe `source_status = "lida"`. Quando apenas apareceu no resultado de busca, recebe `source_status = "resultado de busca, nao pagina lida"`.

O agente deve preferir fontes oficiais e avisar quando houver menos evidencia do que o ideal.
