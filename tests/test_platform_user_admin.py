from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_entitlements.auth import UserRecord, hash_password, load_user, write_user
from crow_workbench.shell import create_app


def _configure_admin(monkeypatch: pytest.MonkeyPatch, *, user_id: str = "admin") -> None:
    monkeypatch.setenv("CROW_MODE", "server")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "crow-admin")
    monkeypatch.setenv("CROW_USER_ID", user_id)
    monkeypatch.setenv("CROW_ROLES", "platform-admin")


def _write_customer(root: Path, customer_id: str) -> None:
    target = root / "config" / "customers" / customer_id / "entitlements.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"customer_id": customer_id, "modules": []}),
        encoding="utf-8",
    )


def _write_user(root: Path, username: str, customer_id: str, *, active: bool = True) -> UserRecord:
    salt, digest = hash_password("correct-horse-battery-staple")
    user = UserRecord(
        username=username,
        customer_id=customer_id,
        roles=(),
        password_salt=salt,
        password_hash=digest,
        active=active,
    )
    write_user(root / "config", user)
    return user


def test_admin_can_create_customer_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_admin(monkeypatch)
    _write_customer(tmp_path, "acme")
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/admin/users",
        json={
            "username": "Alice",
            "customer_id": "acme",
            "password": "long-enough-password",
            "roles": [],
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "username": "alice",
        "customer_id": "acme",
        "roles": [],
        "active": True,
    }
    stored = load_user(tmp_path / "config", "alice")
    assert stored is not None
    assert stored.password_hash != "long-enough-password"


def test_admin_user_api_never_exposes_password_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_admin(monkeypatch)
    _write_customer(tmp_path, "acme")
    _write_user(tmp_path, "alice", "acme")
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/admin/users")

    assert response.status_code == 200
    payload = response.json()["users"][0]
    assert payload == {
        "username": "alice",
        "customer_id": "acme",
        "roles": [],
        "active": True,
    }
    assert "password_hash" not in payload
    assert "password_salt" not in payload


def test_admin_can_disable_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_admin(monkeypatch)
    _write_customer(tmp_path, "acme")
    _write_user(tmp_path, "alice", "acme")
    client = TestClient(create_app(tmp_path))

    response = client.put(
        "/api/admin/users/alice",
        json={"customer_id": "acme", "roles": [], "active": False},
    )

    assert response.status_code == 200
    assert response.json()["active"] is False
    stored = load_user(tmp_path / "config", "alice")
    assert stored is not None
    assert stored.active is False


def test_non_admin_cannot_manage_users(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_MODE", "server")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    monkeypatch.setenv("CROW_ROLES", "")
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/admin/users")

    assert response.status_code == 403


def test_customer_user_requires_existing_customer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_admin(monkeypatch)
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/admin/users",
        json={
            "username": "alice",
            "customer_id": "missing",
            "password": "long-enough-password",
            "roles": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Customer does not exist"


def test_disabled_user_loses_existing_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.setenv("CROW_SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("CROW_COOKIE_SECURE", "false")
    _write_customer(tmp_path, "acme")
    user = _write_user(tmp_path, "alice", "acme")
    client = TestClient(create_app(tmp_path))

    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    assert client.get("/api/session").status_code == 200

    disabled = UserRecord(
        username=user.username,
        customer_id=user.customer_id,
        roles=user.roles,
        password_salt=user.password_salt,
        password_hash=user.password_hash,
        active=False,
    )
    write_user(tmp_path / "config", disabled, overwrite=True)

    response = client.get("/api/session")

    assert response.status_code == 401


def test_role_change_invalidates_existing_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.setenv("CROW_SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("CROW_COOKIE_SECURE", "false")
    _write_customer(tmp_path, "acme")
    user = _write_user(tmp_path, "alice", "acme")
    client = TestClient(create_app(tmp_path))

    assert (
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-horse-battery-staple"},
        ).status_code
        == 200
    )

    changed = UserRecord(
        username=user.username,
        customer_id=user.customer_id,
        roles=("auditor",),
        password_salt=user.password_salt,
        password_hash=user.password_hash,
        active=True,
    )
    write_user(tmp_path / "config", changed, overwrite=True)

    response = client.get("/api/session")

    assert response.status_code == 401
