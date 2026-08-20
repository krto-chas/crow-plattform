from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def test_workbench_injects_product_bridge(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/workbench?project_id=demo")

    assert response.status_code == 200
    assert '<script src="/static/workbench-product-bridge.js"></script>' in response.text


def test_workbench_product_bridge_routes_vent_out_of_legacy_view(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/static/workbench-product-bridge.js")

    assert response.status_code == 200
    assert "window.renderVent = () => {}" in response.text
    assert "ventProductRail" in response.text
    assert "openVentProduct" in response.text
    assert "project_id" in response.text
