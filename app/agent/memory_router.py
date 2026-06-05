from __future__ import annotations

from app.agent.memory_policy import detect_memory_category
from app.agent.router import normalize_for_intent


SAVE_PREFIXES = [
    "lembre que",
    "guarde que",
    "salve que",
    "memorize que",
    "salva isso",
    "não esquece isso",
    "nao esquece isso",
]

FORGET_PREFIXES = [
    "esquece isso",
    "apague isso",
    "remove essa memoria",
    "remova essa memoria",
    "nao lembre disso",
    "não lembre disso",
]

SEARCH_PATTERNS = [
    "o que voce lembra de mim",
    "o que você lembra de mim",
    "qual meu notebook",
    "voce lembra meu trabalho",
    "você lembra meu trabalho",
    "o que sabe de mim",
    "minhas memorias",
    "minhas memórias",
]


def route_memory_intent(message: str) -> dict:
    text = normalize_for_intent(message)
    if any(text.startswith(prefix) for prefix in SAVE_PREFIXES):
        value = _strip_prefix(message, SAVE_PREFIXES)
        return {"action": "save", "value": value, "category": detect_memory_category(value), "confidence": 0.9}
    if any(text.startswith(prefix) for prefix in FORGET_PREFIXES):
        value = _strip_prefix(message, FORGET_PREFIXES)
        return {"action": "forget", "value": value, "category": "do_not_remember", "confidence": 0.8}
    if any(pattern in text for pattern in SEARCH_PATTERNS) or "lembra" in text or "memoria" in text:
        return {"action": "search", "value": message, "category": None, "confidence": 0.8}
    return {"action": "none", "value": message, "category": None, "confidence": 0.0}


def _strip_prefix(message: str, prefixes: list[str]) -> str:
    normalized = normalize_for_intent(message)
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return message[len(prefix) :].strip(" :.-") or message.strip()
    return message.strip()
