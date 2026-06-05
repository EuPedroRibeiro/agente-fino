from __future__ import annotations

from app.agent.memory_stores.sqlite_memory import create_pending_action, get_pending_action, update_pending_action_status
from app.agent.tools_registry import get_tool
from app.services.actions import clean_temp_files, restart_spooler


EXECUTABLE_ACTIONS = {
    "clean_temp": clean_temp_files,
    "restart_spooler": restart_spooler,
}


def prepare_pending_action(user_id: str, tool_name: str, payload: dict | None = None) -> dict | None:
    tool = get_tool(tool_name)
    if not tool or not tool.enabled or not tool.requires_confirmation:
        return None
    return create_pending_action(
        user_id=user_id,
        action_name=tool.name,
        payload=payload or {},
        risk_level=tool.risk_level,
        requires_admin=tool.requires_admin,
    )


def confirm_action(pending_action_id: str, confirm: bool) -> dict:
    pending = get_pending_action(pending_action_id)
    if not pending:
        return {"status": "error", "message": "Acao pendente nao encontrada."}
    if pending["status"] != "pending":
        return {"status": "error", "message": f"Acao ja esta com status {pending['status']}."}
    if not confirm:
        update_pending_action_status(pending_action_id, "rejected")
        return {"status": "rejected", "message": "Acao rejeitada pelo usuario."}
    action = EXECUTABLE_ACTIONS.get(pending["action_name"])
    if not action:
        update_pending_action_status(pending_action_id, "blocked")
        return {"status": "blocked", "message": "Ferramenta nao executavel nesta versao."}
    result = action()
    update_pending_action_status(pending_action_id, "executed")
    return {"status": "executed", "result": result}
