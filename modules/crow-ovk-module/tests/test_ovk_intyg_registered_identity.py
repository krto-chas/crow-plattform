from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from crow_ovk_fastighet import (
    Adress,
    Behorighet,
    Besiktningsman,
    BesiktningsmanRepository,
    Byggnad,
    Fastighet,
    FastighetRepository,
)
from pytest import MonkeyPatch
from test_ovk_workflow import _client, _record

from crow_ovk_workflow import OvkWorkflowRepository
from crow_ovk_workflow.models import InspectionPlanning


def test_registered_identity_controls_certificate(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    today = date.today()
    properties = FastighetRepository(tmp_path)
    properties.save(
        Fastighet(
            fastighet_id="object-1",
            project_id="p1",
            fastighetsbeteckning="Register 1:2",
            byggnadens_adress=Adress(gata="Registervägen 1"),
            byggnadsagare_namn="Registrerad ägare",
            byggnader=(Byggnad("building-1", "Hus A"),),
        )
    )
    inspectors = BesiktningsmanRepository(tmp_path)
    person = Besiktningsman(
        "inspector-1", "Registrerad kontrollant", Behorighet.K, "RISE", "K-123", today
    )
    inspectors.save(person)
    repository = OvkWorkflowRepository(tmp_path)
    record = replace(
        _record(),
        planning=InspectionPlanning("inspector-1", today, "aterkommande"),
        building_structure_json=json.dumps(
            {
                "systems": [{"system_id": "FTX01", "system_type": "FTX", "label": "System FTX01"}],
                "units": [],
                "technical_spaces": [],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    repository.save(record)
    base = "/api/ovk/projects/p1/inspections/ovk-001/intyg"
    body = {
        "intyg_id": "registered-1",
        "inspection_type": "aterkommande",
        "inspection_date": today.isoformat(),
        "building_category": "flerbostadshus",
        "fastighetsbeteckning": "Fel fastighet",
        "byggnadsagare_name": "Fel ägare",
        "kontrollant_name": "Fel kontrollant",
    }
    for change in (
        {"fastighet_id": "other"},
        {"besiktningsman_id": "other"},
        {"inspection_type": "forstagang"},
        {"building_category": "lokal"},
    ):
        assert client.post(base + "/preview", json={**body, **change}).status_code == 422
    preview = client.post(base + "/preview", json=body)
    assert preview.status_code == 200, preview.text
    approved = client.post(
        base + "/review",
        json=body,
        headers={"X-OVK-Review-Revision": preview.headers["X-OVK-Review-Revision"]},
    )
    assert approved.status_code == 200, approved.text
    issued = client.post(base, json=body)
    assert issued.status_code == 200, issued.text
    data = issued.json()
    assert data["object_name"] == "Register 1:2 · Hus A"
    assert data["byggnadsagare"]["name"] == "Registrerad ägare"
    assert data["funktionskontrollant"]["name"] == "Registrerad kontrollant"
    assert data["next_inspection"]["interval_years"] == 3
    inspectors.save(replace(person, giltig_till=today - timedelta(days=1)))
    assert client.post(base + "/preview", json=body).status_code == 422
    inspectors.save(person)
    system = replace(record.inspection.systems[0], system_type="F")
    repository.save(replace(record, inspection=replace(record.inspection, systems=(system,))))
    assert client.post(base + "/preview", json=body).status_code == 422
