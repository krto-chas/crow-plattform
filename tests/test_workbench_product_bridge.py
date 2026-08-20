from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def test_workbench_serves_unified_project_workspace(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/workbench?project_id=demo")

    assert response.status_code == 200
    assert "Projekt &amp; Workbench" in response.text
    assert "/static/product.css" in response.text
    assert "/static/workbench-home.js" in response.text
    assert "/workbench/advanced" in response.text


def test_advanced_workbench_injects_product_bridge(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/workbench/advanced?project_id=demo&view=cad")

    assert response.status_code == 200
    assert '<script src="/static/workbench-product-bridge.js"></script>' in response.text


def test_workbench_product_bridge_routes_vent_out_of_legacy_view(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/static/workbench-product-bridge.js")

    assert response.status_code == 200
    assert "window.renderVent = () => {}" in response.text
    assert "ventProductRail" in response.text
    assert "openVentProduct" in response.text
    assert "requestedView" in response.text
    assert "window.switchView(requestedView)" in response.text


def test_workbench_requires_login_in_session_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.delenv("CROW_CUSTOMER_ID", raising=False)
    client = TestClient(create_app(tmp_path))

    home = client.get("/workbench", follow_redirects=False)
    advanced = client.get("/workbench/advanced", follow_redirects=False)

    assert home.status_code == 303
    assert home.headers["location"] == "/login"
    assert advanced.status_code == 303
    assert advanced.headers["location"] == "/login"
