from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent.memory_stores.sqlite_memory import init_agent_storage
from app.agent.rag import init_knowledge_base
from app.core.config import settings
from app.core.logging_db import init_db
from app.core.production import production_config_errors
from app.core.runtime import is_cloud
from app.db.migrations import init_database_layer
from app.routes import actions, agent, darkforest, dashboard, logs, mcp_brasil, public_data, report, sherlock, status
from app.security.access import AuthRequiredMiddleware
from app.security.config import security_settings
from app.security.csrf import CsrfProtectionMiddleware
from app.security.errors import safe_exception_handler
from app.security.headers import SecurityHeadersMiddleware
from app.security.rate_limit import RateLimitMiddleware


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="IA web/cloud para conversar, organizar ideias e trabalhar com providers online.",
        version=settings.app_version,
        default_response_class=Utf8JSONResponse,
    )

    config_errors = production_config_errors()
    if not config_errors:
        init_database_layer()
        init_db()
        if not is_cloud() or settings.db_engine in {"sqlite", "memory"}:
            init_agent_storage()
        if settings.rag_enabled:
            init_knowledge_base()
    app.state.provider_status = {"startup": "lazy", "message": "Provider status is checked on demand."}

    app.add_exception_handler(Exception, safe_exception_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=security_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Agente-Fino-Session"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CsrfProtectionMiddleware)
    app.add_middleware(AuthRequiredMiddleware)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse("app/static/favicon.ico", media_type="image/x-icon")

    app.include_router(agent.router)
    app.include_router(darkforest.router)
    app.include_router(mcp_brasil.router)
    app.include_router(public_data.router)
    app.include_router(sherlock.router)
    app.include_router(dashboard.router)
    app.include_router(status.router)
    if not is_cloud():
        app.include_router(actions.router)
        app.include_router(logs.router)
        app.include_router(report.router)
    else:
        app.include_router(actions.router)
    return app


app = create_app()
