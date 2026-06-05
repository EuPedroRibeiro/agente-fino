from __future__ import annotations

import re
import unicodedata


NEXUS_CONVERSATIONAL_SYSTEM_PROMPT = (
    "Você é o Agente Fino, uma IA técnica e conversacional em português do Brasil. "
    "Você resolve problemas de TI com precisão, mas também conversa naturalmente sobre assuntos gerais, vida, rotina, carreira, "
    "dinheiro, relacionamentos, família, esportes, cultura, música, filmes, games, tecnologia, compras, dúvidas pessoais e opinião. "
    "Seja direto, útil, confiável, natural e seguro. Quando o assunto for técnico, aja com postura profissional. "
    "Quando for conversa comum, responda como um assistente inteligente, humano e parceiro. "
    "Não diga que não é especializado em temas comuns. Só recuse ou limite a resposta quando houver risco real, ilegalidade, "
    "violação de privacidade, conteúdo perigoso, exploração, automutilação, instruções sexuais explícitas, conteúdo envolvendo "
    "menores ou falta absoluta de informação. Quando não houver dados atuais, deixe claro e ofereça uma análise geral."
)


CONVERSATION_INTENTS = {
    "greeting",
    "casual_chat",
    "general_question",
    "general_opinion",
    "life_advice",
    "relationship_advice",
    "family_advice",
    "friendship_advice",
    "career_advice",
    "money_advice",
    "emotional_support",
    "motivation",
    "routine_planning",
    "decision_support",
    "personal_reflection",
    "dating_advice",
    "safe_sexual_education",
    "health_general",
    "tech_support",
    "pc_diagnostic",
    "disk_space",
    "storage_status",
    "ram_status",
    "cpu_status",
    "local_ip_status",
    "uptime_status",
    "spooler_status",
    "simple_pc_metric",
    "folder_size",
    "folder_usage_top",
    "file_count",
    "followup_accept_offer",
    "language_correction",
    "cpf_lookup",
    "cpf_validate",
    "cpf_lab_lookup",
    "cnpj_lookup",
    "public_data_query",
    "disk_usage",
    "printer_support",
    "network_support",
    "software_support",
    "cybersecurity_learning",
    "web_research",
    "deep_web_research",
    "sports_opinion",
    "football_opinion",
    "music_opinion",
    "movie_opinion",
    "gaming_opinion",
    "product_advice",
    "price_or_product_advice",
    "rag_search",
    "memory_search",
    "memory_save",
    "clarification_needed",
    "safe_refusal",
}

GENERAL_CONVERSATION_INTENTS = {
    "greeting",
    "casual_chat",
    "general_question",
    "general_opinion",
    "life_advice",
    "relationship_advice",
    "family_advice",
    "friendship_advice",
    "career_advice",
    "money_advice",
    "emotional_support",
    "motivation",
    "routine_planning",
    "decision_support",
    "personal_reflection",
    "dating_advice",
    "safe_sexual_education",
    "health_general",
    "sports_opinion",
    "football_opinion",
    "music_opinion",
    "movie_opinion",
    "gaming_opinion",
    "product_advice",
    "price_or_product_advice",
}

TECHNICAL_INTENTS = {
    "tech_support",
    "pc_diagnostic",
    "disk_space",
    "storage_status",
    "ram_status",
    "cpu_status",
    "local_ip_status",
    "uptime_status",
    "spooler_status",
    "simple_pc_metric",
    "folder_size",
    "folder_usage_top",
    "file_count",
    "followup_accept_offer",
    "language_correction",
    "cpf_lookup",
    "cpf_validate",
    "cpf_lab_lookup",
    "cnpj_lookup",
    "public_data_query",
    "disk_usage",
    "printer_support",
    "network_support",
    "software_support",
    "cybersecurity_learning",
    "web_research",
    "deep_web_research",
    "rag_search",
}

TOOL_INTENTS = {
    "pc_diagnostic": "analyze_pc",
    "folder_size": "folder_size",
    "folder_usage_top": "disk_usage",
    "file_count": "folder_size",
    "disk_usage": "disk_usage",
    "printer_support": "printer_status",
    "network_support": "network_info",
    "web_research": "web_search",
    "deep_web_research": "web_search",
    "price_or_product_advice": "web_search",
    "rag_search": "rag_search",
    "memory_search": "memory_search",
    "memory_save": "memory_save",
    "cpf_lookup": "document_lookup",
    "cpf_validate": "cpf_validate_local",
    "cpf_lab_lookup": "cpf_lab_simulation",
    "cnpj_lookup": "document_lookup",
    "public_data_query": "public_data",
}

