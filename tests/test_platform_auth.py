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
    monkeypatch.delenv("CROW_SESSION_SECRET_FILE", raising=False)
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


def test_session_secret_file_supports_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.delenv("CROW_SESSION_SECRET", raising=False)
    secret_file = tmp_path / "session-secret"
    secret_file.write_text("0123456789abcdef0123456789abcdef\n", encoding="utf-8")
    monkeypatch.setenv("CROW_SESSION_SECRET_FILE", str(secret_file))
    monkeypatch.setenv("CROW_COOKIE_SECURE", "false")
    monkeypatch.delenv("CROW_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("CROW_USER_ID", raising=False)
    monkeypatch.delenv("CROW_ROLES", raising=False)
    _write_user(tmp_path, "anna", "acme", ())
    client = TestClient(create_app(tmp_path))

    login = client.post(
        "/api/auth/login",
        json={"username": "anna", "password": "correct-horse-battery-staple"},
    )

    assert login.status_code == 200
    assert login.json()["customer_id"] == "acme"


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


def test_session_boundary_blocks_private_routes_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    app = create_app(tmp_path)
    client = TestClient(app)

    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/") or path == "/api/auth/login":
            continue
        for method in getattr(route, "methods", set()) or set():
            response = client.request(method, path, follow_redirects=False)
            assert response.status_code == 401, (method, path, response.text)
            assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"

    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert client.get(path, follow_redirects=False).status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.post("/api/auth/login", json={}).status_code == 422
    assert client.get("/api/auth/login").status_code == 401
    assert client.post("/health").status_code == 401
    client.cookies.set("crow_session", "invalid")
    assert client.get("/api/projects").status_code == 401
    client.cookies.clear()

    @app.get("/future-private-route")
    def future_route() -> dict[str, bool]:
        return {"private": True}

    assert client.get("/future-private-route", follow_redirects=False).status_code == 303


def test_authenticated_session_can_use_core_projects_and_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _session_mode(monkeypatch)
    _write_user(tmp_path, "anna", "acme", ())
    client = TestClient(create_app(tmp_path))
    blocked = client.post("/api/projects", json={"name": "Blocked", "project_id": "blocked"})
    assert blocked.status_code == 401
    login = client.post(
        "/api/auth/login",
        json={"username": "anna", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    assert client.get("/api/projects").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    allowed = client.post("/api/projects", json={"name": "Allowed", "project_id": "allowed"})
    assert allowed.status_code in {200, 201}
    assert not (tmp_path / "projects" / "blocked").exists()
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/projects").status_code == 401
