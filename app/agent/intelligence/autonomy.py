from app.core.config import settings


def autonomy_status() -> dict:
    return {"enabled": settings.autonomy_enabled, "level": settings.autonomy_level, "dangerous_actions_auto_execute": False}