INTENT_RULES = {
    "greeting": {"category": "open_world", "style": "leve, natural e aberto", "needs_web": False, "needs_tool": False},
    "casual_chat": {"category": "open_world", "style": "conversa curta e humana", "needs_web": False, "needs_tool": False},
    "general_question": {"category": "open_world", "style": "explicativo e direto", "needs_web": False, "needs_tool": False},
    "general_opinion": {"category": "opinion", "style": "opinar com nuance e sem fugir", "needs_web": False, "needs_tool": False},
    "life_advice": {"category": "personal", "style": "acolhedor, pratico e sem romantizar sofrimento", "needs_web": False, "needs_tool": False},
    "relationship_advice": {"category": "relationship", "style": "empatico, respeitoso e estrategico", "needs_web": False, "needs_tool": False},
    "family_advice": {"category": "family", "style": "calmo, pratico e respeitoso", "needs_web": False, "needs_tool": False},
    "friendship_advice": {"category": "friendship", "style": "direto, justo e cuidadoso", "needs_web": False, "needs_tool": False},
    "career_advice": {"category": "career", "style": "pratico, orientado a plano", "needs_web": False, "needs_tool": False},
    "money_advice": {"category": "money", "style": "prudente, pratico e sem promessa financeira", "needs_web": False, "needs_tool": False},
    "emotional_support": {"category": "personal", "style": "acolhedor e com pequena acao concreta", "needs_web": False, "needs_tool": False},
    "motivation": {"category": "personal", "style": "energico sem frase vazia", "needs_web": False, "needs_tool": False},
    "routine_planning": {"category": "planning", "style": "organizado e aplicavel", "needs_web": False, "needs_tool": False},
    "decision_support": {"category": "planning", "style": "comparar custo, risco, tempo e beneficio", "needs_web": False, "needs_tool": False},
    "personal_reflection": {"category": "personal", "style": "reflexivo e honesto", "needs_web": False, "needs_tool": False},
    "dating_advice": {"category": "relationship", "style": "respeitoso, simples e sem manipulacao", "needs_web": False, "needs_tool": False},
    "safe_sexual_education": {"category": "safety", "style": "educativo, seguro e nao grafico", "needs_web": False, "needs_tool": False},
    "health_general": {"category": "health", "style": "geral, prudente e nao diagnostico medico", "needs_web": False, "needs_tool": False},
    "tech_support": {"category": "technology", "style": "tecnico, claro e investigativo", "needs_web": False, "needs_tool": False},
    "pc_diagnostic": {"category": "performance", "style": "tecnico com dados locais", "needs_web": False, "needs_tool": True},
    "disk_space": {"category": "storage", "style": "resposta direta primeiro, bonus tecnico curto", "needs_web": False, "needs_tool": True},
    "storage_status": {"category": "storage", "style": "resposta direta primeiro, bonus tecnico curto", "needs_web": False, "needs_tool": True},
    "ram_status": {"category": "system", "style": "metrica local objetiva", "needs_web": False, "needs_tool": True},
    "cpu_status": {"category": "system", "style": "metrica local objetiva", "needs_web": False, "needs_tool": True},
    "local_ip_status": {"category": "network", "style": "metrica local objetiva", "needs_web": False, "needs_tool": True},
    "uptime_status": {"category": "system", "style": "metrica local objetiva", "needs_web": False, "needs_tool": True},
    "spooler_status": {"category": "printer", "style": "status local objetivo", "needs_web": False, "needs_tool": True},
    "simple_pc_metric": {"category": "system", "style": "metrica local objetiva", "needs_web": False, "needs_tool": True},
    "folder_size": {"category": "storage", "style": "tamanho de pasta especifica, direto e seguro", "needs_web": False, "needs_tool": True},
    "folder_usage_top": {"category": "storage", "style": "ranking objetivo e seguro", "needs_web": False, "needs_tool": True},
    "file_count": {"category": "storage", "style": "contagem de arquivos primeiro, tamanho como bonus", "needs_web": False, "needs_tool": True},
    "followup_accept_offer": {"category": "storage", "style": "executar oferta anterior com contexto local", "needs_web": False, "needs_tool": True},
    "language_correction": {"category": "behavior", "style": "corrigir idioma rapidamente e manter portugues do Brasil", "needs_web": False, "needs_tool": False},
    "cpf_lookup": {"category": "authorized_document_lookup", "style": "consulta autorizada direta com documento mascarado", "needs_web": False, "needs_tool": True},
    "cpf_validate": {"category": "authorized_document_lookup", "style": "validacao local objetiva com documento mascarado", "needs_web": False, "needs_tool": True},
    "cpf_lab_lookup": {"category": "document_lab", "style": "simulacao educativa com dados ficticios e documento mascarado", "needs_web": False, "needs_tool": True},
    "cnpj_lookup": {"category": "authorized_document_lookup", "style": "consulta autorizada direta com documento mascarado", "needs_web": False, "needs_tool": True},
    "public_data_query": {"category": "public_data", "style": "consulta direta a fonte publica oficial, com limites claros", "needs_web": False, "needs_tool": True},
    "disk_usage": {"category": "storage", "style": "ranking objetivo e seguro", "needs_web": False, "needs_tool": True},
    "printer_support": {"category": "printer", "style": "tecnico e orientado a verificacoes", "needs_web": False, "needs_tool": True},
    "network_support": {"category": "network", "style": "tecnico e orientado a teste", "needs_web": False, "needs_tool": True},
    "software_support": {"category": "software", "style": "tecnico e direto", "needs_web": False, "needs_tool": False},
    "cybersecurity_learning": {"category": "security", "style": "educativo e defensivo", "needs_web": False, "needs_tool": False},
    "web_research": {"category": "web_research", "style": "com fontes e incertezas", "needs_web": True, "needs_tool": True},
    "deep_web_research": {"category": "web_research", "style": "comparativo, fontes e incertezas", "needs_web": True, "needs_tool": True},
    "sports_opinion": {"category": "sports", "style": "opinar com criterio esportivo", "needs_web": False, "needs_tool": False},
    "football_opinion": {"category": "football", "style": "opinar sobre talento, fisico, ritmo e papel no grupo", "needs_web": False, "needs_tool": False},
    "music_opinion": {"category": "culture", "style": "opinar com gosto e criterio", "needs_web": False, "needs_tool": False},
    "movie_opinion": {"category": "culture", "style": "opinar com contexto e ressalva se faltar dado", "needs_web": False, "needs_tool": False},
    "gaming_opinion": {"category": "games", "style": "comparar proposta, publico, custo e complexidade", "needs_web": False, "needs_tool": False},
    "product_advice": {"category": "shopping", "style": "pratico e comparativo", "needs_web": False, "needs_tool": False},
    "price_or_product_advice": {"category": "shopping", "style": "comparativo com dado atual quando possivel", "needs_web": True, "needs_tool": True},
    "rag_search": {"category": "knowledge", "style": "base local com contexto", "needs_web": False, "needs_tool": True},
    "memory_search": {"category": "memory", "style": "honesto sobre memoria local", "needs_web": False, "needs_tool": True},
    "memory_save": {"category": "memory", "style": "confirmar salvamento sem dados sensiveis", "needs_web": False, "needs_tool": True},
    "clarification_needed": {"category": "general", "style": "perguntar uma coisa especifica", "needs_web": False, "needs_tool": False},
    "safe_refusal": {"category": "safety", "style": "recusar curto e redirecionar para alternativa segura", "needs_web": False, "needs_tool": False},
}

