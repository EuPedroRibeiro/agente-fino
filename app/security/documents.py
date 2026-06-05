from __future__ import annotations

import re
import unicodedata
from typing import Any


CPF_PATTERN = re.compile(r"(?<!\d)(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)")
CNPJ_PATTERN = re.compile(r"(?<!\d)(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def mask_cpf(value: str) -> str:
    digits = digits_only(value)
    if len(digits) != 11:
        return "***"
    return f"{digits[:3]}******{digits[-2:]}"


def mask_cnpj(value: str) -> str:
    digits = digits_only(value)
    if len(digits) != 14:
        return "**.***.***/****-**"
    return f"{digits[:2]}.***.***/****-{digits[-2:]}"


def mask_personal_documents(value: str) -> str:
    text = str(value or "")
    text = CNPJ_PATTERN.sub(lambda match: mask_cnpj(match.group(1)), text)
    return CPF_PATTERN.sub(lambda match: mask_cpf(match.group(1)), text)


def sanitize_document_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_document_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_document_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_document_payload(item) for item in value)
    if isinstance(value, str):
        return mask_personal_documents(value)
    return value


def extract_cpfs(message: str) -> list[str]:
    return list(dict.fromkeys(digits_only(match) for match in CPF_PATTERN.findall(message or "")))


def extract_cnpjs(message: str) -> list[str]:
    return list(dict.fromkeys(digits_only(match) for match in CNPJ_PATTERN.findall(message or "")))


def validate_cpf(value: str) -> bool:
    digits = digits_only(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for position in (9, 10):
        total = sum(int(digits[index]) * (position + 1 - index) for index in range(position))
        check = (total * 10) % 11
        check = 0 if check == 10 else check
        if check != int(digits[position]):
            return False
    return True


def validate_cnpj(value: str) -> bool:
    digits = digits_only(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    for length, weights in (
        (12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
        (13, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
    ):
        total = sum(int(digits[index]) * weights[index] for index in range(length))
        remainder = total % 11
        check = 0 if remainder < 2 else 11 - remainder
        if check != int(digits[length]):
            return False
    return True


def classify_document_request(message: str) -> dict[str, Any] | None:
    normalized = _normalize(message)
    cpfs = extract_cpfs(message)
    cnpjs = extract_cnpjs(message)

    if cpfs and "cpf" in normalized:
        if any(term in normalized for term in ("simular", "simulacao", "modo laboratorio", "laboratorio", "estudo")):
            return {
                "intent": "cpf_lab_lookup",
                "category": "document_lab",
                "documents": cpfs,
                "document_type": "cpf",
            }
        validation_terms = ("validar", "valide", "validacao", "e valido", "eh valido", "cpf valido")
        intent = "cpf_validate" if any(term in normalized for term in validation_terms) else "cpf_lookup"
        return {"intent": intent, "category": "authorized_document_lookup", "documents": cpfs, "document_type": "cpf"}
    if cnpjs and "cnpj" in normalized:
        return {"intent": "cnpj_lookup", "category": "authorized_document_lookup", "documents": cnpjs, "document_type": "cnpj"}
    return None


def is_clear_cpf_abuse(message: str, cpfs: list[str]) -> bool:
    if len(cpfs) > 1:
        return True
    normalized = _normalize(message)
    automated_terms = (
        "scraping",
        "scrape",
        "automatizado",
        "automaticamente",
        "varrer",
        "varredura",
        "consulta em massa",
        "consultar em massa",
        "lote de cpf",
        "lista inteira",
    )
    return len(cpfs) > 1 and any(term in normalized for term in automated_terms)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip()
