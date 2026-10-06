"""Matching engine simulator — Week 1 health only; DB connectivity planned."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent):
    if (_candidate / "common").is_dir():
        sys.path.insert(0, str(_candidate))
        break

from common.logging_utils import (  # noqa: E402
    actor_id_var,
    configure_logging,
    correlation_id_var,
    log_event,
    new_correlation_id,
    source_ip_var,
)

SERVICE_NAME = "matching-engine"
logger = configure_logging(SERVICE_NAME)

app = FastAPI(
    title="Secure Exchange Connectivity Lab — Matching Engine",
    description="Educational matching simulator. Synthetic orders only.",
    version="0.1.0",
)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or new_correlation_id()
        actor_id = request.headers.get("x-actor-id", "anonymous")
        source_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")

        correlation_id_var.set(correlation_id)
        actor_id_var.set(actor_id)
        source_ip_var.set(source_ip.split(",")[0].strip())

        log_event(
            logger,
            action=f"{request.method} {request.url.path}",
            result="received",
            actor_id=actor_id,
            source_ip=source_ip_var.get(),
            correlation_id=correlation_id,
        )

        response: Response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id

        log_event(
            logger,
            action=f"{request.method} {request.url.path}",
            result=f"status_{response.status_code}",
            actor_id=actor_id,
            source_ip=source_ip_var.get(),
            correlation_id=correlation_id,
        )
        return response


app.add_middleware(StructuredLoggingMiddleware)


@app.get("/health")
def health() -> dict:
    log_event(logger, action="health_check", result="ok", actor_id="system")
    db_url = os.getenv("DATABASE_URL", "")
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "zone": "app+data",
        "database_configured": bool(db_url),
    }


@app.get("/")
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "role": "matching-simulator",
        "trust_boundary": "Accepts traffic from app-net; only this service may reach PostgreSQL on data-net",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8002")), log_config=None)
