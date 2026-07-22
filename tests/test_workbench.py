from pathlib import Path

from fastapi.testclient import TestClient

from crow_workbench.app import create_app


def test_create_and_list_project(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    response = client.post("/api/projects", json={"name": "Testprojekt"})
    assert response.status_code == 201
    assert response.json()["project_name"] == "Testprojekt"

    projects = client.get("/api/projects")
    assert projects.status_code == 200
    assert projects.json()[0]["project_id"] == "testprojekt"


def test_reject_non_pdf_upload(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})
    response = client.post(
        "/api/projects/testprojekt/documents",
        files={"files": ("notes.txt", b"text", "text/plain")},
    )
    assert response.status_code == 400


def test_claims_endpoint_is_explicit_before_analysis(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.get("/api/projects/testprojekt/claims")

    assert response.status_code == 200
    assert response.json() == {
        "analyzed": False,
        "summary": {
            "candidates": 0,
            "clusters": 0,
            "conflicting": 0,
            "review_required": 0,
        },
        "clusters": [],
    }


def test_claim_analysis_runs_through_public_services(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.post("/api/projects/testprojekt/analysis/claims")

    assert response.status_code == 200
    assert response.json()["claims"]["candidates"] == 0
    claims = client.get("/api/projects/testprojekt/claims")
    assert claims.status_code == 200
    assert claims.json()["analyzed"] is True


def test_authority_endpoint_is_explicit_before_resolution(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.get("/api/projects/testprojekt/authority")

    assert response.status_code == 200
    assert response.json()["resolved"] is False
    assert response.json()["accepted"]["accepted"] == 0


def test_authority_resolution_requires_claim_analysis(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.post("/api/projects/testprojekt/authority/resolve", json={"documents": []})

    assert response.status_code == 409


def test_authority_resolution_builds_accepted_claim_set(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})
    client.post("/api/projects/testprojekt/analysis/claims")

    response = client.post("/api/projects/testprojekt/authority/resolve", json={"documents": []})

    assert response.status_code == 200
    assert response.json()["summary"]["decisions"] == 0
    assert response.json()["accepted"]["accepted"] == 0
    authority = client.get("/api/projects/testprojekt/authority").json()
    assert authority["resolved"] is True


def test_technical_delta_endpoint_reports_missing_prerequisites(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.get("/api/projects/testprojekt/technical-deltas")

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["generated"] is False
    assert response.json()["prerequisites"] == {
        "baseline": False,
        "decisions": False,
        "reviews": False,
    }


def test_technical_delta_build_rejects_incomplete_pipeline(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.post("/api/projects/testprojekt/technical-deltas/build")

    assert response.status_code == 409
    assert "teknisk baseline" in response.json()["detail"]


def test_technical_delta_endpoint_loads_existing_delta_set(tmp_path: Path) -> None:
    import json

    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})
    project_dir = tmp_path / "projects" / "testprojekt"
    delta_file = project_dir / "crow-technical-deltas.json"
    delta_file.write_text(
        json.dumps(
            {
                "project_id": "testprojekt",
                "baseline_id": "baseline.contract",
                "deltas": [
                    {
                        "id": "delta:1",
                        "comparison_key": "ventilation|flow",
                        "delta_type": "modified",
                        "category": "ventilation",
                        "title": "Luftflöde",
                        "baseline_value": "300",
                        "approved_value": "400",
                        "unit": "L/S",
                        "confidence": 0.95,
                        "provenance": {
                            "baseline_item_id": "baseline:1",
                            "decision_id": "decision:1",
                            "review_event_id": "review:1",
                            "accepted_claim_ids": ["claim:1"],
                            "authority_decision_ids": ["authority:1"],
                            "document_ids": ["document:1"],
                            "trace": ["baseline -> decision"],
                        },
                        "fingerprint": "abc",
                        "object_ref": "AHU-01",
                        "property_name": "airflow",
                        "value_kind": "number",
                        "baseline_quantity": 300.0,
                        "approved_quantity": 400.0,
                        "quantity_delta": 100.0,
                        "change_direction": "increase",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.get("/api/projects/testprojekt/technical-deltas")

    assert response.status_code == 200
    assert response.json()["generated"] is True
    assert response.json()["summary"]["changed"] == 1
    assert response.json()["deltas"][0]["quantity_delta"] == 100.0


def test_commercial_endpoint_reports_readiness(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.get("/api/projects/testprojekt/commercial")

    assert response.status_code == 200
    assert response.json()["prerequisites"] == {
        "technical_deltas": False,
        "scope_rules": False,
        "price_book": False,
        "adjustment_profile": False,
    }
    assert response.json()["estimate"] is None


def test_commercial_example_profile_creates_explicit_configuration(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})

    response = client.post("/api/projects/testprojekt/commercial/profile/example")

    assert response.status_code == 200
    readiness = client.get("/api/projects/testprojekt/commercial").json()["prerequisites"]
    assert readiness["scope_rules"] is True
    assert readiness["price_book"] is True
    assert readiness["adjustment_profile"] is True
    assert readiness["technical_deltas"] is False


def test_commercial_build_requires_technical_delta(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Testprojekt"})
    client.post("/api/projects/testprojekt/commercial/profile/example")

    response = client.post("/api/projects/testprojekt/commercial/build")

    assert response.status_code == 409
    assert "Technical Delta" in response.json()["detail"]


def test_workbench_endpoint_returns_beta_foundation(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Betaprojekt"})
    response = client.get("/api/projects/betaprojekt/workbench")
    assert response.status_code == 200
    payload = response.json()
    assert payload["health"]["score"] >= 0
    assert payload["graph"]["nodes"][0]["type"] == "project"
    assert len(payload["timeline"]) == 6


def test_beta_shell_is_served(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    assert "Crow Workbench Beta" in response.text
    assert "Evidence Graph" in response.text


def test_import_framework_accepts_ifc(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "IFC project", "project_id": "ifc-project"})
    content = (
        b"ISO-10303-21;\nHEADER;FILE_SCHEMA(('IFC4'));ENDSEC;\nDATA;\n"
        b"#1=IFCPROJECT('x');\nENDSEC;END-ISO-10303-21;"
    )
    response = client.post(
        "/api/projects/ifc-project/documents",
        files=[("files", ("model.ifc", content, "application/octet-stream"))],
    )
    assert response.status_code == 201
    assert response.json()["assets"][0]["format_id"] == "ifc"
    manifests = client.get("/api/projects/ifc-project/imports").json()
    assert manifests[0]["metadata"]["schema"] == "IFC4"


def test_import_asset_detail_endpoint_returns_preview(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "DXF project", "project_id": "dxf-project"})
    content = (
        b"0\nSECTION\n2\nENTITIES\n0\nLINE\n8\nVENT\n10\n0\n20\n0\n"
        b"11\n10\n21\n10\n0\nENDSEC\n0\nEOF\n"
    )
    response = client.post(
        "/api/projects/dxf-project/documents",
        files=[("files", ("plan.dxf", content, "application/dxf"))],
    )
    assert response.status_code == 201
    checksum = response.json()["assets"][0]["checksum_sha256"]
    detail = client.get(f"/api/projects/dxf-project/imports/{checksum}")
    assert detail.status_code == 200
    assert detail.json()["preview"]["kind"] == "dxf_2d"
    source = client.get(f"/api/projects/dxf-project/imports/{checksum}/file")
    assert source.status_code == 200


def test_health_endpoint_reports_runtime_version(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.7.0-alpha.1"}


def _seed_identity_candidate(client: TestClient, project_id: str) -> str:
    for object_id in ("ccm:object:a", "ccm:object:b"):
        response = client.post(
            f"/api/projects/{project_id}/graph/objects",
            json={
                "object_type": "air_terminal",
                "discipline": "ventilation",
                "name": "TD1",
                "object_id": object_id,
            },
        )
        assert response.status_code == 201
    evidence = client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={
            "kind": "text",
            "source_id": "drawing-plan",
            "locator": "V-57--/D1",
            "metadata": {"source_kind": "drawing_text"},
            "evidence_id": "evidence:identity-candidate",
        },
    )
    assert evidence.status_code == 201
    relation = client.post(
        f"/api/projects/{project_id}/graph/relations",
        json={
            "source_id": "ccm:object:a",
            "relation_type": "same_as_candidate",
            "target_id": "ccm:object:b",
            "evidence_ids": ["evidence:identity-candidate"],
            "metadata": {"status": "review_required"},
            "relation_id": "ccm:relation:candidate-1",
        },
    )
    assert relation.status_code == 201
    return relation.json()["id"]


def test_workbench_identity_review_flow_is_persistent_and_auditable(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Identity Review"})
    relation_id = _seed_identity_candidate(client, "identity-review")

    pending = client.get("/api/projects/identity-review/graph/identity-candidates")
    assert pending.status_code == 200
    assert pending.json()["pending_count"] == 1

    reviewed = client.post(
        f"/api/projects/identity-review/graph/identity-candidates/{relation_id}/review",
        json={
            "decision": "confirm_same",
            "reviewer": "reviewer@example.test",
            "rationale": "Kontrollerad mot plan- och detaljritning.",
            "decided_at": "2026-07-21T07:45:00+00:00",
        },
    )
    assert reviewed.status_code == 201
    assert reviewed.json()["resolved_relation"]["relation_type"] == "same_as_confirmed"
    assert reviewed.json()["review"]["candidate_relation_id"] == relation_id

    pending_after = client.get("/api/projects/identity-review/graph/identity-candidates").json()
    assert pending_after["pending_count"] == 0
    assert pending_after["reviewed_count"] == 1
    history = client.get("/api/projects/identity-review/graph/identity-reviews").json()
    assert history["count"] == 1
    assert history["items"][0]["reviewer"] == "reviewer@example.test"

    duplicate = client.post(
        f"/api/projects/identity-review/graph/identity-candidates/{relation_id}/review",
        json={
            "decision": "reject_same",
            "reviewer": "second@example.test",
            "rationale": "Försök till nytt beslut.",
        },
    )
    assert duplicate.status_code == 409


def test_workbench_graph_audit_is_live_persistable_and_deduplicated(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    created_project = client.post("/api/projects", json={"name": "Graph Audit"})
    assert created_project.status_code == 201

    object_response = client.post(
        "/api/projects/graph-audit/graph/objects",
        json={
            "object_type": "air_terminal",
            "discipline": "ventilation",
            "name": "TD1",
            "object_id": "ccm:object:td1",
        },
    )
    assert object_response.status_code == 201

    live = client.get("/api/projects/graph-audit/graph/audit")
    assert live.status_code == 200
    assert live.json()["summary"]["evidence_gap"] == 2
    assert {item["rule_id"] for item in live.json()["findings"]} == {
        "VENT-EVID-001",
        "VENT-EVID-002",
    }
    assert live.json()["metadata"]["inference_performed"] is False

    first = client.post("/api/projects/graph-audit/graph/audit-runs")
    assert first.status_code == 201
    assert first.json()["created"] is True
    audit_id = first.json()["audit"]["audit_id"]

    duplicate = client.post("/api/projects/graph-audit/graph/audit-runs")
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False
    assert duplicate.json()["audit"]["audit_id"] == audit_id

    history = client.get("/api/projects/graph-audit/graph/audit-runs")
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["audit_id"] == audit_id
    assert history.json()["items"][0]["graph_checksum"] == live.json()["graph_checksum"]


def test_workbench_graph_audit_creates_new_run_after_graph_change(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Audit History"})
    first = client.post("/api/projects/audit-history/graph/audit-runs")
    assert first.status_code == 201

    object_response = client.post(
        "/api/projects/audit-history/graph/objects",
        json={
            "object_type": "duct",
            "discipline": "ventilation",
            "object_id": "ccm:object:duct1",
        },
    )
    assert object_response.status_code == 201

    second = client.post("/api/projects/audit-history/graph/audit-runs")
    assert second.status_code == 201
    assert second.json()["audit"]["audit_id"] != first.json()["audit"]["audit_id"]

    history = client.get("/api/projects/audit-history/graph/audit-runs")
    assert history.json()["count"] == 2


def test_workbench_audit_finding_review_is_separate_immutable_decision(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Finding Review"})
    client.post(
        "/api/projects/finding-review/graph/objects",
        json={
            "object_type": "air_terminal",
            "discipline": "ventilation",
            "name": "TD1",
            "object_id": "ccm:object:td1",
        },
    )
    audit_response = client.post("/api/projects/finding-review/graph/audit-runs")
    audit = audit_response.json()["audit"]
    finding = audit["findings"][0]

    reviewed = client.post(
        f"/api/projects/finding-review/graph/audit-runs/{audit['audit_id']}"
        f"/findings/{finding['finding_id']}/review",
        json={
            "decision": "acknowledge",
            "reviewer": "reviewer@example.test",
            "rationale": "Informationsluckan är känd och ska följas upp.",
            "decided_at": "2026-07-21T09:30:00+00:00",
        },
    )
    assert reviewed.status_code == 201
    body = reviewed.json()
    assert body["audit_id"] == audit["audit_id"]
    assert body["finding_id"] == finding["finding_id"]
    assert body["finding_snapshot"] == finding
    assert body["metadata"]["audit_mutated"] is False
    assert body["metadata"]["graph_mutated"] is False

    duplicate = client.post(
        f"/api/projects/finding-review/graph/audit-runs/{audit['audit_id']}"
        f"/findings/{finding['finding_id']}/review",
        json={
            "decision": "dismiss",
            "reviewer": "second@example.test",
            "rationale": "Försök till nytt beslut.",
        },
    )
    assert duplicate.status_code == 409

    history = client.get(
        f"/api/projects/finding-review/graph/audit-finding-reviews?audit_id={audit['audit_id']}"
    )
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["reviewer"] == "reviewer@example.test"

    original = client.get("/api/projects/finding-review/graph/audit-runs").json()["items"][0]
    assert original["findings"][0] == finding


def test_workbench_compares_immutable_audit_runs_without_auto_resolution(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Audit Diff"})
    base = client.post("/api/projects/audit-diff/graph/audit-runs").json()["audit"]

    created = client.post(
        "/api/projects/audit-diff/graph/objects",
        json={
            "object_type": "duct",
            "discipline": "ventilation",
            "object_id": "ccm:object:duct1",
        },
    )
    assert created.status_code == 201
    target = client.post("/api/projects/audit-diff/graph/audit-runs").json()["audit"]

    compared = client.get(
        f"/api/projects/audit-diff/graph/audit-runs/{base['audit_id']}/compare/{target['audit_id']}"
    )
    assert compared.status_code == 200
    body = compared.json()
    assert body["summary"] == {
        "total": 1,
        "new": 1,
        "persistent": 0,
        "no_longer_detected": 0,
    }
    assert body["changes"][0]["lifecycle"] == "new"
    assert body["metadata"]["comparison_only"] is True
    assert body["metadata"]["automatic_resolution_performed"] is False


def test_workbench_requires_human_verification_before_resolution_is_confirmed(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Resolution Verification"})
    project = "resolution-verification"

    terminal = client.post(
        f"/api/projects/{project}/graph/objects",
        json={
            "object_type": "air_terminal",
            "discipline": "ventilation",
            "name": "TD1",
            "object_id": "ccm:object:td1",
        },
    )
    assert terminal.status_code == 201
    base = client.post(f"/api/projects/{project}/graph/audit-runs").json()["audit"]
    feeds_finding = next(item for item in base["findings"] if item["rule_id"] == "VENT-EVID-001")

    for object_id, object_type in (
        ("ccm:object:duct1", "duct"),
        ("ccm:object:lb01", "ventilation_system"),
    ):
        response = client.post(
            f"/api/projects/{project}/graph/objects",
            json={
                "object_type": object_type,
                "discipline": "ventilation",
                "object_id": object_id,
            },
        )
        assert response.status_code == 201
    evidence = client.post(
        f"/api/projects/{project}/graph/evidence",
        json={
            "kind": "text",
            "source_id": "ifc-model",
            "locator": "#4242",
            "evidence_id": "evidence:relation:1",
        },
    )
    assert evidence.status_code == 201
    for source_id, relation_type, target_id, relation_id in (
        ("ccm:object:duct1", "feeds", "ccm:object:td1", "relation:feeds:td1"),
        ("ccm:object:td1", "belongs_to", "ccm:object:lb01", "relation:system:td1"),
        ("ccm:object:duct1", "belongs_to", "ccm:object:lb01", "relation:system:duct1"),
    ):
        relation = client.post(
            f"/api/projects/{project}/graph/relations",
            json={
                "source_id": source_id,
                "relation_type": relation_type,
                "target_id": target_id,
                "evidence_ids": ["evidence:relation:1"],
                "relation_id": relation_id,
            },
        )
        assert relation.status_code == 201

    target = client.post(f"/api/projects/{project}/graph/audit-runs").json()["audit"]
    comparison = client.get(
        f"/api/projects/{project}/graph/audit-runs/{base['audit_id']}/compare/{target['audit_id']}"
    ).json()
    change = next(
        item for item in comparison["changes"] if item["finding_id"] == feeds_finding["finding_id"]
    )
    assert change["lifecycle"] == "no_longer_detected"
    assert change["metadata"]["resolution_status"] == "candidate_for_verification"

    verified = client.post(
        f"/api/projects/{project}/graph/audit-runs/{base['audit_id']}"
        f"/compare/{target['audit_id']}/findings/{feeds_finding['finding_id']}/verify",
        json={
            "decision": "verify_resolved",
            "reviewer": "reviewer@example.test",
            "rationale": "Försörjande relation är nu explicit och verifierad mot IFC.",
            "decided_at": "2026-07-21T10:45:00+00:00",
        },
    )
    assert verified.status_code == 201
    body = verified.json()
    assert body["decision"] == "verify_resolved"
    assert body["previous_finding"] == feeds_finding
    assert body["base_graph_checksum"] == base["graph_checksum"]
    assert body["target_graph_checksum"] == target["graph_checksum"]
    assert body["metadata"]["graph_mutated"] is False

    duplicate = client.post(
        f"/api/projects/{project}/graph/audit-runs/{base['audit_id']}"
        f"/compare/{target['audit_id']}/findings/{feeds_finding['finding_id']}/verify",
        json={
            "decision": "reject_resolution",
            "reviewer": "second@example.test",
            "rationale": "Försök till nytt beslut.",
        },
    )
    assert duplicate.status_code == 409

    history = client.get(
        f"/api/projects/{project}/graph/audit-resolution-verifications"
        f"?base_audit_id={base['audit_id']}&target_audit_id={target['audit_id']}"
    )
    assert history.status_code == 200
    assert history.json()["count"] == 1


def test_graph_evidence_index_endpoint_reports_usage_and_gaps(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post("/api/projects", json={"name": "Evidence index"}).json()
    project_id = project["project_id"]

    ev1 = client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "dxf", "source_id": "drawing.dxf", "checksum": "a" * 64},
    ).json()
    client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "pdf", "source_id": "description.pdf", "checksum": "b" * 64},
    )
    client.post(
        f"/api/projects/{project_id}/graph/objects",
        json={
            "object_type": "air_terminal",
            "discipline": "ventilation",
            "evidence_ids": [ev1["id"]],
        },
    )

    response = client.get(f"/api/projects/{project_id}/graph/evidence-index")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_count"] == 2
    assert payload["reference_count"] == 1
    assert len(payload["unreferenced_evidence_ids"]) == 1
    assert payload["missing_evidence_ids"] == []
    assert payload["graph_mutated"] is False


def test_graph_evidence_audit_endpoint_is_read_only(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post("/api/projects", json={"name": "Evidence audit"}).json()
    project_id = project["project_id"]

    client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "pdf", "source_id": "unused.pdf", "checksum": "d" * 64},
    )

    response = client.get(f"/api/projects/{project_id}/graph/evidence-audit")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {"total": 1, "data_quality": 0, "evidence_gap": 1}
    assert payload["findings"][0]["rule_id"] == "EVID-EVID-001"
    assert payload["metadata"]["automatic_repair_performed"] is False


def test_evidence_audit_runs_are_immutable_and_deduplicated(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post("/api/projects", json={"name": "Evidence history"}).json()
    project_id = project["project_id"]
    client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "pdf", "source_id": "unused.pdf", "checksum": "e" * 64},
    )

    first = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs")
    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["created"] is True
    audit = first_payload["audit"]
    assert audit["audit_id"].startswith("evidence:audit:")
    assert len(audit["graph_checksum"]) == 64
    assert audit["summary"]["evidence_gap"] == 1

    duplicate = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs")
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False
    assert duplicate.json()["audit"]["audit_id"] == audit["audit_id"]
    assert duplicate.json()["audit"]["created_at"] == audit["created_at"]

    history = client.get(f"/api/projects/{project_id}/graph/evidence-audit-runs")
    assert history.status_code == 200
    assert history.json()["count"] == 1

    stored = client.get(f"/api/projects/{project_id}/graph/evidence-audit-runs/{audit['audit_id']}")
    assert stored.status_code == 200
    assert stored.json() == audit


def test_new_graph_checksum_creates_new_evidence_audit_run(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post("/api/projects", json={"name": "Evidence snapshots"}).json()
    project_id = project["project_id"]

    first = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs").json()["audit"]
    client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "dxf", "source_id": "new.dxf", "checksum": "f" * 64},
    )
    second_response = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs")
    assert second_response.status_code == 201
    second = second_response.json()["audit"]

    assert second["audit_id"] != first["audit_id"]
    assert second["graph_checksum"] != first["graph_checksum"]
    history = client.get(f"/api/projects/{project_id}/graph/evidence-audit-runs").json()
    assert history["count"] == 2


def test_compare_evidence_audit_runs_reports_finding_lifecycle(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post("/api/projects", json={"name": "Evidence comparison"}).json()
    project_id = project["project_id"]

    base = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs").json()["audit"]
    client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "pdf", "source_id": "unused.pdf", "checksum": "a" * 64},
    )
    target = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs").json()["audit"]

    response = client.get(
        f"/api/projects/{project_id}/graph/evidence-audit-runs/"
        f"{base['audit_id']}/compare/{target['audit_id']}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "total": 1,
        "new": 1,
        "persistent": 0,
        "no_longer_detected": 0,
    }
    assert payload["changes"][0]["lifecycle"] == "new"
    assert payload["metadata"] == {
        "comparison_only": True,
        "automatic_resolution_performed": False,
        "audit_runs_mutated": False,
        "graph_mutated": False,
        "evidence_mutated": False,
    }


def test_evidence_audit_finding_review_is_persistent_and_immutable(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post("/api/projects", json={"name": "Evidence finding review"}).json()
    project_id = project["project_id"]
    client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "pdf", "source_id": "unused.pdf", "checksum": "9" * 64},
    )
    audit = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs").json()[
        "audit"
    ]
    finding = audit["findings"][0]

    reviewed = client.post(
        f"/api/projects/{project_id}/graph/evidence-audit-runs/{audit['audit_id']}"
        f"/findings/{finding['finding_id']}/review",
        json={
            "decision": "acknowledge",
            "reviewer": "evidence-reviewer@example.test",
            "rationale": "Evidensposten ska kopplas till objekt efter manuell kontroll.",
            "decided_at": "2026-07-21T11:00:00+00:00",
        },
    )
    assert reviewed.status_code == 201
    body = reviewed.json()
    assert body["review_id"].startswith("evidence:finding-review:")
    assert body["finding_snapshot"] == finding
    assert body["ruleset_version"] == audit["metadata"]["ruleset_version"]
    assert body["metadata"] == {
        "human_review": True,
        "audit_mutated": False,
        "graph_mutated": False,
        "evidence_mutated": False,
        "automatic_repair_performed": False,
    }

    duplicate = client.post(
        f"/api/projects/{project_id}/graph/evidence-audit-runs/{audit['audit_id']}"
        f"/findings/{finding['finding_id']}/review",
        json={
            "decision": "dismiss",
            "reviewer": "second@example.test",
            "rationale": "Försök till ett andra beslut.",
        },
    )
    assert duplicate.status_code == 409

    history = client.get(
        f"/api/projects/{project_id}/graph/evidence-finding-reviews"
        f"?audit_id={audit['audit_id']}"
    )
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["finding_id"] == finding["finding_id"]

    stored = client.get(
        f"/api/projects/{project_id}/graph/evidence-audit-runs/{audit['audit_id']}"
    )
    assert stored.status_code == 200
    assert stored.json() == audit


def test_evidence_audit_comparison_includes_base_review_context(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post("/api/projects", json={"name": "Evidence review comparison"}).json()
    project_id = project["project_id"]
    evidence = client.post(
        f"/api/projects/{project_id}/graph/evidence",
        json={"kind": "pdf", "source_id": "unused.pdf", "checksum": "8" * 64},
    ).json()
    base = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs").json()[
        "audit"
    ]
    finding = base["findings"][0]
    review = client.post(
        f"/api/projects/{project_id}/graph/evidence-audit-runs/{base['audit_id']}"
        f"/findings/{finding['finding_id']}/review",
        json={
            "decision": "mark_resolved",
            "reviewer": "reviewer@example.test",
            "rationale": "Kopplingen är kontrollerad och införs i nästa graf-snapshot.",
            "decided_at": "2026-07-21T11:30:00+00:00",
        },
    ).json()
    client.post(
        f"/api/projects/{project_id}/graph/objects",
        json={
            "object_type": "document_reference",
            "discipline": "general",
            "object_id": "ccm:object:evidence-owner",
            "evidence_ids": [evidence["id"]],
        },
    )
    target = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs").json()[
        "audit"
    ]

    compared = client.get(
        f"/api/projects/{project_id}/graph/evidence-audit-runs/"
        f"{base['audit_id']}/compare/{target['audit_id']}"
    )
    assert compared.status_code == 200
    change = compared.json()["changes"][0]
    assert change["lifecycle"] == "no_longer_detected"
    assert change["metadata"]["resolution_status"] == "candidate_for_verification"
    assert change["metadata"]["base_review"] == {
        "review_id": review["review_id"],
        "decision": "mark_resolved",
        "reviewer": "reviewer@example.test",
        "decided_at": "2026-07-21T11:30:00+00:00",
    }


def test_graph_assurance_summary_aggregates_persisted_audits(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    created = client.post("/api/projects", json={"name": "Assuranceprojekt"})
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    initial = client.get(f"/api/projects/{project_id}/graph/assurance-summary")
    assert initial.status_code == 200
    assert initial.json()["status"] == "incomplete_audit_coverage"

    graph_run = client.post(f"/api/projects/{project_id}/graph/audit-runs")
    assert graph_run.status_code in {200, 201}
    evidence_run = client.post(f"/api/projects/{project_id}/graph/evidence-audit-runs")
    assert evidence_run.status_code in {200, 201}

    response = client.get(f"/api/projects/{project_id}/graph/assurance-summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domains"]["graph"]["audit_id"] == graph_run.json()["audit"]["audit_id"]
    assert payload["domains"]["evidence"]["audit_id"] == evidence_run.json()["audit"]["audit_id"]
    assert payload["metadata"]["read_only"] is True
    assert payload["metadata"]["technical_correctness_asserted"] is False
