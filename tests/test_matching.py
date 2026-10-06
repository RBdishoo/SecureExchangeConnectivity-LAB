"""Matching-engine tenant isolation and order validation tests."""

from __future__ import annotations


def _headers(user_id, username, role, tenant_id=None):
    h = {
        "x-user-id": user_id,
        "x-username": username,
        "x-role": role,
    }
    if tenant_id:
        h["x-tenant-id"] = tenant_id
    return h


MEMBER_A = _headers("usr-member-a", "member_a", "member", "TENANT_A")
MEMBER_B = _headers("usr-member-b", "member_b", "member", "TENANT_B")
ANALYST = _headers("usr-analyst", "analyst", "security_analyst")


ORDER = {
    "symbol": "SYNTH",
    "side": "buy",
    "quantity": 10,
    "price": "12.50",
    "client_order_id": "c-order-1",
}


def test_member_can_create_order(matching_client):
    resp = matching_client.post("/internal/orders", json=ORDER, headers=MEMBER_A)
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == "TENANT_A"
    assert body["owner_user_id"] == "usr-member-a"


def test_analyst_cannot_create_order(matching_client):
    resp = matching_client.post("/internal/orders", json=ORDER, headers=ANALYST)
    assert resp.status_code == 403


def test_cross_tenant_order_read_blocked(matching_client):
    created = matching_client.post("/internal/orders", json=ORDER, headers=MEMBER_A)
    assert created.status_code == 201
    order_id = created.json()["order_id"]

    denied = matching_client.get(f"/internal/orders/{order_id}", headers=MEMBER_B)
    assert denied.status_code == 403
    assert "cross-tenant" in denied.json()["detail"].lower()

    allowed = matching_client.get(f"/internal/orders/{order_id}", headers=MEMBER_A)
    assert allowed.status_code == 200


def test_member_list_orders_is_tenant_scoped(matching_client):
    matching_client.post("/internal/orders", json=ORDER, headers=MEMBER_A)
    matching_client.post(
        "/internal/orders",
        json={**ORDER, "client_order_id": "c-order-2"},
        headers=MEMBER_B,
    )
    listed = matching_client.get("/internal/orders", headers=MEMBER_A)
    assert listed.status_code == 200
    tenants = {o["tenant_id"] for o in listed.json()["orders"]}
    assert tenants == {"TENANT_A"}


def test_malformed_order_rejected(matching_client):
    bad = {**ORDER, "quantity": -5}
    resp = matching_client.post("/internal/orders", json=bad, headers=MEMBER_A)
    assert resp.status_code == 422


def test_missing_actor_headers_rejected(matching_client):
    resp = matching_client.post("/internal/orders", json=ORDER)
    assert resp.status_code == 401