BAD_RESPONSE_PATTERNS = [
    "não sou especializado",
    "nao sou especializado",
    "sou apenas um assistente técnico",
    "sou apenas um assistente tecnico",
    "isso foge da minha função",
    "isso foge da minha funcao",
    "não posso opinar",
    "nao posso opinar",
    "como IA, não tenho opinião",
    "como ia, nao tenho opiniao",
    "o que você acha?",
    "o que voce acha?",
    "não encontrei fontes",
    "nao encontrei fontes",
    "consulte um especialista",
    "não tenho dados em tempo real",
    "nao tenho dados em tempo real",
]

SAFETY_RULES = {
    "sexual": [
        "Permitir educação geral, consentimento, prevenção, ISTs, limites e comunicação.",
        "Não gerar conteúdo erótico, descrição gráfica, roleplay sexual ou instruções explícitas.",
        "Bloquear exploração, coerção, manipulação e qualquer conteúdo sexual envolvendo menores.",
    ],
    "personal_advice": [
        "Validar contexto rapidamente e dar conselho prático.",
        "Não fingir ser psicólogo e não romantizar sofrimento.",
        "Em risco sério de segurança, recomendar ajuda confiável e presencial.",
    ],
    "relationships": [
        "Ajudar com conversa, limites, término, ciúmes, insegurança, respeito e decisão.",
        "Não simular relacionamento romântico em primeira pessoa.",
        "Não ensinar manipulação emocional ou joguinhos abusivos.",
    ],
    "money_career": [
        "Separar desejo de realidade, custo, risco, tempo e benefício.",
        "Não prometer retorno financeiro.",
        "Usar dados atuais quando preço, lei, cotação ou mercado recente forem necessários.",
    ],
    "technical": [
        "Não inventar diagnóstico técnico sem dado.",
        "Ferramentas que alteram o PC precisam de confirmação.",
        "Ferramentas de leitura podem rodar direto.",
    ],
}

