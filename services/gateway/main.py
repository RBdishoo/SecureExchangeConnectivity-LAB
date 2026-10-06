"""Edge gateway — JWT auth, order validation, rate limits, RBAC enforcement."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent):
    if (_candidate / "common").is_dir():
        sys.path.insert(0, str(_candidate))
        break

from common.auth import (  # noqa: E402
    Principal,
    can_read_audit,
    can_submit_orders,
    decode_access_token,
    require_principal,
)
from common.logging_utils import actor_id_var, configure_logging, log_event  # noqa: E402
from common.middleware import MaxBodySizeMiddleware, StructuredLoggingMiddleware  # noqa: E402
from common.rate_limit import SlidingWindowRateLimiter  # noqa: E402
from common.schemas import (  # noqa: E402
    MAX_ORDER_BODY_BYTES,
    LoginRequest,
    OrderCreate,
    RoleChangeRequest,
)

SERVICE_NAME = "gateway"
logger = configure_logging(SERVICE_NAME)

IDENTITY_URL = os.getenv("IDENTITY_URL", "http://identity:8001")
MATCHING_URL = os.getenv("MATCHING_URL", "http://matching-engine:8002")
ORDER_RATE_LIMIT = int(os.getenv("ORDER_RATE_LIMIT", "5"))
ORDER_RATE_WINDOW = float(os.getenv("ORDER_RATE_WINDOW_SECONDS", "60"))

order_limiter = SlidingWindowRateLimiter(
    max_calls=ORDER_RATE_LIMIT,
    window_seconds=ORDER_RATE_WINDOW,
)

app = FastAPI(
    title="Secure Exchange Connectivity Lab — Gateway",
    description="Educational edge gateway. Synthetic traffic only.",
    version="0.2.0",
)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=MAX_ORDER_BODY_BYTES)
app.add_middleware(StructuredLoggingMiddleware, logger=logger)


def _actor_headers(principal: Principal, request: Request) -> dict[str, str]:
    headers = {
        "x-user-id": principal.user_id,
        "x-username": principal.username,
        "x-role": principal.role.value,
        "x-actor-id": principal.user_id,
    }
    if principal.tenant_id:
        headers["x-tenant-id"] = principal.tenant_id
    corr = request.headers.get("x-correlation-id")
    if corr:
        headers["x-correlation-id"] = corr
    return headers


def _forward_error(exc: httpx.HTTPStatusError) -> None:
    detail: object
    try:
        detail = exc.response.json().get("detail", exc.response.text)
    except Exception:  # noqa: BLE001
        detail = exc.response.text
    raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc


@app.get("/health")
def health() -> dict:
    log_event(logger, action="health_check", result="ok", actor_id="system")
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "zone": "edge",
        "message": "Synthetic educational gateway health endpoint",
        "auth": "enabled",
    }


@app.get("/")
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "role": "edge-gateway",
        "note": "Week 2 — JWT/RBAC, tenant-scoped orders, rate limits",
        "trust_boundary": "Untrusted member clients terminate here; only gateway may reach app-net peers",
        "endpoints": {
            "login": "POST /auth/login",
            "me": "GET /auth/me",
            "orders": "POST /orders, GET /orders, GET /orders/{id}",
            "roles": "PATCH /users/{id}/role",
            "audit": "GET /audit",
        },
    }


@app.post("/auth/login")
def login(body: LoginRequest, request: Request) -> dict:
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{IDENTITY_URL}/auth/login",
                json=body.model_dump(),
                headers={"x-correlation-id": request.headers.get("x-correlation-id", "")},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log_event(logger, action="login", result="denied", actor_id=body.username)
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Identity unavailable: {exc}") from exc

    data = resp.json()
    actor_id_var.set(data.get("user", {}).get("user_id", body.username))
    log_event(logger, action="login", result="ok", actor_id=actor_id_var.get())
    return data


@app.get("/auth/me")
def me(principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    return {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
        "tenant_id": principal.tenant_id,
    }


@app.get("/roles")
def roles(request: Request, principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{IDENTITY_URL}/roles",
                headers={
                    "Authorization": request.headers.get("Authorization", ""),
                    "x-correlation-id": request.headers.get("x-correlation-id", ""),
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Identity unavailable: {exc}") from exc
    return resp.json()


@app.post("/orders", status_code=status.HTTP_201_CREATED)
def submit_order(
    body: OrderCreate,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> dict:
    actor_id_var.set(principal.actor_id)

    if not can_submit_orders(principal):
        log_event(logger, action="submit_order", result="denied", actor_id=principal.actor_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated members with a tenant may submit orders",
        )

    if not order_limiter.allow(principal.user_id):
        log_event(logger, action="submit_order", result="rate_limited", actor_id=principal.actor_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Order rate limit exceeded",
        )

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{MATCHING_URL}/internal/orders",
                json=body.model_dump(mode="json"),
                headers=_actor_headers(principal, request),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log_event(logger, action="submit_order", result="upstream_denied", actor_id=principal.actor_id)
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Matching engine unavailable: {exc}") from exc

    log_event(logger, action="submit_order", result="ok", actor_id=principal.actor_id)
    return resp.json()


@app.get("/orders")
def list_orders(request: Request, principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{MATCHING_URL}/internal/orders",
                headers=_actor_headers(principal, request),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Matching engine unavailable: {exc}") from exc
    return resp.json()


@app.get("/orders/{order_id}")
def get_order(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> dict:
    actor_id_var.set(principal.actor_id)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{MATCHING_URL}/internal/orders/{order_id}",
                headers=_actor_headers(principal, request),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log_event(
            logger,
            action="get_order",
            result="denied" if exc.response.status_code == 403 else f"status_{exc.response.status_code}",
            actor_id=principal.actor_id,
        )
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Matching engine unavailable: {exc}") from exc
    return resp.json()


@app.patch("/users/{user_id}/role")
def change_role(
    user_id: str,
    body: RoleChangeRequest,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> dict:
    """Forward to identity so denied attempts are audited there too."""
    actor_id_var.set(principal.actor_id)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.patch(
                f"{IDENTITY_URL}/users/{user_id}/role",
                json=body.model_dump(),
                headers={
                    "Authorization": request.headers.get("Authorization", ""),
                    **{k: v for k, v in _actor_headers(principal, request).items()},
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log_event(
            logger,
            action="change_role",
            result="denied" if exc.response.status_code == 403 else f"status_{exc.response.status_code}",
            actor_id=principal.actor_id,
        )
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Identity unavailable: {exc}") from exc

    log_event(logger, action="change_role", result="ok", actor_id=principal.actor_id)
    return resp.json()


@app.get("/audit")
def audit(request: Request, principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    if not can_read_audit(principal):
        log_event(logger, action="list_audit", result="denied", actor_id=principal.actor_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{IDENTITY_URL}/audit",
                headers={"Authorization": request.headers.get("Authorization", "")},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Identity unavailable: {exc}") from exc
    return resp.json()


@app.get("/users")
def list_users(request: Request, principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{IDENTITY_URL}/users",
                headers={"Authorization": request.headers.get("Authorization", "")},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _forward_error(exc)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Identity unavailable: {exc}") from exc
    return resp.json()


# Expose decode helper for tests that exercise expired tokens via gateway middleware path.
def authenticate_bearer(authorization: str | None) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return decode_access_token(authorization.split(" ", 1)[1])
