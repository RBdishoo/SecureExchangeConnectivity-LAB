"""Shared structured JSON logging for Secure Exchange Connectivity Lab."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
actor_id_var: ContextVar[str] = ContextVar("actor_id", default="anonymous")
source_ip_var: ContextVar[str] = ContextVar("source_ip", default="unknown")


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for SIEM-friendly ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", record.name),
            "actor_id": getattr(record, "actor_id", actor_id_var.get() or "anonymous"),
            "source_ip": getattr(record, "source_ip", source_ip_var.get() or "unknown"),
            "action": getattr(record, "action", record.getMessage()),
            "result": getattr(record, "result", "info"),
            "correlation_id": getattr(
                record, "correlation_id", correlation_id_var.get() or str(uuid.uuid4())
            ),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure root logging once and return a service-scoped logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    return logger


def log_event(
    logger: logging.Logger,
    *,
    action: str,
    result: str,
    actor_id: str | None = None,
    source_ip: str | None = None,
    correlation_id: str | None = None,
    level: int = logging.INFO,
    **extra: Any,
) -> None:
    """Write a structured security-relevant event."""
    logger.log(
        level,
        action,
        extra={
            "action": action,
            "result": result,
            "actor_id": actor_id or actor_id_var.get() or "anonymous",
            "source_ip": source_ip or source_ip_var.get() or "unknown",
            "correlation_id": correlation_id or correlation_id_var.get() or str(uuid.uuid4()),
            "service": logger.name,
            **extra,
        },
    )


def new_correlation_id() -> str:
    return str(uuid.uuid4())
