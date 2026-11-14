from datetime import date
from pathlib import Path

from crow_ovk_fastighet import Behorighet, Besiktningsman, BesiktningsmanRepository
from test_ovk_field_history import _client, _payload

from crow_ovk import OvkObject, VentilationSystemRef
from crow_ovk_module.ovk_field_migration import migrate_field_data
from crow_ovk_workflow import OvkWorkflowRepository, build_record
from crow_ovk_workflow.models import InspectionPlanning


def test_migration_dry_run_and_preserves_originals(tmp_path: Path) -> None:
    client = _client(tmp_path)
    BesiktningsmanRepository(tmp_path).save(
        Besiktningsman("person-1", "Inspector", Behorighet.K, "RISE", "K-123", date.today())
    )
    OvkWorkflowRepository(tmp_path).save(
        build_record(
            inspection_id="ovk-2025",
            ovk_object=OvkObject("object-1", "p1", "building-1", "Building"),
            systems=(VentilationSystemRef("F1", "F", "F1"),),
            planning=InspectionPlanning("person-1", date.today(), "aterkommande"),
        )
    )
    context = client.put(
        "/api/ovk/field/context/ovk-2025",
        json={"project_id": "p1", "inspector": "Inspector", "system_type": "F"},
    )
    assert context.status_code == 200
    snapshot = client.put("/api/ovk/field/sync/ovk-2025", json=_payload(b"photo"))
    assert snapshot.status_code == 200
    media = client.put(
        "/api/ovk/field/media/ovk-2025/photo-old",
        content=b"photo",
        headers={"Content-Type": "image/jpeg"},
    )
    assert media.status_code == 200
    original = tmp_path / "ovk-field-sync/ovk-2025.json"
    before = original.read_bytes()
    target = tmp_path / "projects/p1/ovk-field/ovk-2025"
    scoped = "/api/ovk/projects/p1/field/ovk-2025/sync"
    assert client.get(scoped).status_code == 409
    assert client.put(scoped, json=_payload(b"photo")).status_code == 409
    assert migrate_field_data(tmp_path)[0]["status"] == "ready"
    assert not target.exists()
    assert migrate_field_data(tmp_path, apply=True)[0]["status"] == "migrated"
    assert original.read_bytes() == before
    assert client.get(scoped).status_code == 200
    assert (target / "migration.json").is_file()
    url = "/api/ovk/projects/p1/field/ovk-2025/media/photo-old/content"
    assert client.get(url).content == b"photo"
    assert migrate_field_data(tmp_path, apply=True)[0]["status"] == "blocked"
    assert client.get(url).content == b"photo"


def test_migration_blocks_unbound_snapshot(tmp_path: Path) -> None:
    client = _client(tmp_path)
    snapshot = client.put("/api/ovk/field/sync/ovk-2025", json=_payload(b"photo"))
    assert snapshot.status_code == 200
    assert migrate_field_data(tmp_path, apply=True)[0]["status"] == "blocked"
    assert not (tmp_path / "projects").exists()
