"""Gateway edge tests — auth proxy, order ACL, validation, rate limit."""

from __future__ import annotations

from helpers import auth_header, login

ORDER = {
    "symbol": "SYNTH",
    "side": "sell",
    "quantity": 3,
    "price": "99.10",
    "client_order_id": "gw-1",
}


def test_gateway_login_and_me(gateway_client):
    token = login(gateway_client, "member_a", "MemberA1!")
    me = gateway_client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["tenant_id"] == "TENANT_A"


def test_gateway_rejects_unauthenticated_order(gateway_client):
    resp = gateway_client.post("/orders", json=ORDER)
    assert resp.status_code == 401


def test_gateway_member_order_and_cross_tenant_denied(gateway_client):
    token_a = login(gateway_client, "member_a", "MemberA1!")
    created = gateway_client.post("/orders", json=ORDER, headers=auth_header(token_a))
    assert created.status_code == 201, created.text
    order_id = created.json()["order_id"]

    token_b = login(gateway_client, "member_b", "MemberB1!")
    denied = gateway_client.get(f"/orders/{order_id}", headers=auth_header(token_b))
    assert denied.status_code == 403


def test_gateway_analyst_cannot_modify_roles(gateway_client):
    token = login(gateway_client, "analyst", "Analyst1!")
    resp = gateway_client.patch(
        "/users/usr-member-a/role",
        headers=auth_header(token),
        json={"role": "administrator"},
    )
    assert resp.status_code == 403


def test_gateway_admin_role_change_audited(gateway_client):
    admin = login(gateway_client, "admin", "Admin1!lab")
    resp = gateway_client.patch(
        "/users/usr-member-b/role",
        headers=auth_header(admin),
        json={"role": "operations"},
    )
    assert resp.status_code == 200, resp.text
    assert "audit" in resp.json()
    assert resp.json()["audit"]["result"] == "ok"

    audit = gateway_client.get("/audit", headers=auth_header(admin))
    assert audit.status_code == 200
    assert any(r["action"] == "change_role" and r["result"] == "ok" for r in audit.json()["audit"])


def test_gateway_rejects_malformed_order(gateway_client):
    token = login(gateway_client, "member_a", "MemberA1!")
    bad = {**ORDER, "side": "hold"}
    resp = gateway_client.post("/orders", json=bad, headers=auth_header(token))
    assert resp.status_code == 422


def test_gateway_rejects_oversized_body(gateway_client):
    token = login(gateway_client, "member_a", "MemberA1!")
    huge = {**ORDER, "client_order_id": "x" * 20000}
    resp = gateway_client.post("/orders", json=huge, headers=auth_header(token))
    # Either content-length middleware (413) or pydantic max length (422)
    assert resp.status_code in {413, 422}


def test_gateway_rate_limits_member_orders(gateway_client):
    token = login(gateway_client, "member_a", "MemberA1!")
    statuses = []
    for i in range(6):
        payload = {**ORDER, "client_order_id": f"rate-{i}"}
        resp = gateway_client.post("/orders", json=payload, headers=auth_header(token))
        statuses.append(resp.status_code)
    assert 429 in statuses
    assert statuses.count(201) == 5


def test_gateway_analyst_cannot_submit_orders(gateway_client):
    token = login(gateway_client, "analyst", "Analyst1!")
    resp = gateway_client.post("/orders", json=ORDER, headers=auth_header(token))
    assert resp.status_code == 403
