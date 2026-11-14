"""Intygets integritet: omutbarhet, verifiering, utkast, Unicode och konsekvent resultat.

Återinför augustigranskningens fixar, anpassade till dagens fältbrygga.
"""

from __future__ import annotations

import io
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from pytest import MonkeyPatch
from test_ovk_workflow import _client, _workflow_payload

from crow_ovk import (
    ActionStatus,
    FindingSeverity,
    OvkAction,
    OvkFinding,
    unresolved_required_finding_ids,
)
from crow_ovk_intyg import Byggnadsagare, OvkIntyg, OvkIntygRepository

_INTYG_BODY: dict[str, object] = {
    "intyg_id": "intyg-001",
    "fastighetsbeteckning": "Berghällen 1:2",
    "byggnadsagare_name": "Brf Berghällen",
    "inspection_type": "aterkommande",
    "building_category": "flerbostadshus",
    "inspection_date": "2026-11-13",
    "kontrollant_name": "Stina Kontrollant",
    "kontrollant_behorighet": "K",
    "kontrollant_certification_body": "RISE",
    "kontrollant_certificate_number": "K-12345",
}
_BASE = "/api/ovk/projects/p1/inspections/ovk-001"


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return re.sub(r"\s+", " ", "\n".join(page.extract_text() or "" for page in reader.pages))


def _ready_client(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    findings: list[dict[str, object]] | None = None,
    actions: list[dict[str, object]] | None = None,
) -> TestClient:
    monkeypatch.setenv("CROW_EXPORT_SIGNING_KEY", "test-signing-key")
    monkeypatch.delenv("CROW_OVK_VERIFY_BASE", raising=False)
    client = _client(tmp_path, monkeypatch)
    payload: dict[str, Any] = _workflow_payload()
    payload["inspection"]["findings"] = findings or []
    payload["inspection"]["actions"] = actions or []
    saved = client.put(_BASE, json=payload)
    assert saved.status_code == 200, saved.text
    _approve(client, _INTYG_BODY)
    return client


def _approve(client: TestClient, body: dict[str, object]) -> None:
    preview = client.post(_BASE + "/intyg/preview", json=body)
    assert preview.status_code == 200, preview.text
    approval = client.post(
        _BASE + "/intyg/review",
        json=body,
        headers={"X-OVK-Review-Revision": preview.headers["X-OVK-Review-Revision"]},
    )
    assert approval.status_code == 200, approval.text


def _finding(
    severity: FindingSeverity, *, action_required: bool = True, system_id: str | None = None
) -> OvkFinding:
    return OvkFinding(
        finding_id="f1",
        description="Brist",
        severity=severity,
        action_required=action_required,
        system_id=system_id,
    )


def test_unresolved_rule_distinguishes_blocking_from_minor_findings() -> None:
    major = (_finding(FindingSeverity.MAJOR),)
    minor = (_finding(FindingSeverity.MINOR),)
    open_action = (OvkAction("a1", "f1", "Åtgärda"),)
    closed_action = (OvkAction("a1", "f1", "Åtgärda", status=ActionStatus.CLOSED),)

    # Allvarlig brist utan registrerad åtgärd får inte glida igenom som godkänd.
    assert unresolved_required_finding_ids(major, ()) == {"f1"}
    assert unresolved_required_finding_ids(major, open_action) == {"f1"}
    assert unresolved_required_finding_ids(major, closed_action) == frozenset()
    # Klass 1 utan öppen åtgärd är "godkänd med anmärkning".
    assert unresolved_required_finding_ids(minor, ()) == frozenset()
    assert unresolved_required_finding_ids(minor, open_action) == {"f1"}
    assert (
        unresolved_required_finding_ids(
            (_finding(FindingSeverity.MAJOR, action_required=False),), ()
        )
        == frozenset()
    )


