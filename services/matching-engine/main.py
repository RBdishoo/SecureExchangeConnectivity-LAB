"""Matching engine — tenant-scoped synthetic order store."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent):
    if (_candidate / "common").is_dir():
        sys.path.insert(0, str(_candidate))
        break

from common.auth import Role, can_read_tenant_orders  # noqa: E402
from common.auth import Principal  # noqa: E402
from common.logging_utils import actor_id_var, configure_logging, log_event  # noqa: E402
from common.middleware import StructuredLoggingMiddleware  # noqa: E402
from common.schemas import OrderCreate, OrderSide  # noqa: E402

SERVICE_NAME = "matching-engine"
logger = configure_logging(SERVICE_NAME)

app = FastAPI(
    title="Secure Exchange Connectivity Lab — Matching Engine",
    description="Educational matching simulator. Synthetic orders only.",
    version="0.2.0",
)
app.add_middleware(StructuredLoggingMiddleware, logger=logger)

_lock = Lock()
ORDERS: dict[str, dict[str, Any]] = {}


class InternalOrderRequest(OrderCreate):
    """Order payload as forwarded by the gateway after JWT validation."""


def _principal_from_headers(
    x_user_id: str | None,
    x_username: str | None,
    x_role: str | None,
    x_tenant_id: str | None,
) -> Principal:
    if not x_user_id or not x_username or not x_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing trusted actor headers from gateway",
        )
    try:
        role = Role(x_role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role") from exc
    return Principal(
        user_id=x_user_id,
        username=x_username,
        role=role,
        tenant_id=x_tenant_id or None,
    )


def _serialize(order: dict[str, Any]) -> dict[str, Any]:
    return {
        **order,
        "price": str(order["price"]),
        "side": order["side"].value if isinstance(order["side"], OrderSide) else order["side"],
    }


@app.get("/health")
def health() -> dict:
    log_event(logger, action="health_check", result="ok", actor_id="system")
    db_url = os.getenv("DATABASE_URL", "")
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "zone": "app+data",
        "database_configured": bool(db_url),
        "order_store": "memory+postgres-ready",
        "orders_count": len(ORDERS),
    }


@app.get("/")
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "role": "matching-simulator",
        "trust_boundary": "Accepts traffic from app-net; tenant checks enforced on read/write",
    }


@app.post("/internal/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    body: InternalOrderRequest,
    x_user_id: str | None = Header(default=None),
    x_username: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> dict:
    principal = _principal_from_headers(x_user_id, x_username, x_role, x_tenant_id)
    actor_id_var.set(principal.actor_id)

    if principal.role != Role.MEMBER or not principal.tenant_id:
        log_event(logger, action="create_order", result="denied", actor_id=principal.actor_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant members may submit orders",
        )

    order_id = str(uuid.uuid4())
    record = {
        "order_id": order_id,
        "tenant_id": principal.tenant_id,
        "owner_user_id": principal.user_id,
        "symbol": body.symbol,
        "side": body.side,
        "quantity": body.quantity,
        "price": body.price,
        "client_order_id": body.client_order_id,
        "status": "accepted",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        ORDERS[order_id] = record

    # Optional Postgres persistence when available (best-effort; memory is source for Week 2 demos).
    _persist_order(record)

    log_event(logger, action="create_order", result="ok", actor_id=principal.actor_id)
    return _serialize(record)


@app.get("/internal/orders/{order_id}")
def get_order(
    order_id: str,
    x_user_id: str | None = Header(default=None),
    x_username: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> dict:
    principal = _principal_from_headers(x_user_id, x_username, x_role, x_tenant_id)
    actor_id_var.set(principal.actor_id)

    with _lock:
        order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if not can_read_tenant_orders(principal, order["tenant_id"]):
        log_event(
            logger,
            action="get_order",
            result="denied_cross_tenant",
            actor_id=principal.actor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant order access denied",
        )

    log_event(logger, action="get_order", result="ok", actor_id=principal.actor_id)
    return _serialize(order)


@app.get("/internal/orders")
def list_orders(
    x_user_id: str | None = Header(default=None),
    x_username: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> dict:
    principal = _principal_from_headers(x_user_id, x_username, x_role, x_tenant_id)
    actor_id_var.set(principal.actor_id)

    with _lock:
        all_orders = list(ORDERS.values())

    visible = [o for o in all_orders if can_read_tenant_orders(principal, o["tenant_id"])]
    # Members only see their tenant; already filtered. Staff see all.
    log_event(logger, action="list_orders", result="ok", actor_id=principal.actor_id)
    return {"orders": [_serialize(o) for o in visible]}


def _persist_order(record: dict[str, Any]) -> None:
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return
    try:
        import psycopg

        with psycopg.connect(db_url) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price NUMERIC NOT NULL,
                    client_order_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO orders (
                    order_id, tenant_id, owner_user_id, symbol, side, quantity,
                    price, client_order_id, status, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (order_id) DO NOTHING
                """,
                (
                    record["order_id"],
                    record["tenant_id"],
                    record["owner_user_id"],
                    record["symbol"],
                    record["side"].value if isinstance(record["side"], OrderSide) else record["side"],
                    record["quantity"],
                    Decimal(record["price"]),
                    record["client_order_id"],
                    record["status"],
                    record["created_at"],
                ),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 — lab best-effort persistence
        log_event(
            logger,
            action="persist_order",
            result="db_error",
            actor_id=record.get("owner_user_id", "system"),
        )
        logger.warning("postgres persist skipped: %s", exc)


def reset_state_for_tests() -> None:
    with _lock:
        ORDERS.clear()
