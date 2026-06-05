# Agente Fino 2.1.1 Production Repository Cleanup

Esta versao prepara o Agente Fino para rodar de verdade em cloud/Vercel. O modo cloud de producao exige Postgres persistente, sessao segura, hash de senha admin e providers configurados por variaveis de ambiente.

## Regras de producao

Em producao cloud, estas variaveis sao obrigatorias:

```env
AGENTE_FINO_RUNTIME=cloud
AGENTE_FINO_ENV=production
AGENTE_FINO_PUBLIC_MODE=true
AGENTE_FINO_SECURITY_ENABLED=true
AGENTE_FINO_REQUIRE_LOGIN=true
AGENTE_FINO_SESSION_SECRET=
AGENTE_FINO_ALLOWED_ORIGINS=https://SEU-DOMINIO.vercel.app

AGENTE_FINO_DB_ENGINE=postgres
DATABASE_URL=

AGENTE_FINO_ADMIN_USER=Pedro
AGENTE_FINO_ADMIN_PASSWORD_HASH=
```

Se `AGENTE_FINO_PUBLIC_MODE=true` ou `AGENTE_FINO_ENV=production`, o app nao considera `memory` um storage valido. Sem `DATABASE_URL`, sem `AGENTE_FINO_SESSION_SECRET` ou sem `AGENTE_FINO_ADMIN_PASSWORD_HASH`, `/api/health` retorna `status: unhealthy`.

## Gerar hash da senha admin

Use:

```powershell
python tools/create_password_hash.py "SUA_SENHA_FORTE"
```

Configure o resultado em `AGENTE_FINO_ADMIN_PASSWORD_HASH` na Vercel. Nao salve senha crua em `.env`, README, codigo ou logs.

## Providers sem cobranca

Para evitar qualquer cobranca de API por token, nao configure OpenAI na Vercel. Use Gemini Free Tier como provider online e `local-rules` como fallback final:

```env
OPENAI_ENABLED=false
OPENAI_API_KEY=
GEMINI_API_KEY=
DEFAULT_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
LOCAL_RULES_ONLY_FALLBACK=true
```

OpenAI API e cobrada por uso de tokens. O script gratuito nao envia `OPENAI_API_KEY` para a Vercel e define `OPENAI_ENABLED=false`. Para incluir OpenAI futuramente, use a opcao explicita `-IncludeOpenAI` sabendo que pode gerar cobranca.

No runtime cloud:

- Ollama fica sempre `disabled_in_cloud`.
- Ferramentas locais Windows/disco/processos ficam bloqueadas.
- `local-rules` entra apenas como fallback final.

## Banco recomendado

Use um Postgres gerenciado como Neon, Supabase ou outro provedor compatível. O `DATABASE_URL` deve apontar para um banco persistente. O Agente Fino cria/verifica tabelas idempotentemente no startup.

Tabelas principais:

- `users`
- `sessions`
- `conversations`
- `messages`
- `long_term_memories`
- `audit_events`
- `feedback`
- `rate_limits`

## Vercel

Arquivos relevantes:

- `api/index.py`: entrypoint serverless que importa o app FastAPI.
- `app/application.py`: cria o app sem `uvicorn.run`.
- `vercel.json`: roteia requisicoes para `api/index.py`.
- `requirements.txt`: dependencias cloud-safe.
- `requirements-local.txt`: dependencias do modo local/desktop.

Deploy:

1. Configure as variaveis obrigatorias na Vercel.
2. Configure `DATABASE_URL`.
3. Configure OpenAI e/ou Gemini.
4. Faça redeploy.
5. Valide `/api/health`.
6. Entre em `/login`, crie conversa, recarregue a pagina e confirme historico persistente.

## Scripts seguros para Postgres + Vercel

Os scripts abaixo nao imprimem chaves, senha crua, `DATABASE_URL` nem tokens.

Fluxo recomendado sem cobranca:

- Vercel Hobby/free para hospedar.
- Neon Free ou Supabase Free para Postgres.
- Gemini Free Tier para IA.
- OpenAI desativado.

1. Autentique/linke a Vercel:

```powershell
npx.cmd vercel login
npx.cmd vercel link --yes --project SEU-PROJETO
```

2. Defina os segredos no PowerShell atual, sem salvar em arquivo versionado:

```powershell
$env:AGENTE_FINO_DB_ENGINE="postgres"
$env:DATABASE_URL="postgres://..."
$env:AGENTE_FINO_SESSION_SECRET="<segredo-forte>"
$env:AGENTE_FINO_ADMIN_PASSWORD_HASH="<hash-gerado-com-tools/create_password_hash.py>"
$env:GEMINI_API_KEY="<chave-gemini-free>"
$env:OPENAI_ENABLED="false"
```

3. Confira prontidao sem imprimir valores:

```powershell
powershell -ExecutionPolicy Bypass -File tools/check_production_readiness.ps1
```

4. Envie variaveis para a Vercel via `vercel env add`:

```powershell
powershell -ExecutionPolicy Bypass -File tools/configure_vercel_free_env.ps1 -Project SEU-PROJETO
```

Se a variavel ja existir na Vercel e precisar substituir:

```powershell
powershell -ExecutionPolicy Bypass -File tools/configure_vercel_free_env.ps1 -Project SEU-PROJETO -Replace
```

5. Deploy de producao com testes:

```powershell
powershell -ExecutionPolicy Bypass -File tools/deploy_vercel_production.ps1
```

Se quiser configurar envs e fazer deploy no mesmo fluxo:

```powershell
powershell -ExecutionPolicy Bypass -File tools/deploy_vercel_production.ps1 -ConfigureEnv -Project SEU-PROJETO
```

## Healthchecks

`GET /api/health` e publico e basico:

- status
- product
- version
- runtime
- storage_status
- configuration_errors

`GET /api/admin/health` e protegido por login e mostra:

- database
- security
- rate_limit_mode
- audit_mode
- memory/rag/upload modes

## Modo local legado

Para usar diagnostico local Windows, desktop app, Ollama local e SQLite:

```powershell
$env:AGENTE_FINO_RUNTIME="local_legacy"
$env:AGENTE_FINO_ENV="local"
$env:AGENTE_FINO_PUBLIC_MODE="false"
pip install -r requirements-local.txt
python main.py
```

Esse modo e legado/local. Nao use como configuracao de producao web.

## Checklist de release

- `python -B -m unittest discover -s tests -v`
- Verificar que `.env`, logs, bancos locais, backups, zips e uploads nao entram no Git.
- Buscar credenciais antes de commit.
- Confirmar `DATABASE_URL` e `AGENTE_FINO_SESSION_SECRET` na Vercel.
- Trocar qualquer senha temporaria por senha forte antes de producao publica.
