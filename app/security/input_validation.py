from __future__ import annotations

import re

from fastapi import HTTPException, status

from app.security.config import security_settings


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate_text_field(value: str, *, field_name: str, max_chars: int) -> str:
    text = value or ""
    if len(text) > max_chars:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"{field_name} excede o limite de {max_chars} caracteres.")
    if CONTROL_CHARS.search(text):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} contem caracteres de controle nao permitidos.")
    return text


def validate_chat_message(message: str) -> str:
    return validate_text_field(message, field_name="message", max_chars=security_settings.max_chat_message_chars)


def validate_title(title: str) -> str:
    return validate_text_field(title, field_name="title", max_chars=security_settings.max_title_chars)


def validate_path_text(path: str) -> str:
    return validate_text_field(path, field_name="path", max_chars=security_settings.max_path_chars)


def validate_filename(filename: str) -> str:
    return validate_text_field(filename, field_name="filename", max_chars=security_settings.max_filename_chars)

