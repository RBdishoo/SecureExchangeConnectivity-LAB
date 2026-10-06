"""Shared FastAPI middleware helpers."""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from common.logging_utils import (
    actor_id_var,
    correlation_id_var,
    log_event,
    new_correlation_id,
    source_ip_var,
)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or new_correlation_id()
        actor_id = request.headers.get("x-actor-id", "anonymous")
        source_ip = request.headers.get(
            "x-forwarded-for", request.client.host if request.client else "unknown"
        )

        correlation_id_var.set(correlation_id)
        actor_id_var.set(actor_id)
        source_ip_var.set(source_ip.split(",")[0].strip())

        log_event(
            self.logger,
            action=f"{request.method} {request.url.path}",
            result="received",
            actor_id=actor_id,
            source_ip=source_ip_var.get(),
            correlation_id=correlation_id,
        )

        response: Response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id

        # Prefer authenticated actor if middleware/handlers set it.
        effective_actor = actor_id_var.get() or actor_id
        log_event(
            self.logger,
            action=f"{request.method} {request.url.path}",
            result=f"status_{response.status_code}",
            actor_id=effective_actor,
            source_ip=source_ip_var.get(),
            correlation_id=correlation_id,
        )
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies early (protocol / abuse control)."""

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    return Response(
                        content='{"detail":"Request body too large"}',
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                return Response(
                    content='{"detail":"Invalid Content-Length"}',
                    status_code=400,
                    media_type="application/json",
                )
        return await call_next(request)
