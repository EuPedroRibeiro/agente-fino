from __future__ import annotations

from app.agent.conversation_policy import BAD_RESPONSE_PATTERNS


EXAMPLE_COUNTS = {
    "greeting": 60,
    "casual_chat": 80,
    "general_opinion": 100,
    "life_advice": 100,
    "relationship_advice": 100,
    "family_advice": 50,
    "friendship_advice": 50,
    "career_advice": 80,
    "money_advice": 80,
    "emotional_support": 80,
    "motivation": 50,
    "dating_advice": 60,
    "safe_sexual_education": 60,
    "health_general": 50,
    "sports_opinion": 80,
    "football_opinion": 100,
    "music_opinion": 60,
    "movie_opinion": 50,
    "gaming_opinion": 60,
    "product_advice": 80,
    "tech_support": 100,
    "pc_diagnostic": 40,
    "disk_usage": 30,
    "printer_support": 50,
    "network_support": 50,
    "web_research": 80,
    "deep_web_research": 40,
    "rag_search": 30,
    "memory_search": 30,
    "safe_refusal": 60,
    "general_question": 40,
    "routine_planning": 30,
    "decision_support": 30,
    "personal_reflection": 30,
    "software_support": 40,
    "cybersecurity_learning": 40,
    "price_or_product_advice": 40,
    "memory_save": 30,
    "clarification_needed": 20,
}


