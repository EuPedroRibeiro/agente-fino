from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.runtime import is_cloud
from app.security.config import security_settings


PRODUCTION_ENVS = {"production", "prod", "public"}


@dataclass(frozen=True)
class ProductionReadiness:
    ready: bool
    status: str
    errors: list[str]
    warnings: list[str]
    storage_required: bool


def is_production_cloud() -> bool:
    return is_cloud() and (
        security_settings.public_mode
        or security_settings.environment in PRODUCTION_ENVS
    )


def production_config_errors() -> list[str]:
    if not is_production_cloud():
        return []

    errors: list[str] = []
    if settings.db_engine != "postgres":
        errors.append("AGENTE_FINO_DB_ENGINE precisa ser postgres em producao cloud.")
    if not settings.database_url:
        errors.append("DATABASE_URL e obrigatorio em producao cloud.")
    if not security_settings.session_secret:
        errors.append("AGENTE_FINO_SESSION_SECRET e obrigatorio em producao cloud.")
    if not settings.admin_password_hash:
        errors.append("AGENTE_FINO_ADMIN_PASSWORD_HASH e obrigatorio em producao cloud.")
    return list(dict.fromkeys(errors))


def production_warnings() -> list[str]:
    warnings: list[str] = []
    if is_cloud() and not is_production_cloud() and not settings.database_url:
        warnings.append("Runtime cloud em modo dev usando memoria temporaria; nao use assim em producao.")
    return warnings


def production_readiness() -> ProductionReadiness:
    errors = production_config_errors()
    warnings = production_warnings()
    return ProductionReadiness(
        ready=not errors,
        status="ok" if not errors else "unhealthy",
        errors=errors,
        warnings=warnings,
        storage_required=is_production_cloud(),
    )
