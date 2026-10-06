"""Identity service — auth/RBAC scaffold (Week 1: health + basic endpoint)."""

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

SERVICE_NAME = "identity"
logger = configure_logging(SERVICE_NAME)

# Synthetic role catalog for documentation and later JWT/RBAC work.
SYNTHETIC_ROLES = [
    "member",
    "security_analyst",
    "operations",
    "administrator",
]

app = FastAPI(
    title="Secure Exchange Connectivity Lab — Identity",
    description="Educational identity service. Synthetic users only.",
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
    return {"status": "ok", "service": SERVICE_NAME, "zone": "app"}


@app.get("/roles")
def list_roles() -> dict:
    """Basic endpoint exposing the planned RBAC role set (no auth yet — Week 2)."""
    log_event(logger, action="list_roles", result="ok", actor_id="system")
    return {
        "roles": SYNTHETIC_ROLES,
        "note": "JWT issuance and enforcement arrive in Week 2",
    }


@app.get("/")
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "role": "identity-provider-scaffold",
        "trust_boundary": "Reachable only from app-net peers (gateway, matching-engine)",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8001")), log_config=None)
