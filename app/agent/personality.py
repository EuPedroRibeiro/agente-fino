from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PERSONALITY_PATH = Path("data/personality_settings.json")

DEFAULT_PERSONALITY = {
    "tone": "parceiro fiel",
    "detail_level": "equilibrado",
    "style": "premium esportivo",
    "technical_default": "auto",
    "emoji_usage": "pouco",
    "posture": "natural, firme e seguro",
    "auto_web": True,
    "auto_memory": False,
    "response_preference": "equilibrada",
}

TONE_INSTRUCTIONS = {
    "parceiro fiel": "fale de forma próxima, firme, leal e prática, sem exagerar intimidade.",
    "técnico formal": "responda como documentação técnica clara, com termos precisos e pouca informalidade.",
    "tecnico formal": "responda como documentação técnica clara, com termos precisos e pouca informalidade.",
    "direto e frio": "seja objetivo, analítico e seco, sem rodeios.",
    "Harvey mode": "responda com confiança, estratégia e objetividade, sem arrogância excessiva.",
    "harvey mode": "responda com confiança, estratégia e objetividade, sem arrogância excessiva.",
    "descontraído": "fale leve, natural e com energia, mantendo utilidade.",
    "descontraido": "fale leve, natural e com energia, mantendo utilidade.",
    "premium consultivo": "responda como consultor premium: diagnóstico, critério, plano e próximos passos.",
    "professor iniciante": "explique com calma, exemplos simples e progressão didática.",
    "analista estratégico": "pense em cenários, riscos, trade-offs e melhor decisão.",
    "analista estrategico": "pense em cenários, riscos, trade-offs e melhor decisão.",
}

DETAIL_INSTRUCTIONS = {
    "curto": "respostas curtas, sem perder a resposta principal.",
    "equilibrado": "respostas com contexto suficiente e sem enrolação.",
    "completo": "respostas completas, com nuances e critérios.",
    "passo a passo": "organize a resposta em passos claros quando fizer sentido.",
}

EMOJI_INSTRUCTIONS = {
    "nunca": "não use emojis.",
    "pouco": "use emojis raramente e só se combinarem com o tom.",
    "moderado": "pode usar poucos emojis para calor humano, sem poluir.",
    "livre": "em conversa casual pode usar emojis com naturalidade, mantendo profissionalismo.",
}


def ensure_personality_file() -> None:
    PERSONALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PERSONALITY_PATH.exists():
        save_personality(DEFAULT_PERSONALITY)


def get_personality() -> dict[str, Any]:
    ensure_personality_file()
    try:
        data = json.loads(PERSONALITY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    merged = dict(DEFAULT_PERSONALITY)
    merged.update({key: value for key, value in data.items() if key in DEFAULT_PERSONALITY})
    return merged


def save_personality(settings: dict[str, Any]) -> dict[str, Any]:
    PERSONALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULT_PERSONALITY)
    merged.update({key: value for key, value in settings.items() if key in DEFAULT_PERSONALITY})
    PERSONALITY_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def update_personality(patch: dict[str, Any]) -> dict[str, Any]:
    current = get_personality()
    current.update({key: value for key, value in patch.items() if key in DEFAULT_PERSONALITY and value is not None})
    return save_personality(current)


def reset_personality() -> dict[str, Any]:
    return save_personality(DEFAULT_PERSONALITY)


def build_personality_prompt() -> str:
    settings = get_personality()
    tone = str(settings.get("tone", DEFAULT_PERSONALITY["tone"]))
    detail = str(settings.get("detail_level", DEFAULT_PERSONALITY["detail_level"]))
    emoji = str(settings.get("emoji_usage", DEFAULT_PERSONALITY["emoji_usage"]))
    instructions = [
        f"Personalidade atual: {tone}.",
        TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["parceiro fiel"]),
        DETAIL_INSTRUCTIONS.get(detail, DETAIL_INSTRUCTIONS["equilibrado"]),
        EMOJI_INSTRUCTIONS.get(emoji, EMOJI_INSTRUCTIONS["pouco"]),
        f"Estilo: {settings.get('style')}. Postura: {settings.get('posture')}.",
        f"Modo técnico padrão: {settings.get('technical_default')}. Preferência de resposta: {settings.get('response_preference')}.",
    ]
    if not settings.get("auto_web", True):
        instructions.append("Não use web automaticamente; use somente quando o usuário pedir ou quando for indispensável.")
    if not settings.get("auto_memory", False):
        instructions.append("Não salve memórias automaticamente sem intenção clara do usuário.")
    return " ".join(instructions)
