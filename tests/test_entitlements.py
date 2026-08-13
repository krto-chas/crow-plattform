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
    assert [item["id"] for item in response.json()["modules"]] == ["vent"]


def test_module_api_is_denied_without_entitlement(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/vent/registry")
    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "vent"}


def test_module_api_is_available_with_entitlement(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _write_entitlements(tmp_path, "acme", [{"id": "vent", "active": True}])
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/vent/registry")
    assert response.status_code == 200


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
