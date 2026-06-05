from __future__ import annotations

import re
import unicodedata

from app.agent.calculator import looks_like_calculation
from app.agent.conversation_policy import NO_WEB_KEYWORDS, WEB_TRIGGER_KEYWORDS, should_force_web
from app.services.folder_size import resolve_folder_target


LOCAL_METRIC_INTENTS = {
    "disk_space",
    "storage_status",
    "ram_status",
    "cpu_status",
    "local_ip_status",
    "uptime_status",
    "spooler_status",
    "simple_pc_metric",
    "folder_size",
    "file_count",
    "followup_accept_offer",
    "language_correction",
}
SIMPLE_INTENTS = {"greeting", "casual_chat", "time_query", "date_query", "identity_query"}
DIRECT_INTENTS = SIMPLE_INTENTS | LOCAL_METRIC_INTENTS | {"calculation_query"}
NO_WEB_OPINION_INTENTS = {
    "general_opinion",
    "life_advice",
    "relationship_advice",
    "family_advice",
    "friendship_advice",
    "career_advice",
    "money_advice",
    "emotional_support",
    "motivation",
    "dating_advice",
    "safe_sexual_education",
    "health_general",
    "sports_opinion",
    "football_opinion",
    "music_opinion",
    "movie_opinion",
    "gaming_opinion",
    "product_advice",
}


