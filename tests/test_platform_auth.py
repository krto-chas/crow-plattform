from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_entitlements.auth import UserRecord, hash_password, write_user
from crow_workbench.shell import create_app


def _write_user(root: Path, username: str, customer_id: str, roles: tuple[str, ...]) -> None:
    salt, digest = hash_password("correct-horse-battery-staple")
    write_user(
        root / "config",
        UserRecord(
            username=username,
            customer_id=customer_id,
            roles=roles,
            password_salt=salt,
            password_hash=digest,
        ),
    )


def _session_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.setenv("CROW_SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("CROW_COOKIE_SECURE", "false")
    monkeypatch.delenv("CROW_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("CROW_USER_ID", raising=False)
    monkeypatch.delenv("CROW_ROLES", raising=False)


def test_session_mode_root_shows_login_when_unauthenticated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    client = TestClient(create_app(tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "Logga in" in response.text


def test_customer_login_routes_to_customer_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    _write_user(tmp_path, "anna", "acme", ())
    client = TestClient(create_app(tmp_path))

    login = client.post(
        "/api/auth/login",
        json={"username": "anna", "password": "correct-horse-battery-staple"},
    )
    session = client.get("/api/session")

    assert login.status_code == 200
    assert login.json()["destination"] == "/app"
    assert session.status_code == 200
    assert session.json()["customer_id"] == "acme"
    assert session.json()["user_id"] == "anna"


def test_admin_login_routes_to_admin_and_unlocks_admin_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    _write_user(tmp_path, "admin", "crow-admin", ("platform-admin",))
    client = TestClient(create_app(tmp_path))

    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "correct-horse-battery-staple"},
    )
    admin = client.get("/api/admin/modules")

    assert login.status_code == 200
    assert login.json()["destination"] == "/admin"
    assert admin.status_code == 200


def test_wrong_password_does_not_create_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    _write_user(tmp_path, "anna", "acme", ())
    client = TestClient(create_app(tmp_path))

    login = client.post("/api/auth/login", json={"username": "anna", "password": "wrong-password"})
    session = client.get("/api/session")

    assert login.status_code == 401
    assert session.status_code == 401


def test_environment_identity_remains_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "environment")
    monkeypatch.setenv("CROW_MODE", "server")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "legacy")
    monkeypatch.setenv("CROW_USER_ID", "legacy-user")
    monkeypatch.setenv("CROW_ROLES", "")
    client = TestClient(create_app(tmp_path))

    session = client.get("/api/session")

    assert session.status_code == 200
    assert session.json()["customer_id"] == "legacy"
