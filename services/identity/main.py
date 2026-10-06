"""Identity service — login, JWT, RBAC, admin role changes, audit trail."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent):
    if (_candidate / "common").is_dir():
        sys.path.insert(0, str(_candidate))
        break

from common.auth import (  # noqa: E402
    ALL_ROLES,
    Principal,
    Role,
    can_modify_roles,
    can_read_audit,
    create_access_token,
    hash_password,
    require_principal,
    verify_password,
)
from common.logging_utils import actor_id_var, configure_logging, log_event  # noqa: E402
from common.middleware import StructuredLoggingMiddleware  # noqa: E402
from common.schemas import LoginRequest, RoleChangeRequest  # noqa: E402

SERVICE_NAME = "identity"
logger = configure_logging(SERVICE_NAME)

app = FastAPI(
    title="Secure Exchange Connectivity Lab — Identity",
    description="Educational identity service. Synthetic users only.",
    version="0.2.0",
)
app.add_middleware(StructuredLoggingMiddleware, logger=logger)

_store_lock = Lock()


def _seed_users() -> dict[str, dict[str, Any]]:
    """Synthetic lab users — passwords are placeholders for local demos only."""
    seeds = [
        {
            "user_id": "usr-member-a",
            "username": "member_a",
            "password": "MemberA1!",
            "role": Role.MEMBER.value,
            "tenant_id": "TENANT_A",
        },
        {
            "user_id": "usr-member-b",
            "username": "member_b",
            "password": "MemberB1!",
            "role": Role.MEMBER.value,
            "tenant_id": "TENANT_B",
        },
        {
            "user_id": "usr-analyst",
            "username": "analyst",
            "password": "Analyst1!",
            "role": Role.SECURITY_ANALYST.value,
            "tenant_id": None,
        },
        {
            "user_id": "usr-ops",
            "username": "ops",
            "password": "OpsUser1!",
            "role": Role.OPERATIONS.value,
            "tenant_id": "LAB",
        },
        {
            "user_id": "usr-admin",
            "username": "admin",
            "password": "Admin1!lab",
            "role": Role.ADMINISTRATOR.value,
            "tenant_id": "LAB",
        },
    ]
    users: dict[str, dict[str, Any]] = {}
    for row in seeds:
        users[row["username"]] = {
            "user_id": row["user_id"],
            "username": row["username"],
            "password_hash": hash_password(row["password"]),
            "role": row["role"],
            "tenant_id": row["tenant_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    return users


USERS: dict[str, dict[str, Any]] = _seed_users()
# Append-only audit log — no update/delete APIs (immutable-style for the lab).
AUDIT_LOG: list[dict[str, Any]] = []


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    }


def _append_audit(
    *,
    actor: Principal,
    action: str,
    target_user_id: str,
    detail: dict[str, Any],
    result: str,
    source_ip: str,
    correlation_id: str | None,
) -> dict[str, Any]:
    record = {
        "audit_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_id": actor.user_id,
        "actor_username": actor.username,
        "actor_role": actor.role.value,
        "action": action,
        "target_user_id": target_user_id,
        "detail": detail,
        "result": result,
        "source_ip": source_ip,
        "correlation_id": correlation_id,
    }
    with _store_lock:
        AUDIT_LOG.append(record)
    return record


@app.get("/health")
def health() -> dict:
    log_event(logger, action="health_check", result="ok", actor_id="system")
    return {"status": "ok", "service": SERVICE_NAME, "zone": "app"}


@app.get("/")
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "role": "identity-provider",
        "trust_boundary": "Reachable only from app-net peers (gateway)",
        "auth": "JWT bearer; passwords hashed with bcrypt",
    }


@app.get("/roles")
def list_roles(principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    log_event(logger, action="list_roles", result="ok", actor_id=principal.actor_id)
    return {"roles": list(ALL_ROLES)}


@app.post("/auth/login")
def login(body: LoginRequest, request: Request) -> dict:
    source_ip = request.client.host if request.client else "unknown"
    with _store_lock:
        user = USERS.get(body.username)
    if user is None or not verify_password(body.password, user["password_hash"]):
        log_event(
            logger,
            action="login",
            result="denied",
            actor_id=body.username,
            source_ip=source_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token, expires = create_access_token(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        tenant_id=user["tenant_id"],
    )
    actor_id_var.set(user["user_id"])
    log_event(
        logger,
        action="login",
        result="ok",
        actor_id=user["user_id"],
        source_ip=source_ip,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "user": _public_user(user),
    }


@app.get("/auth/me")
def me(principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    return {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
        "tenant_id": principal.tenant_id,
    }


@app.get("/users")
def list_users(principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    if principal.role not in {
        Role.ADMINISTRATOR,
        Role.SECURITY_ANALYST,
        Role.OPERATIONS,
    }:
        log_event(logger, action="list_users", result="denied", actor_id=principal.actor_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
    with _store_lock:
        users = [_public_user(u) for u in USERS.values()]
    log_event(logger, action="list_users", result="ok", actor_id=principal.actor_id)
    return {"users": users}


@app.patch("/users/{user_id}/role")
def change_role(
    user_id: str,
    body: RoleChangeRequest,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> dict:
    actor_id_var.set(principal.actor_id)
    source_ip = request.client.host if request.client else "unknown"
    correlation_id = request.headers.get("x-correlation-id")

    if not can_modify_roles(principal):
        _append_audit(
            actor=principal,
            action="change_role",
            target_user_id=user_id,
            detail={"requested_role": body.role},
            result="denied",
            source_ip=source_ip,
            correlation_id=correlation_id,
        )
        log_event(logger, action="change_role", result="denied", actor_id=principal.actor_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators may modify roles",
        )

    with _store_lock:
        target = next((u for u in USERS.values() if u["user_id"] == user_id), None)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        previous = target["role"]
        target["role"] = body.role

    audit = _append_audit(
        actor=principal,
        action="change_role",
        target_user_id=user_id,
        detail={"previous_role": previous, "new_role": body.role},
        result="ok",
        source_ip=source_ip,
        correlation_id=correlation_id,
    )
    log_event(logger, action="change_role", result="ok", actor_id=principal.actor_id)
    return {"user": _public_user(target), "audit": audit}


@app.get("/audit")
def list_audit(principal: Principal = Depends(require_principal)) -> dict:
    actor_id_var.set(principal.actor_id)
    if not can_read_audit(principal):
        log_event(logger, action="list_audit", result="denied", actor_id=principal.actor_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
    with _store_lock:
        records = list(AUDIT_LOG)
    log_event(logger, action="list_audit", result="ok", actor_id=principal.actor_id)
    return {"audit": records}


@app.get("/internal/validate")
def validate_token(principal: Principal = Depends(require_principal)) -> dict:
    """Gateway/helpers can confirm a token and receive claims."""
    return {
        "user_id": principal.user_id,
        "username": principal.username,
        "role": principal.role.value,
        "tenant_id": principal.tenant_id,
    }


def reset_state_for_tests() -> None:
    """Test helper — reseed users and clear audit log."""
    global USERS, AUDIT_LOG
    with _store_lock:
        USERS = _seed_users()
        AUDIT_LOG = []
