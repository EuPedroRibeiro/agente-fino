from __future__ import annotations

from app.agent.security.sanitizer import contains_secret, mask_secrets


def reject_secret_for_memory(value: str) -> dict:
    secret = contains_secret(value or "")
    return {
        "allowed": not secret,
        "masked_value": mask_secrets(value or ""),
        "reason": "Segredos nao devem ser salvos em memoria." if secret else None,
    }

