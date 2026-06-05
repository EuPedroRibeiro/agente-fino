from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.logging_db import list_action_logs


router = APIRouter(tags=["logs"])


@router.get("/api/logs")
def read_logs(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    return {"logs": list_action_logs(limit=limit)}
