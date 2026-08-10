from __future__ import annotations

import io
import json
import time
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from pytest import MonkeyPatch

from crow_ovk import (
    CheckStatus,
    FindingSeverity,
    OvkCheckpoint,
    OvkFinding,
    OvkObject,
    VentilationSystemRef,
)
from crow_ovk_export import (
    ExportSignatureError,
    intyg_pdf,
    protocol_pdf,
    sign_export_path,
    verify_export_signature,
)
from crow_ovk_intyg import (
    Behorighet,
    Byggnadsagare,
    Funktionskontrollant,
    OvkIntyg,
    OvkIntygRepository,
    build_intyg,
)
from crow_ovk_pricing import BuildingCategory, InspectionType
from crow_ovk_workflow import (
    OvkReviewDecision,
    OvkWorkflowRecord,
    OvkWorkflowRepository,
    ReviewStatus,
    build_record,
)
from crow_workbench.shell import create_app

_SECRET = "test-signing-secret"


def _record(
    *,
    approved: bool = True,
    review_status: ReviewStatus = ReviewStatus.ACCEPTED,
) -> OvkWorkflowRecord:
    findings: tuple[OvkFinding, ...] = ()
    if not approved:
        findings = (
            OvkFinding(
                finding_id="f1",
                description="Otillräckligt frånluftsflöde i kök",
                severity=FindingSeverity.MAJOR,
                system_id="FTX01",
            ),
        )
    return build_record(
        inspection_id="ovk-001",
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="p1",
            building_id="building-1",
            name="Testobjekt",
            address="Bergvägen 1",
        ),
        systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="cp1",
                label="Drift och funktion",
                status=CheckStatus.PASS if approved else CheckStatus.FAIL,
                system_id="FTX01",
            ),
        ),
        findings=findings,
        review=(
            OvkReviewDecision(
                observation_id="o1",
                source_text="B1 FTX01 34 l/s 40 l/s",
                evidence_ref="doc#page=1",
                reason="unlabelled_airflow_value",
                status=review_status,
                reviewer="tester",
            ),
        ),
    )


def _intyg() -> OvkIntyg:
    return build_intyg(
        intyg_id="intyg-001",
        record=_record(),
        fastighetsbeteckning="Berghällen 1:2",
        byggnadsagare=Byggnadsagare(name="Brf Berghällen"),
        funktionskontrollant=Funktionskontrollant(
            name="Stina Kontrollant",
            behorighet=Behorighet.K,
            certification_body="RISE",
            certificate_number="K-12345",
        ),
        inspection_type=InspectionType.ATERKOMMANDE,
        inspection_date=date(2026, 8, 1),
        building_category=BuildingCategory.FLERBOSTADSHUS,
    )


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_sign_and_verify_roundtrip() -> None:
    path = "/api/ovk/export/p1/intyg/intyg-001.pdf"
    expires = 2_000_000_000
    signature = sign_export_path(_SECRET, path, expires)
    verify_export_signature(_SECRET, path, expires, signature, now_epoch=expires - 10)


def test_verify_rejects_tampered_path_signature_and_expiry() -> None:
    path = "/api/ovk/export/p1/intyg/intyg-001.pdf"
    expires = 2_000_000_000
    signature = sign_export_path(_SECRET, path, expires)
    with pytest.raises(ExportSignatureError, match="invalid"):
        verify_export_signature(
            _SECRET,
            "/api/ovk/export/p1/intyg/intyg-002.pdf",
            expires,
            signature,
            now_epoch=expires - 10,
        )
    with pytest.raises(ExportSignatureError, match="invalid"):
        verify_export_signature(
            _SECRET, path, expires, signature[:-1] + "0", now_epoch=expires - 10
        )
    with pytest.raises(ExportSignatureError, match="expired"):
        verify_export_signature(_SECRET, path, expires, signature, now_epoch=expires + 1)
    with pytest.raises(ExportSignatureError, match="invalid"):
        verify_export_signature("annan-nyckel", path, expires, signature, now_epoch=expires - 10)


def test_protocol_pdf_contains_core_content() -> None:
    content = protocol_pdf(_record(approved=False))
    assert content.startswith(b"%PDF")
    text = _pdf_text(content)
    assert "OVK-PROTOKOLL" in text
    assert "Testobjekt" in text
    assert "Drift och funktion" in text
    assert "Otillräckligt frånluftsflöde i kök" in text
    assert "EJ GODKÄND" in text


def test_intyg_pdf_contains_core_content_and_basis() -> None:
    content = intyg_pdf(_intyg())
    assert content.startswith(b"%PDF")
    text = _pdf_text(content)
    assert "OVK-INTYG" in text
    assert "Berghällen 1:2" in text
    assert "Stina Kontrollant" in text
    assert "GODKÄND" in text
    assert "2029-08-01" in text
    assert "BFS 2011:16" in text


def _write_entitlements(root: Path) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps(
            {
                "customer_id": "acme",
                "modules": [{"id": "ovk", "active": True}],
            }
        ),
        encoding="utf-8",
    )


def _client(tmp_path: Path, monkeypatch: MonkeyPatch, *, with_key: bool = True) -> TestClient:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    if with_key:
        monkeypatch.setenv("CROW_EXPORT_SIGNING_KEY", _SECRET)
    else:
        monkeypatch.delenv("CROW_EXPORT_SIGNING_KEY", raising=False)
    _write_entitlements(tmp_path)
    return TestClient(create_app(tmp_path))


def test_surface_sign_then_download_both_kinds(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    OvkWorkflowRepository(tmp_path).save(_record())
    OvkIntygRepository(tmp_path).save(_intyg())
    client = _client(tmp_path, monkeypatch)

    for kind, document_id, marker in (
        ("protokoll", "ovk-001", "OVK-PROTOKOLL"),
        ("intyg", "intyg-001", "OVK-INTYG"),
    ):
        signed = client.post(f"/api/ovk/projects/p1/export/{kind}/{document_id}/sign")
        assert signed.status_code == 200, signed.text
        payload = signed.json()
        assert payload["algorithm"] == "hmac-sha256"
        download = client.get(payload["url"])
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/pdf"
        assert download.content.startswith(b"%PDF")
        assert marker in _pdf_text(download.content)


def test_surface_rejects_unsigned_tampered_and_expired_links(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    OvkIntygRepository(tmp_path).save(_intyg())
    client = _client(tmp_path, monkeypatch)

    signed = client.post("/api/ovk/projects/p1/export/intyg/intyg-001/sign")
    url = signed.json()["url"]

    tampered = client.get(url.replace("intyg-001", "intyg-999"))
    assert tampered.status_code == 403

    bad_sig = client.get(url[:-4] + "0000")
    assert bad_sig.status_code == 403
    assert bad_sig.json()["detail"]["code"] == "OVK_EXPORT_SIGNATURE_REJECTED"

    expired_epoch = int(time.time()) - 100
    expired_sig = sign_export_path(_SECRET, "/api/ovk/export/p1/intyg/intyg-001.pdf", expired_epoch)
    expired = client.get(
        f"/api/ovk/export/p1/intyg/intyg-001.pdf?expires={expired_epoch}&sig={expired_sig}"
    )
    assert expired.status_code == 403
    assert "expired" in expired.json()["detail"]["message"]


def test_surface_requires_signing_key(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    OvkIntygRepository(tmp_path).save(_intyg())
    client = _client(tmp_path, monkeypatch, with_key=False)
    response = client.post("/api/ovk/projects/p1/export/intyg/intyg-001/sign")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "OVK_EXPORT_SIGNING_KEY_MISSING"


def test_surface_blocks_protocol_export_when_not_ready(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    OvkWorkflowRepository(tmp_path).save(_record(review_status=ReviewStatus.PENDING))
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/ovk/projects/p1/export/protokoll/ovk-001/sign")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_PROTOCOL_NOT_READY"


def test_surface_validates_kind_ttl_and_missing_document(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    OvkIntygRepository(tmp_path).save(_intyg())
    client = _client(tmp_path, monkeypatch)

    unknown_kind = client.post("/api/ovk/projects/p1/export/ritning/intyg-001/sign")
    assert unknown_kind.status_code == 422

    bad_ttl = client.post(
        "/api/ovk/projects/p1/export/intyg/intyg-001/sign",
        json={"ttl_seconds": 999999},
    )
    assert bad_ttl.status_code == 422

    missing = client.post("/api/ovk/projects/p1/export/intyg/saknas/sign")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "OVK_EXPORT_DOCUMENT_NOT_FOUND"