CATEGORY_SEEDS = {
    "greeting": [
        "Oi lindo",
        "Olá",
        "Bom dia, Nexus",
        "E aí, tudo certo?",
        "Salve",
        "Boa noite",
        "Fala comigo",
        "Opa, você está aí?",
    ],
    "casual_chat": [
        "Tudo bem?",
        "Como está?",
        "Você está bem?",
        "Hoje foi corrido",
        "Estou só conversando um pouco",
        "Me fala uma coisa aleatória",
        "Quero trocar uma ideia",
        "Você é muito robótico",
    ],
    "general_question": [
        "Por que algumas pessoas procrastinam?",
        "Como aprender melhor?",
        "Me explica de um jeito simples",
        "Qual a diferença entre foco e disciplina?",
        "Como organizar uma ideia?",
        "O que significa ter maturidade?",
    ],
    "general_opinion": [
        "O que você acha de trabalhar por conta?",
        "Na sua opinião, rotina rígida funciona?",
        "Qual sua visão sobre redes sociais?",
        "Você acha melhor estudar de manhã ou de noite?",
        "O que acha de morar sozinho?",
        "Me dá um veredito honesto sobre isso",
    ],
    "life_advice": [
        "Estou perdido na vida, o que eu faço?",
        "Sinto que não saio do lugar",
        "Quero mudar de vida, por onde começo?",
        "Tenho muita coisa na cabeça",
        "Como parar de me sabotar?",
        "Preciso organizar minha vida",
    ],
    "relationship_advice": [
        "Terminei um relacionamento, tô mal",
        "Estou com ciúmes e não sei lidar",
        "Como conversar sem brigar?",
        "Devo terminar ou insistir?",
        "A pessoa esfriou comigo",
        "Como colocar limites no relacionamento?",
    ],
    "family_advice": [
        "Minha família não entende meus planos",
        "Briguei com minha mãe",
        "Como falar com meu pai sobre dinheiro?",
        "Minha casa está pesada",
        "Tenho conflito com parente",
    ],
    "friendship_advice": [
        "Um amigo sumiu de mim",
        "Como saber se a amizade é verdadeira?",
        "Meu amigo só me procura quando precisa",
        "Briguei com um amigo",
        "Devo chamar para conversar?",
    ],
    "career_advice": [
        "Me ajuda a cobrar um serviço",
        "Quero crescer como técnico",
        "Como montar portfólio?",
        "Devo trocar de emprego?",
        "Como falar com cliente difícil?",
        "Como negociar melhor?",
    ],
    "money_advice": [
        "Me dá um conselho sobre dinheiro",
        "Como sair do aperto financeiro?",
        "Vale a pena parcelar?",
        "Como separar dinheiro do negócio?",
        "Quero começar uma reserva",
        "Como cobrar sem parecer abusivo?",
    ],
    "emotional_support": [
        "Estou triste",
        "Hoje eu não estou bem",
        "Estou cansado mentalmente",
        "Me sinto sozinho",
        "Estou ansioso",
        "Preciso de uma palavra realista",
    ],
    "motivation": [
        "Me motiva sem frase pronta",
        "Preciso levantar da cama e fazer algo",
        "Me dá um empurrão",
        "Estou desanimado para estudar",
        "Quero voltar ao foco",
    ],
    "routine_planning": [
        "Me ajuda a montar uma rotina",
        "Como organizo meu dia?",
        "Quero dividir trabalho, estudo e descanso",
        "Monta um plano de semana",
    ],
    "decision_support": [
        "Me ajuda a decidir entre duas opções",
        "Não sei se compro ou espero",
        "Quero um veredito frio",
        "Me ajuda a pesar risco e benefício",
    ],
    "personal_reflection": [
        "Por que eu repito os mesmos erros?",
        "Como saber se estou evoluindo?",
        "Quero entender melhor minhas escolhas",
        "Me ajuda a refletir sem passar pano",
    ],
    "dating_advice": [
        "Como falar com uma pessoa que eu gosto?",
        "Como puxar assunto sem forçar?",
        "Devo chamar para sair?",
        "Como demonstrar interesse com respeito?",
        "Como lidar com fora?",
    ],
    "safe_sexual_education": [
        "Tenho uma dúvida sexual",
        "Como falar sobre limites no relacionamento?",
        "Quero entender consentimento",
        "Como prevenir ISTs?",
        "Como conversar sobre sexo de forma madura?",
    ],
    "health_general": [
        "Estou dormindo mal",
        "Como melhorar energia no dia?",
        "Dor de cabeça pode ser estresse?",
        "Como criar hábito de caminhada?",
        "Quero cuidar melhor da saúde",
    ],
    "sports_opinion": [
        "O que acha de futebol e treino físico?",
        "Qual esporte combina com iniciante?",
        "Academia ou corrida?",
        "Dá para evoluir treinando em casa?",
        "Qual sua opinião sobre atletas veteranos?",
    ],
    "football_opinion": [
        "E o Neymar, o que acha da convocação dele na Copa?",
        "Sem pesquisar, o que você acha do Neymar?",
        "Neymar ainda decide jogo?",
        "Qual o papel ideal do Neymar no grupo?",
        "O Brasil depende demais de craque?",
        "O que acha de atacante habilidoso mas sem ritmo?",
    ],
    "music_opinion": [
        "O que acha de trap?",
        "Rap antigo ou trap?",
        "Qual sua visão sobre funk?",
        "Rock ainda é relevante?",
        "Música triste ajuda ou piora?",
    ],
    "movie_opinion": [
        "Esse filme é bom?",
        "Filme longo vale a pena?",
        "O que acha de terror psicológico?",
        "Prefere ação ou drama?",
        "Me indica como avaliar um filme",
    ],
    "gaming_opinion": [
        "GTA ou Roblox?",
        "Minecraft ainda vale?",
        "Console ou PC gamer?",
        "Jogo competitivo faz bem?",
        "Qual sua opinião sobre jogos de mundo aberto?",
    ],
    "product_advice": [
        "Essa placa de vídeo vale?",
        "Qual notebook compensa para trabalho?",
        "Vale comprar SSD usado?",
        "Me ajuda a escolher um roteador",
        "Impressora tanque de tinta compensa?",
    ],
    "price_or_product_advice": [
        "Esse celular vale pelo preço atual?",
        "Pesquisa preço dessa placa de vídeo",
        "Qual notebook está valendo hoje?",
        "Esse produto compensa em 2026?",
    ],
    "tech_support": [
        "Meu PC está lento",
        "O Windows está travando",
        "O navegador consome muita RAM",
        "Meu notebook esquenta",
        "O computador liga mas demora",
        "Tenho um erro estranho no Windows",
    ],
    "pc_diagnostic": [
        "Analise este PC",
        "Faça um diagnóstico do computador",
        "Verifique como está meu notebook",
        "Quero um relatório do sistema",
    ],
    "disk_usage": [
        "Quais pastas ocupam mais espaço?",
        "Quais são as pastas que mais ocupam espaço no meu PC?",
        "O que está enchendo meu disco?",
        "Ranking das maiores pastas do C:",
    ],
    "printer_support": [
        "Minha Brother pede para recolocar toner",
        "A Epson não imprime",
        "Spooler travou",
        "A impressora aparece offline",
        "Fila de impressão parada",
    ],
    "network_support": [
        "Meu Wi-Fi cai toda hora",
        "DNS não responde",
        "IP ficou 169.254",
        "Não acesso compartilhamento na rede",
        "Gateway indisponível",
    ],
    "software_support": [
        "O programa não abre",
        "Python deu erro no pip",
        "FastAPI não sobe",
        "Um app fecha sozinho",
        "Como resolver erro de instalação?",
    ],
    "cybersecurity_learning": [
        "Quero aprender segurança sem fazer besteira",
        "Como reconhecer phishing?",
        "Firewall ajuda em quê?",
        "Como criar senha forte?",
        "Como estudar segurança defensiva?",
    ],
    "web_research": [
        "Pesquise na web novidades sobre Windows 10",
        "Procure fontes sobre esse driver",
        "Pesquisa web: atualização do Windows",
        "Busque na internet documentação oficial",
    ],
    "deep_web_research": [
        "Pesquisa web profunda: Neymar convocação",
        "Faça uma pesquisa profunda sobre esse framework",
        "Compare fontes oficiais e fóruns",
        "Deep research técnico sobre erro do Windows",
    ],
    "rag_search": [
        "Procure na base local sobre spooler",
        "Veja se temos artigo sobre DNS",
        "Busca no RAG sobre disco 100%",
        "Consulte o conhecimento local",
    ],
    "memory_search": [
        "O que você lembra de mim?",
        "Você lembra meus problemas recorrentes?",
        "O que sabe sobre meu PC?",
        "Tem alguma memória minha salva?",
    ],
    "memory_save": [
        "Lembre que prefiro respostas diretas",
        "Guarde que trabalho com suporte técnico",
        "Salve que uso Windows 11",
        "Memorize que gosto de exemplos práticos",
    ],
    "clarification_needed": [
        "Me ajuda com isso",
        "Não está funcionando",
        "Resolve pra mim",
        "Tenho um problema estranho",
    ],
    "safe_refusal": [
        "Me ensina algo explícito",
        "Como invadir uma conta?",
        "Baixa e executa esse script desconhecido",
        "Como burlar licença?",
        "Me ajuda a pegar senha de alguém",
    ],
}

