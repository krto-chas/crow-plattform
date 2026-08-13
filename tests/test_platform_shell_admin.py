from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def _configure_identity(
    monkeypatch: pytest.MonkeyPatch,
    *,
    customer_id: str,
    roles: str = "",
    user_id: str = "test-user",
) -> None:
    monkeypatch.setenv("CROW_MODE", "server")
    monkeypatch.setenv("CROW_CUSTOMER_ID", customer_id)
    monkeypatch.setenv("CROW_USER_ID", user_id)
    monkeypatch.setenv("CROW_ROLES", roles)


def _write_entitlements(root: Path, customer_id: str, modules: list[dict[str, object]]) -> None:
    path = root / "config" / "customers" / customer_id / "entitlements.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"customer_id": customer_id, "modules": modules}), encoding="utf-8")


def test_platform_shell_replaces_domain_module_as_root(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    landing = client.get("/")
    legacy = client.get("/workbench")

    assert landing.status_code == 200
    assert "CROW PLATFORM" in landing.text
    assert legacy.status_code == 200
    assert "Crow" in legacy.text


def test_session_routes_customer_to_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_identity(monkeypatch, customer_id="acme")
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/session")

    assert response.status_code == 200
    assert response.json()["destination"] == "/app"
    assert response.json()["auth_mode"] == "environment"


def test_session_routes_platform_admin_to_admin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="crow-admin", roles="platform-admin")
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/session")

    assert response.status_code == 200
    assert response.json()["destination"] == "/admin"


def test_customer_cannot_open_admin_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="acme")
    client = TestClient(create_app(tmp_path))

    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_session_mode_requires_login_for_customer_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.delenv("CROW_CUSTOMER_ID", raising=False)
    client = TestClient(create_app(tmp_path))

    response = client.get("/app", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_endpoints_are_role_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="acme")
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/admin/customers")

    assert response.status_code == 403


def test_admin_can_create_customer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_identity(monkeypatch, customer_id="crow-admin", roles="platform-admin")
    client = TestClient(create_app(tmp_path))

    response = client.post("/api/admin/customers", json={"customer_id": "Acme_North"})

    assert response.status_code == 201
    assert response.json()["customer_id"] == "acme_north"
    stored = json.loads(
        (
            tmp_path / "config" / "customers" / "acme_north" / "entitlements.json"
        ).read_text(encoding="utf-8")
    )
    assert stored == {"customer_id": "acme_north", "modules": []}


def test_admin_cannot_create_duplicate_customer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="crow-admin", roles="platform-admin")
    _write_entitlements(tmp_path, "acme", [])
    client = TestClient(create_app(tmp_path))

    response = client.post("/api/admin/customers", json={"customer_id": "acme"})

    assert response.status_code == 409


def test_admin_can_update_customer_entitlements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="crow-admin", roles="platform-admin")
    _write_entitlements(tmp_path, "acme", [])
    client = TestClient(create_app(tmp_path))

    response = client.put(
        "/api/admin/customers/acme/entitlements",
        json={
            "modules": [
                {"id": "vent", "active": True, "valid_until": None},
                {"id": "provtryckning", "active": True, "valid_until": None},
                {"id": "ovk", "active": True, "valid_until": None},
                {"id": "injustering", "active": False, "valid_until": None},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    active = {item["id"] for item in payload["modules"] if item["active"]}
    assert active == {"vent", "provtryckning", "ovk"}

    stored = json.loads(
        (tmp_path / "config" / "customers" / "acme" / "entitlements.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored["customer_id"] == "acme"


def test_admin_rejects_missing_product_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="crow-admin", roles="platform-admin")
    client = TestClient(create_app(tmp_path))

    response = client.put(
        "/api/admin/customers/acme/entitlements",
        json={"modules": [{"id": "provtryckning", "active": True}]},
    )

    assert response.status_code == 400
    assert "requires active modules" in response.json()["detail"]


def test_customer_module_surface_is_driven_by_entitlements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="acme")
    _write_entitlements(
        tmp_path,
        "acme",
        [
            {"id": "vent", "active": True},
            {"id": "ovk", "active": True},
            {"id": "provtryckning", "active": False},
        ],
    )
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/me/modules")

    assert response.status_code == 200
    assert {module["id"] for module in response.json()["modules"]} == {"vent", "ovk"}


def test_admin_module_catalog_links_current_runtime_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_identity(monkeypatch, customer_id="crow-admin", roles="platform-admin")
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/admin/modules")

    assert response.status_code == 200
    modules = {module["id"]: module for module in response.json()["modules"]}
    assert modules["vent"]["runtime_module_id"] == "crow.vent"
    assert modules["provtryckning"]["runtime_module_id"] == "crow.provtryckning"
    assert modules["ovk"]["runtime_module_id"] == "crow.ovk"