WEB_TRIGGER_KEYWORDS = [
    "pesquise",
    "pesquisar",
    "pesquisa web",
    "pesquisa profunda",
    "web profunda",
    "busque na web",
    "procure na internet",
    "internet",
    "fontes",
    "noticia",
    "noticias",
    "atual",
    "hoje",
    "agora",
    "preco",
    "cotacao",
    "valor atual",
    "versao atual",
    "driver atual",
    "modelo novo",
    "cve",
    "lei",
    "convocacao atual",
    "lancamento",
]

NO_WEB_KEYWORDS = [
    "sem pesquisar",
    "sem web",
    "sem internet",
    "sem procurar",
    "na sua opiniao",
    "sua opiniao",
    "o que voce acha",
]

TOOL_TRIGGER_KEYWORDS = {
    "pc_diagnostic": ["analise este pc", "analise o pc", "diagnostico do pc", "diagnosticar pc", "analisar computador"],
    "disk_usage": ["pastas ocupam", "mais espaco", "maiores pastas", "ranking de pastas", "o que ocupa espaco"],
    "printer_support": ["impressora", "spooler", "toner", "cilindro", "brother", "epson", "hp"],
    "network_support": ["rede", "dns", "gateway", "ip local", "wi-fi", "wifi", "smb", "compartilhamento"],
    "memory_search": ["o que voce lembra", "o que sabe de mim", "lembra de mim"],
    "memory_save": ["lembre que", "guarde que", "salve que", "memorize que"],
}

STYLE_RULES = {
    "casual": "responder como conversa normal, sem puxar diagnóstico técnico sem motivo",
    "direct": "responder direto, com pouca enrolação",
    "supportive": "validar rapidamente e propor próximo passo prático",
    "analytical": "dar veredito com critérios, riscos e ressalvas",
    "technical": "usar dados, hipóteses e próximos testes seguros",
    "safe": "limitar conteúdo perigoso e oferecer alternativa segura",
}

RESPONSE_QUALITY_CHECKS = [
    "A resposta responde a pergunta principal?",
    "Evitou muletas como 'não sou especializado' em tema comum?",
    "Usou web somente quando pedido ou necessário por atualidade?",
    "Separou opinião de fato quando não havia dados atuais?",
    "Usou ferramenta local quando o usuário pediu dado do PC?",
    "Não inventou fonte, diagnóstico ou dado local?",
    "Tratou temas pessoais com empatia e ação prática?",
    "Tratou temas sexuais apenas de forma educativa e segura?",
]


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def contains_bad_response_pattern(answer: str) -> bool:
    normalized = normalize_text(answer)
    if not normalized:
        return False
    for pattern in BAD_RESPONSE_PATTERNS:
        normalized_pattern = normalize_text(pattern)
        if normalized_pattern == "o que voce acha?":
            if normalized.startswith("o que voce acha") or normalized.startswith("e voce, o que acha"):
                return True
            continue
        if normalized_pattern in normalized:
            return True
    return False


def should_force_web(message: str) -> bool:
    text = normalize_text(message)
    if any(keyword in text for keyword in NO_WEB_KEYWORDS):
        return False
    return any(keyword in text for keyword in WEB_TRIGGER_KEYWORDS)


def intent_requires_tool(intent: str) -> bool:
    return intent in TOOL_INTENTS


def tool_for_intent(intent: str) -> str | None:
    return TOOL_INTENTS.get(intent)


def quality_rewrite_instruction(answer: str, user_message: str) -> str:
    return (
        "A resposta ficou evasiva ou robótica. Reescreva respondendo diretamente ao usuário, sem fugir do tema, mantendo segurança.\n\n"
        f"Mensagem do usuário: {user_message}\n\n"
        f"Resposta problemática: {answer}"
    )
