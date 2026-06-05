from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.auth import require_local_auth
from app.core.runtime import is_cloud
from app.services.actions import clean_temp_files, restart_spooler


router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.post("/clean-temp")
def clean_temp(payload: dict | None = Body(default=None), _auth: None = Depends(require_local_auth)) -> dict:
    if is_cloud():
        return _cloud_disabled_response("clean-temp")
    if not _is_confirmed(payload):
        return _confirmation_response(
            "clean-temp",
            "A limpeza de temporarios remove arquivos antigos das pastas Temp locais. Deseja executar agora?",
        )
    return clean_temp_files()


@router.post("/restart-spooler")
def restart_print_spooler(payload: dict | None = Body(default=None), _auth: None = Depends(require_local_auth)) -> dict:
    if is_cloud():
        return _cloud_disabled_response("restart-spooler")
    if not _is_confirmed(payload):
        return _confirmation_response(
            "restart-spooler",
            "Reiniciar o spooler pode interromper impressoes em andamento. Deseja executar agora?",
        )
    return restart_spooler()


def _is_confirmed(payload: dict | None) -> bool:
    if not payload:
        return False
    return bool(payload.get("confirm") is True)


def _confirmation_response(action: str, message: str) -> dict:
    return {
        "action": action,
        "status": "needs_confirmation",
        "requires_confirmation": True,
        "message": message,
        "risk_level": "low" if action == "clean-temp" else "medium",
    }


def _cloud_disabled_response(action: str) -> dict:
    return {
        "action": action,
        "status": "disabled_in_cloud",
        "requires_confirmation": False,
        "message": "Essa acao local fica desativada no Agente Fino Cloud.",
        "risk_level": "blocked",
    }
