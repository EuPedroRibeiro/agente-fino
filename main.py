from __future__ import annotations

import uvicorn

from app.application import app
from app.core.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )

