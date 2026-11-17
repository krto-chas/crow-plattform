"""Regressionstester för granskningsfynden i november 2026.

Täcker: återställning av avbrutet utfärdande, årsrapportens CSV-rutt,
kontrollerat avslag för trasiga legacyfiler, storleksgräns på legacyuppladdning
och att låsvakten inte skapar kataloger åt okända projekt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from crow_ovk_legacy import preview_legacy_file
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from test_ovk_intyg_integrity import _BASE, _INTYG_BODY, _ready_client
from test_ovk_workflow import _workflow_payload

from crow_ovk_intyg import OvkIntyg, OvkIntygRepository
from crow_ovk_module import ovk_legacy_surface
from crow_ovk_module.ovk_legacy_surface import ovk_legacy_router
from crow_ovk_module.ovk_reporting_surface import ovk_reporting_router
from crow_ovk_module.ovk_workflow_surface import ovk_workflow_router

_MANIFEST = Path("projects") / "p1" / "ovk-issuance-manifest" / "ovk-001.json"
_PROFILE = {
    "inspector_name": "Stina Kontrollant",
    "certification_body": "RISE",
    "certificate_number": "K-12345",
    "authorization": "K",
    "reporting_period_start": "2026-01-01",
    "reporting_period_end": "2026-12-31",
}


def _interrupt_issuance(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    """Låter manifestet publiceras men intygsskrivningen fallera en gång."""
    original = OvkIntygRepository.save

    def failing_save(self: OvkIntygRepository, intyg: OvkIntyg) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(OvkIntygRepository, "save", failing_save)
    with pytest.raises(OSError):
        client.post(_BASE + "/intyg", json=_INTYG_BODY)
    monkeypatch.setattr(OvkIntygRepository, "save", original)


def test_interrupted_issuance_can_be_recovered(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    _interrupt_issuance(client, monkeypatch)
    manifest_bytes = (tmp_path / _MANIFEST).read_bytes()
    assert client.get("/api/ovk/projects/p1/intyg").json()["intyg"] == []

    blocked = client.post(_BASE + "/intyg", json=_INTYG_BODY)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "OVK_ISSUANCE_RECOVERY_REQUIRED"

    recovered = client.post(_BASE + "/intyg/recover", json=_INTYG_BODY)
    assert recovered.status_code == 200, recovered.text
    body = recovered.json()
    assert body["recovered"] is True
    assert body["intyg_id"] == "intyg-001"
    assert (tmp_path / _MANIFEST).read_bytes() == manifest_bytes
    status = client.get("/api/ovk/projects/p1/intyg/intyg-001/status")
    assert status.json() == {"status": "current"}

    # Idempotent, och besiktningen är därefter låst som vid vanligt utfärdande.
    again = client.post(_BASE + "/intyg/recover", json=_INTYG_BODY)
    assert again.status_code == 200, again.text
    assert client.put(_BASE, json=_workflow_payload()).status_code == 409


def test_recovery_refuses_anything_but_the_reviewed_certificate(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    _interrupt_issuance(client, monkeypatch)

    changed: dict[str, Any] = {**_INTYG_BODY, "byggnadsagare_name": "Annan Ägare AB"}
    response = client.post(_BASE + "/intyg/recover", json=changed)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_ISSUANCE_RECOVERY_INVALID"

    renamed: dict[str, Any] = {**_INTYG_BODY, "intyg_id": "intyg-002"}
    response = client.post(_BASE + "/intyg/recover", json=renamed)
    assert response.status_code == 409
    assert client.get("/api/ovk/projects/p1/intyg").json()["intyg"] == []


def test_recovery_requires_a_valid_manifest(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    response = client.post(_BASE + "/intyg/recover", json=_INTYG_BODY)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_ISSUANCE_NOTHING_TO_RECOVER"

    path = tmp_path / _MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    response = client.post(_BASE + "/intyg/recover", json=_INTYG_BODY)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_ISSUANCE_RECOVERY_INVALID"
    assert client.get("/api/ovk/projects/p1/intyg").json()["intyg"] == []


def test_annual_report_csv_route_is_reachable(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_reporting_router(tmp_path))
    client = TestClient(app)
    saved = client.put("/api/ovk/reporting/certification/prof1", json=_PROFILE)
    assert saved.status_code == 200, saved.text

    csv_response = client.get("/api/ovk/reporting/annual/prof1.csv")
    assert csv_response.status_code == 200, csv_response.text
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "certificate_number,K-12345" in csv_response.text

    json_response = client.get("/api/ovk/reporting/annual/prof1")
    assert json_response.status_code == 200
    assert json_response.json()["profile_id"] == "prof1"


@pytest.mark.parametrize("filename", ["trasig.pdf", "trasig.xlsx"])
def test_unreadable_legacy_file_is_rejected_as_value_error(filename: str) -> None:
    with pytest.raises(ValueError, match="Unreadable legacy OVK file"):
        preview_legacy_file("p1", filename, b"%PDF-1.4 avbruten")


def test_legacy_upload_rejects_broken_and_oversized_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = FastAPI()
    app.include_router(ovk_legacy_router(tmp_path))
    client = TestClient(app)

    broken = client.post(
        "/api/ovk/legacy/preview",
        data={"project_id": "p1"},
        files={"file": ("trasig.pdf", b"%PDF-1.4 avbruten")},
    )
    assert broken.status_code == 415
    assert broken.json()["detail"]["code"] == "UNSUPPORTED_LEGACY_OVK_FILE"

    monkeypatch.setattr(ovk_legacy_surface, "_MAX_LEGACY_BYTES", 16)
    oversized = client.post(
        "/api/ovk/legacy/preview",
        data={"project_id": "p1"},
        files={"file": ("stor.pdf", b"x" * 17)},
    )
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "LEGACY_OVK_FILE_TOO_LARGE"


def test_mutation_guard_never_creates_project_directory_for_unknown_project(
    tmp_path: Path,
) -> None:
    app = FastAPI()
    app.include_router(ovk_workflow_router(tmp_path))
    client = TestClient(app)
    response = client.put(
        "/api/ovk/projects/okant-projekt/inspections/ovk-001", json={"inspection": "ogiltig"}
    )
    assert response.status_code == 422
    assert not (tmp_path / "projects").exists()
    # Låset tas alltid, även för första begäran, men utanför projektkatalogen.
    assert (tmp_path / "ovk-issuance-lock" / "okant-projekt" / "ovk-001.sqlite3").is_file()


def test_inspection_named_intyg_cannot_bypass_issued_lock(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    base = "/api/ovk/projects/p1/inspections/intyg"
    assert client.put(base, json=_workflow_payload()).status_code == 200
    body: dict[str, Any] = {**_INTYG_BODY, "intyg_id": "intyg-009"}
    preview = client.post(base + "/intyg/preview", json=body)
    assert preview.status_code == 200, preview.text
    revision = preview.headers["X-OVK-Review-Revision"]
    review = client.post(
        base + "/intyg/review", json=body, headers={"X-OVK-Review-Revision": revision}
    )
    assert review.status_code == 200, review.text
    assert client.post(base + "/intyg", json=body).status_code == 200
    blocked = client.put(base, json=_workflow_payload())
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "OVK_INSPECTION_ISSUED"


def test_recovery_rejects_invalid_body_and_foreign_certificate(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    _interrupt_issuance(client, monkeypatch)
    broken = client.post(
        _BASE + "/intyg/recover",
        content=b"{inte json",
        headers={"content-type": "application/json"},
    )
    assert broken.status_code == 422

    # Ett annat intyg för samma besiktning får aldrig samexistera med återställningen.
    directory = tmp_path / "projects" / "p1" / "ovk-intyg"
    assert client.post(_BASE + "/intyg/recover", json=_INTYG_BODY).status_code == 200
    stored = json.loads((directory / "intyg-001.json").read_text(encoding="utf-8"))
    (directory / "intyg-001.json").unlink()
    stored["intyg_id"] = "intyg-annat"
    (directory / "intyg-annat.json").write_text(json.dumps(stored), encoding="utf-8")
    response = client.post(_BASE + "/intyg/recover", json=_INTYG_BODY)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_ISSUANCE_RECOVERY_INVALID"
    assert not (directory / "intyg-001.json").exists()


def test_recovery_refuses_changed_workflow_basis(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    _interrupt_issuance(client, monkeypatch)
    path = tmp_path / "projects" / "p1" / "ovk" / "ovk-001.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["inspection"]["checkpoints"][0]["note"] = "ändrad efter granskning"
    path.write_text(json.dumps(record), encoding="utf-8")
    response = client.post(_BASE + "/intyg/recover", json=_INTYG_BODY)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_ISSUANCE_RECOVERY_INVALID"
    assert client.get("/api/ovk/projects/p1/intyg").json()["intyg"] == []


def test_profile_identifier_cannot_shadow_csv_route(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_reporting_router(tmp_path))
    client = TestClient(app)
    response = client.put("/api/ovk/reporting/certification/prof1.csv", json=_PROFILE)
    assert response.status_code == 422
