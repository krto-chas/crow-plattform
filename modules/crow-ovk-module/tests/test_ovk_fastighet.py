"""Pass 102: fastighetsentitet, besiktningsmannaregister och intygskoppling."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from crow_ovk_fastighet import (
    Adress,
    Behorighet,
    Besiktningsman,
    BesiktningsmanRepository,
    Byggnad,
    Fastighet,
    FastighetRepository,
    Forvaltare,
    besiktningsman_from_payload,
    besiktningsman_to_payload,
    fastighet_from_payload,
    fastighet_to_payload,
    funktionskontrollant_from,
)
from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def _fastighet() -> Fastighet:
    return Fastighet(
        fastighet_id="berget-1",
        project_id="p1",
        fastighetsbeteckning="Berget 1",
        referensnr="REF-2026-014",
        byggnadens_adress=Adress(gata="Bergvägen 1", postnr="18500", ort="Vaxholm"),
        byggnadsagare_namn="Brf Berget",
        byggnadsagare_adress=Adress(gata="Box 12", postnr="18521", ort="Vaxholm"),
        forvaltare=Forvaltare(namn="Fast Förvaltning AB", telefon="08-123", epost="fv@ex.se"),
        byggnader=(
            Byggnad(
                byggnad_id="b1",
                internt_namn="Hus A",
                internt_nr="001",
                verksamhet="Bostäder",
                bra_m2=Decimal("2450.5"),
                antal_lagenheter=36,
                antal_lokaler=2,
            ),
        ),
    )


def test_fastighet_requires_beteckning_and_unique_byggnader() -> None:
    with pytest.raises(ValueError, match="fastighetsbeteckning"):
        Fastighet(fastighet_id="x", project_id="p1", fastighetsbeteckning=" ")
    with pytest.raises(ValueError, match="duplicate"):
        Fastighet(
            fastighet_id="x",
            project_id="p1",
            fastighetsbeteckning="Berget 1",
            byggnader=(
                Byggnad(byggnad_id="b1", internt_namn="Hus A"),
                Byggnad(byggnad_id="b1", internt_namn="Hus B"),
            ),
        )


def test_byggnad_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="bra_m2"):
        Byggnad(byggnad_id="b1", internt_namn="Hus A", bra_m2=Decimal("-1"))
    with pytest.raises(ValueError, match="antal_lagenheter"):
        Byggnad(byggnad_id="b1", internt_namn="Hus A", antal_lagenheter=-1)


def test_fastighetstyp_roundtrip_and_default() -> None:
    from crow_ovk_fastighet import Fastighetstyp

    default = Fastighet(fastighet_id="x", project_id="p1", fastighetsbeteckning="Berget 1")
    assert default.fastighetstyp is Fastighetstyp.FLERBOSTADSHUS
    villa = fastighet_from_payload(
        {
            "fastighet_id": "v1",
            "project_id": "p1",
            "fastighetsbeteckning": "Villan 2",
            "fastighetstyp": "villa",
        }
    )
    assert villa.fastighetstyp is Fastighetstyp.VILLA
    assert fastighet_to_payload(villa)["fastighetstyp"] == "villa"


def test_fastighet_payload_roundtrip_serializes_bra_as_string() -> None:
    fastighet = _fastighet()
    payload = fastighet_to_payload(fastighet)
    byggnader = payload["byggnader"]
    assert isinstance(byggnader, list)
    assert byggnader[0]["bra_m2"] == "2450.5"
    restored = fastighet_from_payload(payload)
    assert restored == fastighet
    assert restored.byggnader[0].bra_m2 == Decimal("2450.5")


def test_repositories_roundtrip_and_reject_unsafe_ids(tmp_path: Path) -> None:
    fastighet_repo = FastighetRepository(tmp_path)
    fastighet_repo.save(_fastighet())
    assert fastighet_repo.load("p1", "berget-1").fastighetsbeteckning == "Berget 1"
    assert len(fastighet_repo.list("p1")) == 1
    with pytest.raises(ValueError, match="invalid"):
        fastighet_repo.load("p1", "../../etc")

    person = Besiktningsman(
        besiktningsman_id="stina-b",
        namn="Stina Besiktning",
        behorighet=Behorighet.K,
        certifieringsorgan="RISE",
        certnummer="1234",
        giltig_till=date(2028, 1, 1),
    )
    person_repo = BesiktningsmanRepository(tmp_path)
    person_repo.save(person)
    assert person_repo.load("stina-b") == besiktningsman_from_payload(
        besiktningsman_to_payload(person)
    )
    assert len(person_repo.list()) == 1


def test_besiktningsman_adapter_maps_to_funktionskontrollant() -> None:
    person = Besiktningsman(
        besiktningsman_id="stina-b",
        namn="Stina Besiktning",
        behorighet=Behorighet.K,
        certifieringsorgan="RISE",
        certnummer="1234",
        giltig_till=date(2028, 1, 1),
    )
    kontrollant = funktionskontrollant_from(person)
    assert kontrollant.name == "Stina Besiktning"
    assert kontrollant.behorighet.value == "K"
    assert kontrollant.certificate_valid_to == date(2028, 1, 1)


def _surface_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import json

    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    entitlements = tmp_path / "config" / "customers" / "acme"
    entitlements.mkdir(parents=True, exist_ok=True)
    (entitlements / "entitlements.json").write_text(
        json.dumps(
            {
                "schema_version": "crow-entitlements-v1",
                "customer_id": "acme",
                "modules": [{"id": "ovk", "active": True}],
            }
        ),
        encoding="utf-8",
    )
    return TestClient(create_app(tmp_path))


def test_surface_saves_lists_and_reloads_fastighet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _surface_client(tmp_path, monkeypatch)
    payload = fastighet_to_payload(_fastighet())
    saved = client.put("/api/ovk/projects/p1/fastighet/berget-1", json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["fastighet"]["fastighetsbeteckning"] == "Berget 1"

    listing = client.get("/api/ovk/projects/p1/fastighet")
    assert listing.status_code == 200
    assert len(listing.json()["fastigheter"]) == 1

    fetched = client.get("/api/ovk/projects/p1/fastighet/berget-1")
    assert fetched.status_code == 200
    assert fetched.json()["byggnader"][0]["bra_m2"] == "2450.5"

    invalid = client.put(
        "/api/ovk/projects/p1/fastighet/berget-2", json={"fastighetsbeteckning": " "}
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "INVALID_FASTIGHET"

    page = client.get("/ovk/fastighet")
    assert page.status_code == 200
    assert "Fastighet" in page.text
    app_js = client.get("/ovk/fastighet/app.js")
    assert app_js.status_code == 200
    assert app_js.headers["cache-control"] == "no-cache"
    # Inget projekt valt: projektet skapas automatiskt från fastighetsbeteckningen.
    assert "async function ensureProject()" in app_js.text
    assert "slugify($('beteckning').value)" in app_js.text
    # Projektbyte får inte radera ifyllda uppgifter.
    assert "function hasFormContent()" in app_js.text
    assert "if(!hasFormContent())fillFastighet({})" in app_js.text


def test_surface_besiktningsman_registry_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _surface_client(tmp_path, monkeypatch)
    saved = client.put(
        "/api/ovk/registry/besiktningsman/stina-b",
        json={
            "namn": "Stina Besiktning",
            "behorighet": "K",
            "certifieringsorgan": "RISE",
            "certnummer": "1234",
            "giltig_till": "2028-01-01",
        },
    )
    assert saved.status_code == 200, saved.text
    listing = client.get("/api/ovk/registry/besiktningsman")
    assert [item["namn"] for item in listing.json()["besiktningsman"]] == ["Stina Besiktning"]
    missing = client.get("/api/ovk/registry/besiktningsman/okand")
    assert missing.status_code == 404


def test_intyg_surface_resolves_registry_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Intyg kan byggas via fastighet_id + besiktningsman_id i stället för fritext."""
    from test_ovk_workflow import _workflow_payload

    client = _surface_client(tmp_path, monkeypatch)
    saved = client.put("/api/ovk/projects/p1/inspections/ovk-001", json=_workflow_payload())
    assert saved.status_code == 200 and saved.json()["protocol_ready"] is True

    client.put("/api/ovk/projects/p1/fastighet/berget-1", json=fastighet_to_payload(_fastighet()))
    client.put(
        "/api/ovk/registry/besiktningsman/stina-b",
        json={
            "namn": "Stina Besiktning",
            "behorighet": "K",
            "certifieringsorgan": "RISE",
            "certnummer": "1234",
            "giltig_till": "2028-01-01",
        },
    )
    response = client.post(
        "/api/ovk/projects/p1/inspections/ovk-001/intyg",
        json={
            "intyg_id": "intyg-1",
            "fastighet_id": "berget-1",
            "besiktningsman_id": "stina-b",
            "inspection_type": "aterkommande",
            "building_category": "flerbostadshus",
            "inspection_date": "2026-08-01",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fastighetsbeteckning"] == "Berget 1"
    assert body["byggnadsagare"]["name"] == "Brf Berget"
    assert body["funktionskontrollant"]["name"] == "Stina Besiktning"
    assert body["funktionskontrollant"]["certificate_valid_to"] == "2028-01-01"

    missing = client.post(
        "/api/ovk/projects/p1/inspections/ovk-001/intyg",
        json={
            "intyg_id": "intyg-2",
            "fastighet_id": "finns-ej",
            "besiktningsman_id": "stina-b",
            "inspection_type": "aterkommande",
            "building_category": "flerbostadshus",
            "inspection_date": "2026-08-01",
        },
    )
    assert missing.status_code == 404
