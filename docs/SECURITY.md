# Seguranca do NexusTI AI

## Politica central

O NexusTI AI nao possui endpoint para executar comandos livres de shell.

Nao existe rota como:

```text
POST /run-command
POST /run
POST /cmd
POST /exec
POST /powershell
```

O Nexus Core tambem nao possui ferramentas livres chamadas `shell`, `cmd`, `powershell`, `exec`, `registry_edit` ou `download_and_run`.

## Allowlist

Ferramentas permitidas ficam em `app/agent/tools_registry.py`.

Exemplos:

- `get_system_status`
- `generate_report`
- `search_knowledge`
- `search_web`
- `check_spooler`
- `list_printers`
- `get_network_info`
- `restart_spooler`
- `clean_temp`

Acoes `medium` ou `high` exigem confirmacao humana antes da execucao.

## Web read-only

A pesquisa web so le paginas e gera citacoes.

O agente nunca deve:

- executar script da internet
- baixar e rodar instalador
- executar comando copiado da web
- usar `file://`, `localhost` ou IP privado como alvo de fetch

## Bloqueios

O safety checker bloqueia:

- execucao arbitraria
- scripts baixados da web
- alteracao de registro
- desativar antivirus/firewall sem motivo legitimo e confirmacao
- ativadores ilegais
- bypass de licenca
- coleta de senha
- roubo de dados
- ocultacao de malware
- invasao de sistemas
- acoes destrutivas

## Permitido

- diagnostico
- explicacao
- correcoes seguras
- orientacao legal
- coleta de logs locais autorizada
- ferramentas allowlist com confirmacao

## Memoria

O agente pode salvar historico tecnico, problemas resolvidos e perfil da maquina.

Nao deve salvar:

- senhas
- tokens
- chaves
- dados bancarios
- dados privados desnecessarios

## Chaves de IA online

Chaves de providers como OpenAI, OpenRouter ou Groq devem ficar fora do repositorio, em variaveis de ambiente ou `.env` local nao versionado.

O SQLite registra metadados de chamadas de modelo, como provider, modelo e latencia, mas nao deve armazenar chaves de API.

## Mobile e rede

O servidor continua local em `127.0.0.1` por padrao.

Nao use `0.0.0.0` em ambiente real antes de autenticar por token/QR Code.
