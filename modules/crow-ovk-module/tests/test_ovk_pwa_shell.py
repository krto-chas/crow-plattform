from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router


def test_field_pwa_shell_and_manifest() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    client = TestClient(app)

    page = client.get("/ovk/falt")
    assert page.status_code == 200
    assert 'rel="manifest" href="/ovk/falt/manifest.webmanifest"' in page.text
    assert 'name="apple-mobile-web-app-capable" content="yes"' in page.text
    assert "safe-area-inset-top" in page.text
    assert "safe-area-inset-bottom" in page.text
    # iPhone: helskärm kräver start från hemskärmen, så sidan visar en anvisning i Safari.
    assert 'id="ovkInstallHint"' in page.text
    assert "Lägg till på hemskärmen" in page.text
    assert "navigator.standalone===true" in page.text

    response = client.get("/ovk/falt/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    assert response.headers["cache-control"] == "no-cache"
    manifest = response.json()
    assert manifest["display"] == "standalone"
    assert manifest["display_override"] == ["fullscreen", "standalone"]
    assert manifest["start_url"] == "/ovk/falt"
    assert manifest["scope"] == "/ovk/"
    assert manifest["icons"][0]["src"] == "/ovk/falt/icon.svg"

    icon = client.get("/ovk/falt/icon.svg")
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in icon.text
