from __future__ import annotations

from fastapi import APIRouter

from app.services.report import generate_technical_report


router = APIRouter(tags=["report"])


@router.get("/api/report")
def read_report() -> dict:
    return generate_technical_report(register_log=True)
