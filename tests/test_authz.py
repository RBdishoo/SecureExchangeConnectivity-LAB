"""Identity authorization tests — login, RBAC, admin audit, negatives."""

from __future__ import annotations

from helpers import auth_header, login


def test_login_success(identity_client):
    token = login(identity_client, "member_a", "MemberA1!")
    assert token


def test_login_failure(identity_client):
    resp = identity_client.post(
        "/auth/login", json={"username": "member_a", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_me_requires_auth(identity_client):
    assert identity_client.get("/auth/me").status_code == 401


def test_me_with_token(identity_client):
    token = login(identity_client, "analyst", "Analyst1!")
    resp = identity_client.get("/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "security_analyst"


def test_member_cannot_list_users(identity_client):
    token = login(identity_client, "member_a", "MemberA1!")
    resp = identity_client.get("/users", headers=auth_header(token))
    assert resp.status_code == 403


def test_analyst_cannot_modify_roles(identity_client):
    token = login(identity_client, "analyst", "Analyst1!")
    resp = identity_client.patch(
        "/users/usr-member-a/role",
        headers=auth_header(token),
        json={"role": "administrator"},
    )
    assert resp.status_code == 403
    assert "administrator" in resp.json()["detail"].lower() or "Only administrators" in resp.json()["detail"]

    # Denied attempt is audited
    admin_token = login(identity_client, "admin", "Admin1!lab")
    audit = identity_client.get("/audit", headers=auth_header(admin_token))
    assert audit.status_code == 200
    denied = [r for r in audit.json()["audit"] if r["result"] == "denied" and r["action"] == "change_role"]
    assert denied, "expected denied change_role audit record"


def test_admin_role_change_creates_audit(identity_client):
    admin_token = login(identity_client, "admin", "Admin1!lab")
    resp = identity_client.patch(
        "/users/usr-ops/role",
        headers=auth_header(admin_token),
        json={"role": "security_analyst"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "security_analyst"
    audit_record = resp.json()["audit"]
    assert audit_record["action"] == "change_role"
    assert audit_record["result"] == "ok"
    assert audit_record["detail"]["previous_role"] == "operations"
    assert audit_record["detail"]["new_role"] == "security_analyst"

    listed = identity_client.get("/audit", headers=auth_header(admin_token))
    assert any(r["audit_id"] == audit_record["audit_id"] for r in listed.json()["audit"])


def test_member_cannot_read_audit(identity_client):
    token = login(identity_client, "member_a", "MemberA1!")
    assert identity_client.get("/audit", headers=auth_header(token)).status_code == 403


def test_roles_endpoint_requires_auth(identity_client):
    assert identity_client.get("/roles").status_code == 401
