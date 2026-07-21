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
