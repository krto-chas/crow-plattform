from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_entitlements.auth import UserRecord, hash_password, write_user
from crow_workbench.shell import create_app


def _admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_MODE", "server")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "crow-admin")
    monkeypatch.setenv("CROW_USER_ID", "admin")
    monkeypatch.setenv("CROW_ROLES", "platform-admin")


def _customer(root: Path, customer_id: str) -> None:
    path = root / "config" / "customers" / customer_id / "entitlements.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"customer_id": customer_id, "modules": []}), encoding="utf-8")


def _user(root: Path, username: str, customer_id: str) -> None:
    salt, digest = hash_password("correct-horse-battery-staple")
    write_user(
        root / "config",
        UserRecord(
            username=username,
            customer_id=customer_id,
            roles=(),
            password_salt=salt,
            password_hash=digest,
        ),
    )


def test_customer_creation_is_audited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _admin(monkeypatch)
    client = TestClient(create_app(tmp_path))

    assert client.post("/api/admin/customers", json={"customer_id": "acme"}).status_code == 201
    response = client.get("/api/admin/audit")

    assert response.status_code == 200
    event = response.json()["events"][0]
    assert event["action"] == "customer.created"
    assert event["actor_user_id"] == "admin"
    assert event["target_id"] == "acme"


def test_entitlement_update_is_audited_with_before_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _admin(monkeypatch)
    _customer(tmp_path, "acme")
    client = TestClient(create_app(tmp_path))

    response = client.put(
        "/api/admin/customers/acme/entitlements",
        json={"modules": [{"id": "vent", "active": True}]},
    )
    assert response.status_code == 200

    event = client.get("/api/admin/audit").json()["events"][0]
    assert event["action"] == "entitlements.updated"
    assert event["before"]["modules"] == []
    assert event["after"]["modules"][0]["id"] == "vent"


def test_user_password_material_never_enters_audit_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _admin(monkeypatch)
    _customer(tmp_path, "acme")
    _user(tmp_path, "alice", "acme")
    client = TestClient(create_app(tmp_path))

    response = client.put(
        "/api/admin/users/alice",
        json={
            "customer_id": "acme",
            "roles": [],
            "active": True,
            "password": "another-correct-horse-password",
        },
    )
    assert response.status_code == 200

    audit_text = (tmp_path / "config" / "audit" / "events.jsonl").read_text(encoding="utf-8")
    assert "another-correct-horse-password" not in audit_text
    assert "password_hash" not in audit_text
    assert "password_salt" not in audit_text
    event = client.get("/api/admin/audit").json()["events"][0]
    assert event["after"]["password_changed"] is True


def test_non_admin_cannot_read_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_MODE", "server")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    monkeypatch.setenv("CROW_ROLES", "")
    client = TestClient(create_app(tmp_path))

    assert client.get("/api/admin/audit").status_code == 403
    response = client.get("/admin/audit", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"
