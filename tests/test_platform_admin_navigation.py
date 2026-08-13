from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_entitlements.auth import UserRecord, hash_password, write_user
from crow_workbench.shell import create_app


def _session_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.setenv("CROW_SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.delenv("CROW_SESSION_SECRET_FILE", raising=False)
    monkeypatch.setenv("CROW_COOKIE_SECURE", "false")
    monkeypatch.delenv("CROW_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("CROW_USER_ID", raising=False)
    monkeypatch.delenv("CROW_ROLES", raising=False)


def _write_user(
    root: Path,
    username: str,
    customer_id: str,
    roles: tuple[str, ...],
) -> None:
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


def _login_admin(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200
    assert response.json()["destination"] == "/admin"


def test_session_admin_can_open_complete_admin_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    _write_user(tmp_path, "admin", "crow-admin", ("platform-admin",))
    client = TestClient(create_app(tmp_path))
    _login_admin(client)

    home = client.get("/admin")
    access = client.get("/admin?view=access")
    users = client.get("/admin/users")
    audit = client.get("/admin/audit")

    assert home.status_code == 200
    assert "Administrationscenter" in home.text
    assert 'href="/admin?view=access"' in home.text
    assert 'href="/admin/users"' in home.text
    assert 'href="/admin/audit"' in home.text
    assert access.status_code == 200
    assert "CROW PLATFORM" in access.text
    assert users.status_code == 200
    assert "Användare" in users.text
    assert audit.status_code == 200
    assert "Audit" in audit.text


def test_non_admin_session_is_redirected_from_admin_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    _write_user(tmp_path, "anna", "acme", ())
    client = TestClient(create_app(tmp_path))
    login = client.post(
        "/api/auth/login",
        json={"username": "anna", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200

    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_current_admin_cannot_remove_own_admin_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    _write_user(tmp_path, "admin", "crow-admin", ("platform-admin",))
    customer = tmp_path / "config" / "customers" / "crow-admin" / "entitlements.json"
    customer.parent.mkdir(parents=True, exist_ok=True)
    customer.write_text('{"customer_id":"crow-admin","modules":[]}\n', encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    _login_admin(client)

    response = client.put(
        "/api/admin/users/admin",
        json={"customer_id": "crow-admin", "roles": [], "active": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Cannot remove platform-admin from the current administrator"
    )
    assert client.get("/api/session").status_code == 200
