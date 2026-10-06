"""Shared authentication, password hashing, JWT, and RBAC helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Lab-only default; override via JWT_SECRET in Compose / environment.
JWT_SECRET = os.getenv("JWT_SECRET", "changeme-lab-only-jwt-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

_bearer = HTTPBearer(auto_error=False)


class Role(str, Enum):
    MEMBER = "member"
    SECURITY_ANALYST = "security_analyst"
    OPERATIONS = "operations"
    ADMINISTRATOR = "administrator"


ALL_ROLES = tuple(r.value for r in Role)


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    role: Role
    tenant_id: str | None

    @property
    def actor_id(self) -> str:
        return self.user_id


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: str,
    username: str,
    role: Role | str,
    tenant_id: str | None,
    expires_minutes: int | None = None,
) -> tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes if expires_minutes is not None else JWT_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": Role(role).value,
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "token_use": "access",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expire


def decode_access_token(token: str) -> Principal:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    role_raw = payload.get("role")
    try:
        role = Role(role_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role claim",
        ) from exc

    user_id = payload.get("sub")
    username = payload.get("username")
    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )

    return Principal(
        user_id=str(user_id),
        username=str(username),
        role=role,
        tenant_id=payload.get("tenant_id"),
    )


def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return decode_access_token(credentials.credentials)


def require_roles(*allowed: Role):
    allowed_set = set(allowed)

    def _dependency(principal: Principal = Depends(require_principal)) -> Principal:
        if principal.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role.value}' is not permitted for this action",
            )
        return principal

    return _dependency


def can_read_tenant_orders(principal: Principal, order_tenant_id: str) -> bool:
    """Tenant-scoped read: members only their tenant; staff roles may read for ops/analysis."""
    if principal.role == Role.MEMBER:
        return principal.tenant_id is not None and principal.tenant_id == order_tenant_id
    if principal.role in {Role.SECURITY_ANALYST, Role.OPERATIONS, Role.ADMINISTRATOR}:
        return True
    return False


def can_submit_orders(principal: Principal) -> bool:
    return principal.role == Role.MEMBER and bool(principal.tenant_id)


def can_modify_roles(principal: Principal) -> bool:
    return principal.role == Role.ADMINISTRATOR


def can_read_audit(principal: Principal) -> bool:
    return principal.role in {Role.ADMINISTRATOR, Role.SECURITY_ANALYST}
