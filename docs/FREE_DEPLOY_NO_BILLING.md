# Agente Fino sem cobranca

Este fluxo foi criado para colocar o Agente Fino online usando apenas planos gratuitos e evitando providers pagos por token.

## O que usar

- Vercel Hobby/free para hospedagem.
- Neon Free ou Supabase Free para Postgres.
- Gemini API Free Tier para o modelo online.
- `local-rules` como fallback final.

## O que nao usar neste modo

- Nao configurar `OPENAI_API_KEY` na Vercel.
- Nao deixar `OPENAI_ENABLED=true`.
- Nao ativar plano pago da Vercel, Neon, Supabase ou Gemini.
- Nao habilitar billing no Google Cloud se a intencao for risco zero de cobranca.

## Variaveis

```powershell
$env:AGENTE_FINO_DB_ENGINE="postgres"
$env:DATABASE_URL="postgres://..."
$env:AGENTE_FINO_SESSION_SECRET="<segredo-forte>"
$env:AGENTE_FINO_ADMIN_PASSWORD_HASH="<hash-gerado>"
$env:GEMINI_API_KEY="<chave-gemini-free>"
$env:OPENAI_ENABLED="false"
```

## Configurar Vercel

```powershell
npx.cmd vercel login
npx.cmd vercel link --yes --project SEU-PROJETO
powershell -ExecutionPolicy Bypass -File tools/check_production_readiness.ps1
powershell -ExecutionPolicy Bypass -File tools/configure_vercel_free_env.ps1 -Project SEU-PROJETO -GenerateSessionSecret
powershell -ExecutionPolicy Bypass -File tools/deploy_vercel_production.ps1
```

## Se aparecer aviso de falta de OpenAI

Ignore no modo sem cobranca. OpenAI fica propositalmente desativado.

## Resultado esperado

- `/api/health` deve ficar `ok`.
- `/api/agent/providers/status` deve mostrar Gemini como provider principal quando a cota gratuita estiver disponivel.
- OpenAI deve aparecer desativado ou nao configurado.
- Ollama permanece desativado em cloud.
