"""Unit tests for password hashing, JWT, and RBAC helpers."""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from common.auth import (
    Principal,
    Role,
    can_modify_roles,
    can_read_tenant_orders,
    can_submit_orders,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from common.rate_limit import SlidingWindowRateLimiter
from common.schemas import OrderCreate
from pydantic import ValidationError


def test_password_hash_and_verify():
    hashed = hash_password("MemberA1!")
    assert hashed != "MemberA1!"
    assert verify_password("MemberA1!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_roundtrip_and_claims():
    token, expires = create_access_token(
        user_id="usr-1",
        username="member_a",
        role=Role.MEMBER,
        tenant_id="TENANT_A",
    )
    principal = decode_access_token(token)
    assert principal.user_id == "usr-1"
    assert principal.role == Role.MEMBER
    assert principal.tenant_id == "TENANT_A"
    assert expires.timestamp() > time.time()


def test_expired_jwt_rejected():
    token, _ = create_access_token(
        user_id="usr-1",
        username="member_a",
        role=Role.MEMBER,
        tenant_id="TENANT_A",
        expires_minutes=-1,
    )
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_tampered_jwt_rejected():
    token, _ = create_access_token(
        user_id="usr-1",
        username="member_a",
        role=Role.MEMBER,
        tenant_id="TENANT_A",
    )
    parts = token.split(".")
    # Corrupt payload segment
    bad = parts[0] + "." + parts[1][:-2] + "ab." + parts[2]
    with pytest.raises(HTTPException) as exc:
        decode_access_token(bad)
    assert exc.value.status_code == 401


def test_rbac_helpers():
    member = Principal("u1", "member_a", Role.MEMBER, "TENANT_A")
    other = Principal("u2", "member_b", Role.MEMBER, "TENANT_B")
    analyst = Principal("u3", "analyst", Role.SECURITY_ANALYST, None)
    admin = Principal("u4", "admin", Role.ADMINISTRATOR, "LAB")

    assert can_submit_orders(member) is True
    assert can_submit_orders(analyst) is False
    assert can_read_tenant_orders(member, "TENANT_A") is True
    assert can_read_tenant_orders(member, "TENANT_B") is False
    assert can_read_tenant_orders(other, "TENANT_A") is False
    assert can_read_tenant_orders(analyst, "TENANT_A") is True
    assert can_modify_roles(admin) is True
    assert can_modify_roles(analyst) is False


def test_order_schema_rejects_bad_symbol():
    with pytest.raises(ValidationError):
        OrderCreate(
            symbol="BAD1!",
            side="buy",
            quantity=1,
            price="10.5",
            client_order_id="c1",
        )


def test_order_schema_rejects_zero_qty():
    with pytest.raises(ValidationError):
        OrderCreate(
            symbol="SYNTH",
            side="buy",
            quantity=0,
            price="10.5",
            client_order_id="c1",
        )


def test_rate_limiter_blocks_burst():
    limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=60)
    assert limiter.allow("u1") is True
    assert limiter.allow("u1") is True
    assert limiter.allow("u1") is True
    assert limiter.allow("u1") is False
    assert limiter.allow("u2") is True