def test_major_finding_without_action_fails_protocol_and_intyg_alike(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _ready_client(
        tmp_path,
        monkeypatch,
        findings=[
            {
                "finding_id": "f1",
                "description": "Brandspjäll ur funktion",
                "severity": "major",
                "action_required": True,
                "system_id": "FTX01",
            }
        ],
    )
    assert client.get(_BASE).json()["inspection"]["conclusion"] == "deficiencies"
    intyg = client.post(_BASE + "/intyg", json=_INTYG_BODY).json()
    assert intyg["result"] == "ej_godkand"
    assert [row["result"] for row in intyg["systems"]] == ["ej_godkand"]


def test_minor_finding_keeps_overall_and_system_result_approved(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _ready_client(
        tmp_path,
        monkeypatch,
        findings=[
            {
                "finding_id": "f1",
                "description": "Smutsigt don",
                "severity": "minor",
                "action_required": True,
                "system_id": "FTX01",
            }
        ],
    )
    intyg = client.post(_BASE + "/intyg", json=_INTYG_BODY).json()
    assert intyg["result"] == "godkand"
    assert [row["result"] for row in intyg["systems"]] == ["godkand"]


def test_deficiency_without_system_binding_fails_every_system_row(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Fältbryggans grupperade klass 2-rader saknar systemkoppling.
    client = _ready_client(
        tmp_path,
        monkeypatch,
        findings=[
            {
                "finding_id": "f1",
                "description": "[3.7] Felaktigt luftflöde – Badrum: 1201",
                "severity": "major",
                "action_required": True,
            }
        ],
        actions=[{"action_id": "a1", "finding_id": "f1", "description": "Åtgärda"}],
    )
    intyg = client.post(_BASE + "/intyg", json=_INTYG_BODY).json()
    assert intyg["result"] == "ej_godkand"
    assert [row["result"] for row in intyg["systems"]] == ["ej_godkand"]


def test_issued_intyg_cannot_be_overwritten(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    first = client.post(_BASE + "/intyg", json=_INTYG_BODY)
    assert first.status_code == 200, first.text

    second = client.post(
        _BASE + "/intyg", json={**_INTYG_BODY, "byggnadsagare_name": "Annan ägare"}
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "OVK_INTYG_ALREADY_EXISTS"
    stored = client.get("/api/ovk/projects/p1/intyg/intyg-001").json()
    assert stored["byggnadsagare"]["name"] == "Brf Berghällen"
    leftovers = list((tmp_path / "projects" / "p1" / "ovk-intyg").glob("*.tmp"))
    assert leftovers == []


def test_issue_returns_code_that_verifies_and_tampering_is_rejected(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    created = client.post(_BASE + "/intyg", json=_INTYG_BODY).json()
    code = created["verification_code"]
    assert re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}", code)
    assert created["verify_url"] == (
        "https://crowab.se/ovk/verifiera/p1/intyg-001?c=" + code.replace("-", "")
    )

    valid = client.get("/ovk/verifiera/p1/intyg-001", params={"c": code.lower()})
    assert valid.status_code == 200
    assert "GILTIGT INTYG" in valid.text and "EJ GILTIGT" not in valid.text
    assert "Berghällen 1:2" in valid.text

    for path, params in (
        ("/ovk/verifiera/p1/intyg-001", {"c": "AAAA-BBBB-CCCC"}),
        ("/ovk/verifiera/p1/intyg-001", {}),
        ("/ovk/verifiera/p1/finns-ej", {"c": code}),
        ("/ovk/verifiera/p1/intyg-001", {"c": "<script>alert(1)</script>"}),
    ):
        rejected = client.get(path, params=params)
        assert "EJ GILTIGT" in rejected.text
        assert "Berghällen" not in rejected.text
        assert "<script>" not in rejected.text

    # Ett intyg som ändrats på disk i efterhand matchar inte längre den tryckta koden.
    stored = tmp_path / "projects" / "p1" / "ovk-intyg" / "intyg-001.json"
    stored.write_text(
        stored.read_text(encoding="utf-8").replace("Brf Berghällen", "Brf Förfalskad"),
        encoding="utf-8",
    )
    assert "EJ GILTIGT" in client.get("/ovk/verifiera/p1/intyg-001", params={"c": code}).text


def test_verify_page_is_internal_until_opened(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    code = client.post(_BASE + "/intyg", json=_INTYG_BODY).json()["verification_code"]
    monkeypatch.delenv("CROW_CUSTOMER_ID")
    anonymous = client.get(
        "/ovk/verifiera/p1/intyg-001", params={"c": code}, follow_redirects=False
    )
    assert anonymous.status_code != 200
    assert "GILTIGT INTYG" not in anonymous.text


def test_preview_is_watermarked_and_never_issues(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    preview = client.post(_BASE + "/intyg/preview", json=_INTYG_BODY)
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"] == "application/pdf"
    text = _pdf_text(preview.content)
    assert "UTKAST – EJ GILTIGT INTYG" in text
    assert "Verifieringskod" not in text
    assert client.get("/api/ovk/projects/p1/intyg").json()["intyg"] == []


def test_export_pdf_carries_code_and_handles_non_latin1(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    body = {**_INTYG_BODY, "byggnadsagare_name": "Łukasz Żak – ägare ✓"}
    _approve(client, body)
    code = client.post(_BASE + "/intyg", json=body).json()["verification_code"]

    signed = client.post("/api/ovk/projects/p1/export/intyg/intyg-001/sign")
    assert signed.status_code == 200, signed.text
    pdf = client.get(signed.json()["url"])
    assert pdf.status_code == 200
    text = _pdf_text(pdf.content)
    assert "Łukasz Żak – ägare" in text
    assert f"Verifieringskod: {code}" in text
    assert "crowab.se/ovk/verifiera/p1/intyg-001" in text
    assert "UTKAST" not in text

    protocol = client.post("/api/ovk/projects/p1/export/protokoll/ovk-001/sign")
    assert client.get(protocol.json()["url"]).status_code == 200


def test_verify_base_is_configurable(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    monkeypatch.setenv("CROW_OVK_VERIFY_BASE", "https://test.example/v/")
    created = client.post(_BASE + "/intyg", json=_INTYG_BODY).json()
    assert created["verify_url"].startswith("https://test.example/v/p1/intyg-001?c=")


def test_intyg_list_page_escapes_rendered_values(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    page = _ready_client(tmp_path, monkeypatch).get("/ovk/intyg").text
    assert "esc(x.intyg_id)" in page and "esc(x.result)" in page
    assert "'<tr><td>'+x.intyg_id+" not in page
    assert 'id="preview"' in page


@pytest.mark.parametrize("module", ["crow_ovk_export"])
def test_fonts_are_packaged(module: str) -> None:
    from importlib.resources import files

    names = {item.name for item in (files(module) / "fonts").iterdir()}
    assert {"DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf"} <= names
    assert "LICENSE-DejaVu.txt" in names


def test_concurrent_issuance_preserves_winner(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    assert client.post(_BASE + "/intyg", json=_INTYG_BODY).status_code == 200
    repository = OvkIntygRepository(tmp_path)
    original = repository.load("p1", "intyg-001")
    first = replace(original, intyg_id="race", byggnadsagare=Byggnadsagare("Ägare A"))
    second = replace(original, intyg_id="race", byggnadsagare=Byggnadsagare("Ägare B"))
    barrier = Barrier(2)
    real_link = os.link

    def synchronized_link(source: Path, destination: Path) -> None:
        barrier.wait(timeout=10)
        real_link(source, destination)

    monkeypatch.setattr(os, "link", synchronized_link)

    def issue(candidate: OvkIntyg) -> OvkIntyg | None:
        try:
            repository.save(candidate)
        except FileExistsError:
            return None
        return candidate

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(issue, (first, second)))

    winners = [candidate for candidate in results if candidate is not None]
    assert len(winners) == 1
    assert repository.load("p1", "race") == winners[0]
    assert repository.load("p1", "intyg-001") == original
    assert not list((tmp_path / "projects" / "p1" / "ovk-intyg").glob("*.tmp"))


def test_issue_requires_exact_review_revision(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _ready_client(tmp_path, monkeypatch)
    body = {**_INTYG_BODY, "intyg_id": "unreviewed"}
    assert client.post(_BASE + "/intyg", json=body).status_code == 409
    preview = client.post(_BASE + "/intyg/preview", json=body)
    assert preview.status_code == 200
    assert client.post(_BASE + "/intyg", json=body).status_code == 409
    _approve(client, body)
    changed = {**body, "byggnadsagare_name": "Changed"}
    assert client.post(_BASE + "/intyg", json=changed).status_code == 409
    payload: dict[str, Any] = _workflow_payload()
    payload["inspection"]["object"]["name"] = "Changed object"
    assert client.put(_BASE, json=payload).status_code == 200
    assert client.post(_BASE + "/intyg", json=body).status_code == 409
    _approve(client, body)
    assert client.post(_BASE + "/intyg", json=body).status_code == 200
