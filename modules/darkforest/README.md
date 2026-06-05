# DarkForest Hunter no Agente Fino

Modulo sensivel para detectar possiveis API keys, tokens e credenciais expostas em arquivos, textos e projetos autorizados.

## Proposito

O DarkForest Hunter foi integrado como ferramenta acoplada ao Agente Fino, nao como substituto do chat principal. Ele ajuda em auditorias defensivas de projetos proprios ou ambientes onde voce tenha autorizacao.

## Seguranca

- O modulo exige login.
- A tela exige aceite do aviso sensivel.
- A execucao exige checkbox de autorizacao.
- Chaves completas nunca sao exibidas.
- Historico salva apenas metadados: data, usuario, alvo, quantidade de achados, risco e status.
- Alvos remotos ficam bloqueados por padrao. Clone ou baixe o repositorio autorizado e aponte um caminho local.

## Configuracao

```env
DARKFOREST_ENABLED=true
DARKFOREST_PATH=C:\caminho\externo\DarkForest-Hunter-OpenAI
DARKFOREST_MAX_RUNTIME=120
DARKFOREST_MASK_SECRETS=true
DARKFOREST_SAVE_HISTORY=true
DARKFOREST_ALLOW_REMOTE_TARGETS=false
```

## Execucao

1. Abra `/security`.
2. Leia o aviso de conteudo sensivel.
3. Marque a confirmacao de autorizacao.
4. Informe um caminho local ou texto autorizado.
5. Execute a analise.

## Interpretando relatorios

- `critical`: chave/token com alto potencial de abuso.
- `high`: segredo sensivel ou token com risco relevante.
- `medium`: atribuicao suspeita que exige revisao manual.
- `low`: sem achados ou apenas observacao.

## Remover ou desativar

Defina:

```env
DARKFOREST_ENABLED=false
```

Quando desativado, a pagina retorna status de modulo indisponivel e o botao do Agente Fino nao deve aparecer no menu tecnico.

## Sobre o projeto original

Referencia: `https://github.com/pukpuklouis/DarkForest-Hunter-OpenAI`.

O projeto original e opcional e deve ser mantido fora do repositorio de producao. O wrapper defensivo em `modules/darkforest` continua funcional sem carregar o projeto experimental no deploy cloud.

O Agente Fino usa uma camada wrapper defensiva e isolada. A busca publica ampla, validacao de saldo de chaves e chamadas externas dos scripts originais nao sao executadas automaticamente.
