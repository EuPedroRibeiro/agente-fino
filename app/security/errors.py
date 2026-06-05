from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.agent.security.sanitizer import mask_secrets
from app.security.audit import audit_event


async def safe_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = f"AF-ERR-{uuid4().hex[:10]}"
    audit_event(
        "server_error",
        request=request,
        details={"request_id": request_id, "error": mask_secrets(str(exc))},
        severity="error",
    )
    return JSONResponse(
        {
            "detail": "Nao consegui concluir essa acao com seguranca.",
            "request_id": request_id,
        },
        status_code=500,
    )

