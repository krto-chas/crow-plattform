from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from crow_entitlements import load_customer_entitlements, load_product_module_catalog
from crow_workbench.shell import create_app


def _write_entitlements(root: Path, customer_id: str, modules: list[dict[str, object]]) -> None:
    target = root / "config" / "customers" / customer_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": customer_id, "modules": modules}),
        encoding="utf-8",
    )


def test_catalog_separates_data_dependencies_from_commercial_access() -> None:
    catalog = load_product_module_catalog()
    pressure = catalog.get("provtryckning")
    ovk = catalog.get("ovk")
    adjustment = catalog.get("injustering")
    assert pressure.data_dependencies == ("vent_model",)
    assert ovk.data_dependencies == ("vent_model",)
    assert adjustment.data_dependencies == ("vent_model",)
    assert adjustment.status.value == "planned"


def test_catalog_resolves_product_page_routes() -> None:
    catalog = load_product_module_catalog()
    assert catalog.module_for_route_path("/vent").id == "vent"  # type: ignore[union-attr]
    assert catalog.module_for_route_path("/provtryckning").id == "provtryckning"  # type: ignore[union-attr]
    assert catalog.module_for_route_path("/ovk").id == "ovk"  # type: ignore[union-attr]
    assert catalog.module_for_route_path("/app") is None


def test_catalog_resolves_legacy_vent_api_route_templates() -> None:
    catalog = load_product_module_catalog()
    checksum = "a" * 64
    paths = (
        "/api/projects/demo/takeoff",
        f"/api/projects/demo/vent/{checksum}",
        f"/api/projects/demo/vent/{checksum}/quantity.csv",
        f"/api/projects/demo/vent/{checksum}/review",
    )

    for path in paths:
        module = catalog.module_for_api_path(path)
        assert module is not None
        assert module.id == "vent"

    assert catalog.module_for_api_path("/api/projects") is None
    assert catalog.module_for_api_path("/api/projects/demo") is None
    assert catalog.module_for_api_path("/api/projects/demo/imports") is None


def test_missing_entitlement_file_fails_closed(tmp_path: Path) -> None:
    catalog = load_product_module_catalog()
    entitlements = load_customer_entitlements(tmp_path / "config", "acme", catalog=catalog)
    assert entitlements.entries == ()
    assert not entitlements.has_active_module("vent", today=date(2026, 8, 8))


def test_me_modules_returns_only_active_entitled_modules(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _write_entitlements(
        tmp_path,
        "acme",
        [
            {"id": "vent", "active": True, "valid_until": None},
            {"id": "ovk", "active": True, "valid_until": "2020-01-01"},
            {"id": "injustering", "active": True, "valid_until": None},
        ],
    )
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/me/modules")
    assert response.status_code == 200
    modules = response.json()["modules"]
    assert [item["id"] for item in modules] == ["vent"]
    assert "/api/projects/{project_id}/takeoff" in modules[0]["api_routes"]


def test_module_api_is_denied_without_entitlement(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/vent/registry")
    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "vent"}


def test_legacy_vent_api_is_denied_without_entitlement(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/projects/adhoc/takeoff",
        json={"table_rows": [["T-125", "10", "m"]]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "vent"}


def test_module_api_is_available_with_entitlement(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _write_entitlements(tmp_path, "acme", [{"id": "vent", "active": True}])
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/vent/registry")
    assert response.status_code == 200


def test_legacy_vent_api_is_available_with_entitlement(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _write_entitlements(tmp_path, "acme", [{"id": "vent", "active": True}])
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/projects/adhoc/takeoff",
        json={"table_rows": [["T-125", "10", "m"]]},
    )

    assert response.status_code == 200
    assert response.json()["consolidated"]["line_count"] == 1


def test_module_page_redirects_without_entitlement(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))

    response = client.get("/vent", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_module_navigation_only_lists_effective_entitlements(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _write_entitlements(tmp_path, "acme", [{"id": "ovk", "active": True}])
    client = TestClient(create_app(tmp_path))

    response = client.get("/ovk")

    assert response.status_code == 200
    assert "OVK-arbetsyta" in response.text
    assert '<a href="/app">Projekt</a>' in response.text
    assert '<a class="active" href="/ovk">OVK</a>' in response.text
    assert '<a href="/logout">Logga ut</a>' in response.text
    assert 'href="/vent"' not in response.text
    assert 'href="/provtryckning"' not in response.text


def test_shared_api_remains_available_without_module_entitlement(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/projects")
    assert response.status_code == 200


def test_server_mode_requires_customer_identity(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "environment")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_MODE", "server")  # type: ignore[attr-defined]
    monkeypatch.delenv("CROW_CUSTOMER_ID", raising=False)  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/me/modules")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "CUSTOMER_CONTEXT_UNAVAILABLE"
