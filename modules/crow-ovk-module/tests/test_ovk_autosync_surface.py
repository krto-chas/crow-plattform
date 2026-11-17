from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router


def test_autosync_runtime_and_visible_status() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    client = TestClient(app)

    page = client.get("/ovk/falt")
    assert page.status_code == 200
    assert 'id="fieldSyncIndicator"' in page.text
    assert 'aria-live="polite"' in page.text

    auth = client.get("/ovk/falt/auth.js")
    assert auth.status_code == 200
    script = auth.text
    assert "const CROW_AUTO_DELAY_MS = 8000;" in script
    assert "const CROW_AUTO_INTERVAL_MS = 60000;" in script
    assert "crowSyncInFlight" in script
    assert "crowEditVersion === version" in script
    assert "await writeDraft(true);" in script
    assert "window.addEventListener('online'" in script
    assert "document.addEventListener('visibilitychange'" in script
    assert "OVK_FIELD_REVISION_CONFLICT" in script
    assert "$('sync').onclick = syncDraft;" in script
