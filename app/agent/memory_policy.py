from __future__ import annotations

import re
from typing import Any


MEMORY_CATEGORIES = {
    "user_identity",
    "user_preferences",
    "user_devices",
    "work_context",
    "projects",
    "finance_context",
    "health_context_safe",
    "relationship_context_safe",
    "style_preferences",
    "technical_environment",
    "recurring_tasks",
    "personal_goals",
    "do_not_remember",
}

SENSITIVE_CATEGORIES = {
    "finance_context",
    "health_context_safe",
    "relationship_context_safe",
}

SECRET_PATTERNS = [
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b"),
    re.compile(r"\bsk-[0-9A-Za-z_\-]{20,}\b"),
    re.compile(r"\bsk-proj-[0-9A-Za-z_\-]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"(?i)\b(api[_\s-]?key|token|senha|password|secret|credential|credencial)\s*[:=]\s*[^\s]+"),
]

FORBIDDEN_SECRET_WORDS = {
    "senha",
    "password",
    "token",
    "api key",
    "apikey",
    "secret",
    "credencial",
    "private key",
}


def sanitize_memory_value(value: str) -> tuple[str, bool]:
    sanitized = value
    masked = False
    for pattern in SECRET_PATTERNS:
        sanitized, count = pattern.subn("[SEGREDO_MASCARADO]", sanitized)
        masked = masked or count > 0
    return sanitized.strip(), masked


def detect_memory_category(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["prefiro", "gosto que voce", "responda", "tom", "detalhe", "emoji"]):
        return "style_preferences"
    if any(word in lowered for word in ["notebook", "pc", "computador", "windows", "placa de video", "ssd", "impressora"]):
        return "user_devices"
    if any(word in lowered for word in ["trabalho", "servico", "cliente", "empresa", "suporte tecnico", "profissao"]):
        return "work_context"
    if any(word in lowered for word in ["projeto", "nexusti", "app", "sistema"]):
        return "projects"
    if any(word in lowered for word in ["dinheiro", "divida", "salario", "orcamento", "financeiro"]):
        return "finance_context"
    if any(word in lowered for word in ["saude", "remedio", "ansiedade", "sono", "dor"]):
        return "health_context_safe"
    if any(word in lowered for word in ["relacionamento", "namoro", "familia", "ex ", "amizade"]):
        return "relationship_context_safe"
    if any(word in lowered for word in ["meta", "objetivo", "quero aprender", "quero melhorar"]):
        return "personal_goals"
    if any(word in lowered for word in ["nao lembre", "não lembre", "esquece", "apague"]):
        return "do_not_remember"
    return "user_preferences"


def is_sensitive_category(category: str) -> bool:
    return category in SENSITIVE_CATEGORIES


def should_auto_save(category: str, value: str, *, explicit: bool) -> bool:
    if category == "do_not_remember":
        return False
    lowered = value.lower()
    if any(word in lowered for word in FORBIDDEN_SECRET_WORDS):
        return False
    if is_sensitive_category(category) and not explicit:
        return False
    return explicit


def memory_key_from_value(value: str, category: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    cleaned = re.sub(r"^(lembre que|guarde que|salve que|memorize que|salva isso:?|não esquece isso:?|nao esquece isso:?)", "", cleaned).strip(" :.-")
    words = re.findall(r"[a-z0-9áéíóúãõç]+", cleaned, flags=re.IGNORECASE)
    if not words:
        return category
    return "-".join(words[:6])


def build_memory_payload(
    *,
    category: str | None,
    key: str | None,
    value: str,
    source: str,
    confidence: float,
    pinned: bool = False,
) -> dict[str, Any]:
    sanitized, masked = sanitize_memory_value(value)
    detected_category = category or detect_memory_category(sanitized)
    if detected_category not in MEMORY_CATEGORIES:
        detected_category = "user_preferences"
    return {
        "category": detected_category,
        "key": key or memory_key_from_value(sanitized, detected_category),
        "value": sanitized,
        "source": source,
        "confidence": confidence,
        "pinned": pinned,
        "archived": False,
        "masked_secret": masked,
        "requires_confirmation": is_sensitive_category(detected_category) or masked,
    }
