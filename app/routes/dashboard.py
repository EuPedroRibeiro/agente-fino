from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings


router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")
UTF8_HTML = "text/html; charset=utf-8"


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
        },
        media_type=UTF8_HTML,
    )
