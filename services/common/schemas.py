"""Shared request schemas and validation helpers."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

# Soft limit enforced before JSON parse where possible; also validated here.
MAX_ORDER_BODY_BYTES = 8192


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderCreate(BaseModel):
    symbol: Annotated[str, Field(min_length=1, max_length=6, examples=["SYNTH"])]
    side: OrderSide
    quantity: Annotated[int, Field(ge=1, le=10_000)]
    price: Annotated[Decimal, Field(gt=0)]
    client_order_id: Annotated[str, Field(min_length=1, max_length=64)]

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase_alpha(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned.isalpha():
            raise ValueError("symbol must be alphabetic (synthetic tickers only)")
        return cleaned


class LoginRequest(BaseModel):
    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class RoleChangeRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def known_role(cls, value: str) -> str:
        from common.auth import ALL_ROLES

        if value not in ALL_ROLES:
            raise ValueError(f"role must be one of {ALL_ROLES}")
        return value