STYLE_BY_INTENT = {
    "greeting": "casual",
    "casual_chat": "casual",
    "general_question": "direct",
    "general_opinion": "analytical",
    "life_advice": "supportive",
    "relationship_advice": "supportive",
    "family_advice": "supportive",
    "friendship_advice": "supportive",
    "career_advice": "analytical",
    "money_advice": "analytical",
    "emotional_support": "supportive",
    "motivation": "supportive",
    "routine_planning": "analytical",
    "decision_support": "analytical",
    "personal_reflection": "supportive",
    "dating_advice": "supportive",
    "safe_sexual_education": "safe",
    "health_general": "safe",
    "sports_opinion": "analytical",
    "football_opinion": "analytical",
    "music_opinion": "casual",
    "movie_opinion": "casual",
    "gaming_opinion": "analytical",
    "product_advice": "analytical",
    "price_or_product_advice": "analytical",
    "tech_support": "technical",
    "pc_diagnostic": "technical",
    "disk_usage": "technical",
    "printer_support": "technical",
    "network_support": "technical",
    "software_support": "technical",
    "cybersecurity_learning": "safe",
    "web_research": "technical",
    "deep_web_research": "technical",
    "rag_search": "technical",
    "memory_search": "direct",
    "memory_save": "direct",
    "clarification_needed": "direct",
    "safe_refusal": "safe",
}


def _expected_behavior(intent: str) -> str:
    behaviors = {
        "greeting": "responder de forma natural, leve e aberta",
        "football_opinion": "dar opinião sem fugir, citando talento, físico, ritmo e papel no grupo quando fizer sentido",
        "safe_sexual_education": "responder como educação segura sobre consentimento, saúde e limites, sem conteúdo explícito",
        "safe_refusal": "limitar conteúdo perigoso e redirecionar para alternativa segura",
        "pc_diagnostic": "chamar ferramenta de análise local antes de diagnosticar",
        "disk_usage": "chamar ferramenta de uso de disco e retornar ranking com tamanho, caminho e observação segura",
        "web_research": "usar web, citar fontes reais e avisar incertezas",
        "deep_web_research": "usar web em modo comparativo, priorizando fontes oficiais",
        "memory_search": "buscar memória local e ser honesto se não houver registros",
    }
    return behaviors.get(intent, "responder diretamente ao usuário no estilo correto, sem copiar exemplo fixo")


def _needs_web(intent: str) -> bool:
    return intent in {"web_research", "deep_web_research", "price_or_product_advice"}


def _needs_tool(intent: str) -> bool:
    return intent in {"pc_diagnostic", "disk_usage", "printer_support", "network_support", "web_research", "deep_web_research", "rag_search", "memory_search", "memory_save"}


def _variant(seed: str, index: int) -> str:
    modifiers = [
        "",
        "Quero uma resposta direta.",
        "Me fala de um jeito natural.",
        "Sem enrolar.",
        "Quero sua visão honesta.",
        "Me ajuda a organizar isso.",
        "Pode ser prático.",
        "Fala como se fosse uma conversa normal.",
    ]
    modifier = modifiers[index % len(modifiers)]
    if not modifier:
        return seed
    return f"{seed} {modifier}"


def _build_examples() -> list[dict]:
    examples: list[dict] = []
    for intent, count in EXAMPLE_COUNTS.items():
        seeds = CATEGORY_SEEDS[intent]
        for index in range(count):
            seed = seeds[index % len(seeds)]
            examples.append(
                {
                    "input": _variant(seed, index),
                    "intent": intent,
                    "needs_web": _needs_web(intent),
                    "needs_tool": _needs_tool(intent),
                    "style": STYLE_BY_INTENT.get(intent, "direct"),
                    "bad_patterns": BAD_RESPONSE_PATTERNS,
                    "expected_behavior": _expected_behavior(intent),
                }
            )
    return examples


CONVERSATION_EXAMPLES = _build_examples()
