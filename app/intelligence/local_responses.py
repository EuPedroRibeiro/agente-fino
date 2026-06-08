from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agent.router import normalize_for_intent


FAST_LOCAL_INTENTS = {
    "greeting",
    "identity_query",
    "time_query",
    "date_query",
    "casual_chat",
}

_DEFAULT_TIMEZONE_NAME = "America/Sao_Paulo"

_WEEKDAYS_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

_MONTHS_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


_BRASILIA_TIME_TERMS = {
    "horario de brasilia",
    "horário de brasilia",
    "horario de brasília",
    "horário de brasília",
    "hora de brasilia",
    "hora de brasília",
    "hora em brasilia",
    "hora em brasília",
    "hora no brasil",
    "horario do brasil",
    "horário do brasil",
    "hora atual em brasilia",
    "hora atual em brasília",
    "qual horario de brasilia",
    "qual horário de brasilia",
    "qual horario de brasília",
    "qual horário de brasília",
    "qual o horario de brasilia",
    "qual o horário de brasilia",
    "qual o horario de brasília",
    "qual o horário de brasília",
    "que horas sao em brasilia",
    "que horas são em brasilia",
    "que horas sao em brasília",
    "que horas são em brasília",
    "que horas sao no brasil",
    "que horas são no brasil",
}


def _default_timezone_name() -> str:
    return (os.getenv("AGENTE_FINO_DEFAULT_TIMEZONE") or _DEFAULT_TIMEZONE_NAME).strip() or _DEFAULT_TIMEZONE_NAME


def _default_timezone() -> ZoneInfo:
    name = _default_timezone_name()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(_DEFAULT_TIMEZONE_NAME)


def _localized_now(now: datetime | None = None) -> datetime:
    tz = _default_timezone()
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def _timezone_label() -> str:
    name = _default_timezone_name()
    if name == _DEFAULT_TIMEZONE_NAME:
        return "horário de Brasília"
    return f"fuso {name}"


def detect_fast_local_intent(message: str) -> str | None:
    text = normalize_for_intent(message).strip(" .!?")
    if not text:
        return None

    identity_patterns = (
        r"\bqual (?:e |eh )?(?:o )?seu nome\b",
        r"\bcomo voce se chama\b",
        r"\bquem (?:e|eh) voce\b",
        r"\bquem voce (?:e|eh)\b",
    )
    if any(re.search(pattern, text) for pattern in identity_patterns):
        return "identity_query"

    time_patterns = (
        r"\bque horas? (?:sao|e|eh)\b",
        r"\bqual (?:e|eh )?a hora(?: atual)?\b",
        r"\bhora atual\b",
        r"\bme diga a hora\b",
        r"\bhorario de brasilia\b",
        r"\bhora de brasilia\b",
        r"\bhora em brasilia\b",
        r"\bhora no brasil\b",
        r"\bhorario do brasil\b",
        r"\bqual (?:o )?horario de brasilia\b",
        r"\bque horas? (?:sao|e|eh) em brasilia\b",
        r"\bque horas? (?:sao|e|eh) no brasil\b",
    )
    if text in _BRASILIA_TIME_TERMS or any(re.search(pattern, text) for pattern in time_patterns) or text in {"hora", "horas"}:
        return "time_query"

    date_patterns = (
        r"\bque dia (?:e|eh) hoje\b",
        r"\bqual (?:e|eh )?a data(?: de hoje)?\b",
        r"\bdata de hoje\b",
        r"\bdia de hoje\b",
        r"\bdata atual\b",
        r"\bhoje (?:e|eh) que dia\b",
    )
    if any(re.search(pattern, text) for pattern in date_patterns) or text in {"data", "hoje"}:
        return "date_query"

    greetings = {
        "oi",
        "ola",
        "opa",
        "e ai",
        "salve",
        "fala",
        "bom dia",
        "boa tarde",
        "boa noite",
        "oi lindo",
        "ola lindo",
    }
    if text in greetings:
        return "greeting"

    if answer_simple_casual(message) is not None:
        return "casual_chat"
    return None


def answer_greeting(message: str = "") -> str:
    text = normalize_for_intent(message).strip(" .!?")
    if text == "bom dia":
        return "Bom dia! Tô online. Manda a boa."
    if text == "boa tarde":
        return "Boa tarde! Tô online. Manda a boa."
    if text == "boa noite":
        return "Boa noite! Tô online. Manda a boa."
    return "Fala! Tô online. Manda a boa."


def answer_identity() -> str:
    return "Sou o Agente Fino. Tô aqui para pensar, organizar e resolver contigo."


def answer_time(now: datetime | None = None) -> str:
    current = _localized_now(now)
    return f"Agora são {current:%H:%M} no {_timezone_label()}."


def answer_date(now: datetime | None = None) -> str:
    current = _localized_now(now)
    weekday = _WEEKDAYS_PT[current.weekday()]
    month = _MONTHS_PT[current.month - 1]
    return f"Hoje é {weekday}, {current.day} de {month} de {current.year}."


def answer_simple_casual(message: str) -> str | None:
    text = normalize_for_intent(message).strip(" .!?")
    if text in {"obrigado", "obrigada", "valeu"}:
        return "Fechado. Quando precisar, me chama."
    if text == "teste":
        return "Tô respondendo. Pode mandar."
    if text in {"kkkk", "top", "gostei"}:
        return "Boa. Manda a próxima."
    if text in {"tudo bem", "tudo certo", "beleza", "como voce esta", "voce esta bem"}:
        return "Tudo certo por aqui. E contigo?"
    return None


def answer_local_intent(intent: str, message: str = "", now: datetime | None = None) -> str | None:
    if intent == "greeting":
        return answer_greeting(message)
    if intent == "identity_query":
        return answer_identity()
    if intent == "time_query":
        return answer_time(now)
    if intent == "date_query":
        return answer_date(now)
    if intent == "casual_chat":
        return answer_simple_casual(message)
    return None


def fallback_local_intent(intent: str, message: str = "") -> str | None:
    if intent == "greeting":
        return "Fala! Tô online. Manda a boa."
    if intent == "identity_query":
        return "Sou o Agente Fino. Tô aqui para pensar, organizar e resolver contigo."
    if intent == "time_query":
        return "Não consegui ler o relógio local agora, mas meu padrão é responder no horário de Brasília."
    if intent == "date_query":
        return "Não consegui ler a data local agora, mas meu padrão é responder pela data de Brasília."
    if intent == "casual_chat":
        return answer_simple_casual(message)
    return None


def safe_answer_local_intent(intent: str, message: str = "", now: datetime | None = None) -> str | None:
    try:
        return answer_local_intent(intent, message, now)
    except Exception:
        return fallback_local_intent(intent, message)