def normalize_for_intent(message: str) -> str:
    normalized = unicodedata.normalize("NFKD", message.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def classify_message(message: str) -> dict:
    text = normalize_for_intent(message)
    if not text:
        return {"intent": "clarification_needed", "category": "general"}

    if _is_time_query(text):
        return {"intent": "time_query", "category": "open_world"}
    if _is_date_query(text):
        return {"intent": "date_query", "category": "open_world"}
    if _is_identity_query(text):
        return {"intent": "identity_query", "category": "open_world"}
    if looks_like_calculation(text):
        return {"intent": "calculation_query", "category": "math"}

    if _asks_memory_save(text):
        return {"intent": "memory_save", "category": "memory"}
    if _asks_memory(text):
        return {"intent": "memory_search", "category": "memory"}

    if _is_language_correction(text):
        return {"intent": "language_correction", "category": "behavior"}

    if _is_safe_refusal(text):
        return {"intent": "safe_refusal", "category": "safety"}
    if _is_safe_sexual_education(text):
        return {"intent": "safe_sexual_education", "category": "safety"}

    if _is_deep_web_request(text):
        return {"intent": "deep_web_research", "category": "web_research"}
    if _is_explicit_web_request(text):
        return {"intent": "web_research", "category": "web_research"}

    if _is_file_count_query(text):
        folder_target = resolve_folder_target(message)
        return {"intent": "file_count", "category": "storage", "path": folder_target.get("path"), "path_source": folder_target.get("source")}
    if _is_disk_usage_query(text):
        return {"intent": "folder_usage_top", "category": "storage"}
    folder_target = resolve_folder_target(message)
    if _is_folder_size_query(text, folder_target):
        return {"intent": "folder_size", "category": "storage", "path": folder_target.get("path"), "path_source": folder_target.get("source")}
    local_metric = _local_metric_intent(text)
    if local_metric:
        return local_metric
    if _is_pc_diagnostic_query(text):
        return {"intent": "pc_diagnostic", "category": "performance"}
    if _is_system_metric_query(text):
        return {"intent": "simple_pc_metric", "category": "system"}

    if _is_greeting(text):
        return {"intent": "greeting", "category": "open_world"}
    if _is_style_feedback(text) or _is_casual_chat(text):
        return {"intent": "casual_chat", "category": "open_world"}

    if _is_relationship_advice(text):
        return {"intent": "relationship_advice", "category": "relationship"}
    if _is_dating_advice(text):
        return {"intent": "dating_advice", "category": "relationship"}
    if _is_family_advice(text):
        return {"intent": "family_advice", "category": "family"}
    if _is_friendship_advice(text):
        return {"intent": "friendship_advice", "category": "friendship"}
    if _is_emotional_support(text):
        return {"intent": "emotional_support", "category": "personal"}
    if _is_life_advice(text):
        return {"intent": "life_advice", "category": "personal"}
    if _is_motivation(text):
        return {"intent": "motivation", "category": "personal"}
    if _is_routine_planning(text):
        return {"intent": "routine_planning", "category": "planning"}
    if _is_decision_support(text):
        return {"intent": "decision_support", "category": "planning"}
    if _is_personal_reflection(text):
        return {"intent": "personal_reflection", "category": "personal"}
    if _is_money_advice(text):
        return {"intent": "money_advice", "category": "money"}
    if _is_career_advice(text):
        return {"intent": "career_advice", "category": "career"}
    if _is_health_general(text):
        return {"intent": "health_general", "category": "health"}

    if _is_football_opinion(text):
        return {"intent": "football_opinion", "category": "football"}
    if _is_sports_opinion(text):
        return {"intent": "sports_opinion", "category": "sports"}
    if _is_music_opinion(text):
        return {"intent": "music_opinion", "category": "culture"}
    if _is_movie_opinion(text):
        return {"intent": "movie_opinion", "category": "culture"}
    if _is_gaming_opinion(text):
        return {"intent": "gaming_opinion", "category": "games"}

    if _is_price_or_current_product(text):
        return {"intent": "price_or_product_advice", "category": "shopping"}
    if _is_product_advice(text):
        return {"intent": "product_advice", "category": "shopping"}

    if _is_printer_support(text):
        return {"intent": "printer_support", "category": "printer"}
    if _is_network_support(text):
        return {"intent": "network_support", "category": "network"}
    if _is_cybersecurity_learning(text):
        return {"intent": "cybersecurity_learning", "category": "security"}
    if _is_software_support(text):
        return {"intent": "software_support", "category": "software"}
    if _is_tech_support(text):
        return {"intent": "tech_support", "category": "technology"}

    if _is_general_opinion(text):
        return {"intent": "general_opinion", "category": "opinion"}
    if _looks_like_question(text):
        return {"intent": "general_question", "category": "open_world"}
    return {"intent": "casual_chat", "category": "open_world"}


def web_needed(message: str, intent: str) -> bool:
    text = normalize_for_intent(message)
    if is_direct_intent(intent):
        return False
    if any(keyword in text for keyword in NO_WEB_KEYWORDS):
        return False
    if intent in NO_WEB_OPINION_INTENTS:
        return False
    if intent in {"web_research", "deep_web_research", "price_or_product_advice"}:
        return True
    return should_force_web(message)


def is_simple_intent(intent: str) -> bool:
    return intent in SIMPLE_INTENTS


def is_direct_intent(intent: str) -> bool:
    return intent in DIRECT_INTENTS


def _has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _is_time_query(text: str) -> bool:
    patterns = [
        r"\bque horas?\b",
        r"\bqual (e|eh) a hora\b",
        r"\bhora atual\b",
        r"\bme diga a hora\b",
        r"\bagora sao\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns) or text in {"hora", "horas", "que horas sao", "que hora e"}


def _is_date_query(text: str) -> bool:
    patterns = [
        r"\bque dia (e|eh) hoje\b",
        r"\bqual (e|eh) a data\b",
        r"\bdata de hoje\b",
        r"\bdia de hoje\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns) or text in {"data", "hoje", "que dia e hoje"}


def _is_identity_query(text: str) -> bool:
    patterns = [
        r"\bquem (e|eh) voce\b",
        r"\bo que voce (faz|pode fazer|consegue fazer)\b",
        r"\bme explique o que voce consegue fazer\b",
        r"\bqual (e|eh) sua funcao\b",
        r"\bvoce (e|eh) quem\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_greeting(text: str) -> bool:
    greetings = {
        "oi",
        "ola",
        "bom dia",
        "boa tarde",
        "boa noite",
        "e ai",
        "salve",
        "opa",
        "fala",
        "oi lindo",
        "ola lindo",
    }
    stripped = _strip_punctuation(text)
    return stripped in greetings or any(stripped.startswith(greeting + " ") for greeting in greetings)


def _is_casual_chat(text: str) -> bool:
    stripped = _strip_punctuation(text)
    casual = {
        "tudo bem",
        "tudo ok",
        "tudo otimo",
        "tudo certo",
        "beleza",
        "tranquilo",
        "como esta",
        "como voce esta",
        "voce esta bem",
        "vc esta bem",
        "valeu",
        "obrigado",
        "obrigada",
    }
    return stripped in casual or any(stripped.startswith(item + " ") for item in casual)


def _is_style_feedback(text: str) -> bool:
    return _has_any(text, ["robotico", "engessado", "frio demais", "responde mal", "muito seco", "fala natural"])


def _is_safe_refusal(text: str) -> bool:
    dangerous = [
        "me ensina algo explicito",
        "conteudo explicito",
        "roleplay sexual",
        "sexo com menor",
        "invadir conta",
        "invadir uma conta",
        "hackear conta",
        "hackear uma conta",
        "roubar senha",
        "pegar senha",
        "burlar licenca",
        "ativador ilegal",
        "crackear",
        "desativar antivirus",
        "ocultar malware",
        "baixa e executa esse script",
        "executa script da internet",
    ]
    return _has_any(text, dangerous)


def _is_safe_sexual_education(text: str) -> bool:
    return _has_any(text, ["duvida sexual", "educacao sexual", "consentimento", "ists", "ist ", "limites sexuais", "prevenir ist", "preservativo"])


def _is_deep_web_request(text: str) -> bool:
    return _has_any(text, ["pesquisa web profunda", "web profunda", "deep research", "pesquisa profunda"])


def _is_explicit_web_request(text: str) -> bool:
    if any(keyword in text for keyword in NO_WEB_KEYWORDS):
        return False
    if _is_language_correction(text) or _is_behavior_correction(text):
        return False
    return any(keyword in text for keyword in WEB_TRIGGER_KEYWORDS if keyword not in {"hoje", "agora", "atual", "internet"})


def _is_language_correction(text: str) -> bool:
    phrases = [
        "fala portugues",
        "fale portugues",
        "responde em portugues",
        "responda em portugues",
        "continua em portugues",
        "mantenha portugues",
        "nao muda pra ingles",
        "nao mude pra ingles",
        "nao responda em ingles",
        "eu falei em ingles no sarcasmo",
        "falei em ingles no sarcasmo",
        "foi sarcasmo",
        "foi ironia",
        "nao era pra responder em ingles",
    ]
    return _has_any(text, phrases)


def _is_behavior_correction(text: str) -> bool:
    phrases = [
        "nao era isso",
        "voce entendeu errado",
        "entendeu errado",
        "corrige isso",
        "respondeu errado",
        "essa resposta ficou ruim",
        "voce ta burro",
        "voce esta burro",
    ]
    return _has_any(text, phrases)


def _is_disk_usage_query(text: str) -> bool:
    patterns = [
        r"\bpastas?.*(mais|maior|maiores).*(ocup|pesad|espaco|armazenamento|gb)",
        r"\bpastas?.*ocup[a-z]*.*(espaco|disco|armazenamento|gb)",
        r"\b(mais|maior|maiores).*(pastas?|diretorios?).*(espaco|armazenamento|gb)",
        r"\bo que (esta )?ocup[a-z]*.*(espaco|disco|armazenamento)",
        r"\branking.*(pastas?|diretorios?|espaco|disco)",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_folder_size_query(text: str, folder_target: dict | None = None) -> bool:
    target = folder_target or {}
    if target.get("path"):
        return True
    folder_terms = [
        "pasta",
        "diretorio",
        "folder",
        "users",
        "usuario",
        "usuarios",
        "suporte",
        "downloads",
        "desktop",
        "documentos",
        "area de trabalho",
        "appdata",
    ]
    size_terms = ["quanto", "quantos gb", "consome", "pesa", "ocupa", "usa", "tamanho", "espaco usado", "verifica"]
    return _has_any(text, folder_terms) and _has_any(text, size_terms)


def _is_file_count_query(text: str) -> bool:
    patterns = [
        r"\bquantos? arquivos?\b",
        r"\btotal de arquivos?\b",
        r"\bcont(ar|a|e|ando)? (todos os )?arquivos?\b",
        r"\barquivos?.*(tem|totais|total)\b",
        r"\btem.*arquivos?\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_pc_diagnostic_query(text: str) -> bool:
    patterns = [
        r"\banalis[ae] (este|esse|o)?\s*(pc|computador|notebook|sistema)\b",
        r"\banalisar (este|esse|o)?\s*(pc|computador|notebook|sistema)\b",
        r"\bdiagnostico do pc\b",
        r"\bdiagnosticar (este|esse|o)?\s*(pc|computador|notebook|sistema)\b",
        r"\brelatorio tecnico\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_system_metric_query(text: str) -> bool:
    metric_words = [
        "espaco livre",
        "quanto de espaco",
        "disco c",
        "armazenamento",
        "hd livre",
        "ssd livre",
        "uso de disco",
        "meu disco",
        "quanto de ram",
        "quanto de memoria",
        "minha ram",
        "ram livre",
        "uso de ram",
        "quanto de cpu",
        "uso de cpu",
        "processador",
        "meu ip",
        "ip local",
        "nome do pc",
        "hostname",
        "uptime",
        "tempo ligado",
    ]
    return _has_any(text, metric_words)


def _local_metric_intent(text: str) -> dict | None:
    folder_usage_terms = [
        "pastas ocupam",
        "pasta ocupa",
        "maiores pastas",
        "pastas mais",
        "ranking",
        "quais pastas",
        "quais arquivos",
        "arquivos grandes",
        "o que ocupa",
    ]
    if _has_any(text, folder_usage_terms):
        return None

    if _has_any(text, ["spooler", "servico de impressao", "fila de impressao"]) and _has_any(text, ["rodando", "status", "esta ativo", "esta ligado"]):
        return {"intent": "spooler_status", "category": "printer"}

    if _has_any(text, ["ip local", "meu ip", "qual meu ip"]) and not _has_any(text, ["publico", "externo", "internet"]):
        return {"intent": "local_ip_status", "category": "network"}

    if _has_any(text, ["uptime", "tempo ligado", "ha quanto tempo ligado", "quanto tempo ligado", "inicializacao", "inicializou"]):
        return {"intent": "uptime_status", "category": "system"}

    if _has_any(text, ["quanto de ram", "uso de ram", "ram estou usando", "minha ram", "memoria ram", "quanto de memoria", "uso de memoria"]):
        return {"intent": "ram_status", "category": "system"}

    if _has_any(text, ["quanto de cpu", "uso de cpu", "cpu esta", "cpu estou usando", "processador esta", "uso do processador"]):
        return {"intent": "cpu_status", "category": "system"}

    disk_words = ["disco", "hd", "ssd", "armazenamento", "espaco", "unidade c", "disco c", "c:"]
    disk_question_words = ["quanto", "livre", "tem", "cheio", "olhe", "veja", "ver", "status", "sobrou", "resta"]
    if _has_any(text, disk_words) and _has_any(text, disk_question_words):
        return {"intent": "disk_space", "category": "storage"}

    return None


def _is_relationship_advice(text: str) -> bool:
    return _has_any(text, ["relacionamento", "terminei", "termino", "ciumes", "namoro", "namorada", "namorado", "ex ", "brigar no relacionamento"])


def _is_dating_advice(text: str) -> bool:
    return _has_any(text, ["pessoa que eu gosto", "puxar assunto", "chamar para sair", "demonstrar interesse", "tomar fora", "flertar", "ficar com"])


def _is_family_advice(text: str) -> bool:
    return _has_any(text, ["familia", "meu pai", "minha mae", "parente", "irmao", "irma", "em casa"])


def _is_friendship_advice(text: str) -> bool:
    return _has_any(text, ["amigo", "amiga", "amizade", "colega sumiu", "amigo sumiu"])


def _is_emotional_support(text: str) -> bool:
    return _has_any(text, ["estou triste", "to triste", "nao estou bem", "cansado mentalmente", "sozinho", "ansioso", "mal comigo", "desanimado demais"])


def _is_life_advice(text: str) -> bool:
    return _has_any(text, ["perdido na vida", "mudar de vida", "nao saio do lugar", "me sabotar", "organizar minha vida", "vida baguncada"])


def _is_motivation(text: str) -> bool:
    return _has_any(text, ["me motiva", "motivacao", "empurrao", "voltar ao foco", "desanimado para estudar"])


def _is_routine_planning(text: str) -> bool:
    return _has_any(text, ["montar uma rotina", "organizo meu dia", "plano de semana", "dividir trabalho", "rotina de estudo"])


def _is_decision_support(text: str) -> bool:
    return _has_any(text, ["me ajuda a decidir", "veredito", "risco e beneficio", "duas opcoes", "compro ou espero"])


def _is_personal_reflection(text: str) -> bool:
    return _has_any(text, ["repito os mesmos erros", "estou evoluindo", "minhas escolhas", "refletir", "passar pano"])


def _is_money_advice(text: str) -> bool:
    return _has_any(text, ["dinheiro", "financeiro", "parcelar", "reserva", "cobrar um servico", "cobrar sem", "preco do meu servico"])


def _is_career_advice(text: str) -> bool:
    return _has_any(text, ["carreira", "emprego", "cliente dificil", "portfolio", "crescer como tecnico", "negociar", "cobrar um servico"])


def _is_health_general(text: str) -> bool:
    return _has_any(text, ["dormindo mal", "dor de cabeca", "cuidar melhor da saude", "caminhada", "energia no dia", "alimentacao"])


def _is_football_opinion(text: str) -> bool:
    return _has_any(text, ["neymar", "copa", "convocacao", "selecao brasileira", "futebol", "atacante", "jogador"])


def _is_sports_opinion(text: str) -> bool:
    return _has_any(text, ["esporte", "academia", "corrida", "treino", "atleta", "basquete", "volei"])


def _is_music_opinion(text: str) -> bool:
    return _has_any(text, ["trap", "rap", "funk", "rock", "musica", "album", "cantor", "banda"])


def _is_movie_opinion(text: str) -> bool:
    return _has_any(text, ["filme", "serie", "cinema", "terror psicologico", "drama", "acao"])


def _is_gaming_opinion(text: str) -> bool:
    return _has_any(text, ["gta", "roblox", "minecraft", "pc gamer", "console", "jogo", "games", "mundo aberto"])


def _is_price_or_current_product(text: str) -> bool:
    return _is_product_advice(text) and _has_any(text, ["preco atual", "valor atual", "hoje", "em 2026", "pesquisa preco", "cotacao"])


def _is_product_advice(text: str) -> bool:
    return _has_any(text, ["placa de video", "notebook", "celular", "ssd", "roteador", "impressora tanque", "vale comprar", "vale a pena comprar", "esse produto", "essa placa"])


def _is_printer_support(text: str) -> bool:
    return _has_any(text, ["impressora", "printer", "spooler", "toner", "cilindro", "brother", "epson", "hp", "fila de impressao"])


def _is_network_support(text: str) -> bool:
    return _has_any(text, ["rede", "dns", "gateway", "ip ", "169.254", "smb", "compartilhamento", "wifi", "wi-fi", "internet caiu", "internet lenta", "sem internet"])


def _is_cybersecurity_learning(text: str) -> bool:
    return _has_any(text, ["seguranca defensiva", "phishing", "firewall", "senha forte", "aprender seguranca", "cybersecurity"])


def _is_software_support(text: str) -> bool:
    return _has_any(text, ["programa nao abre", "pip", "fastapi", "erro de instalacao", "app fecha", "python deu erro"])


def _is_tech_support(text: str) -> bool:
    return _has_any(text, ["pc lento", "meu pc esta lento", "windows travando", "notebook esquenta", "computador demora", "erro no windows", "navegador consome"])


def _is_general_opinion(text: str) -> bool:
    return _has_any(text, ["o que acha", "qual sua opiniao", "na sua opiniao", "sua visao", "voce prefere"])


def _looks_like_question(text: str) -> bool:
    return "?" in text or text.startswith(("como ", "por que ", "porque ", "qual ", "quando ", "onde ", "quem ", "o que "))


def _asks_memory(text: str) -> bool:
    return _has_any(text, ["lembra", "memoria", "o que voce sabe de mim", "o que voce lembra de mim", "qual meu notebook", "voce lembra meu trabalho", "esquece isso"])


def _asks_memory_save(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in ["lembre que", "guarde que", "salve que", "memorize que", "salva isso", "nao esquece isso"])


def _strip_punctuation(text: str) -> str:
    stripped = re.sub(r"[!?.,;:]+", " ", text).strip()
    return re.sub(r"\s+", " ", stripped)
