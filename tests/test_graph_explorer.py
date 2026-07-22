from pathlib import Path

from fastapi.testclient import TestClient

from crow_graph_explorer import GraphExplorerBuilder
from crow_workbench.app import create_app


def test_graph_explorer_builds_read_only_projection() -> None:
    payload = GraphExplorerBuilder().build(
        {
            "objects": [
                {
                    "id": "o1",
                    "object_type": "air_terminal",
                    "discipline": "vent",
                    "name": "TD1",
                    "evidence_ids": ["e1"],
                },
                {
                    "id": "o2",
                    "object_type": "system",
                    "discipline": "vent",
                    "name": "TA01",
                    "evidence_ids": [],
                },
            ],
            "relations": [
                {
                    "id": "r1",
                    "source_id": "o1",
                    "target_id": "o2",
                    "relation_type": "belongs_to",
                    "evidence_ids": ["missing"],
                }
            ],
            "properties": [
                {
                    "id": "p1",
                    "owner_id": "o1",
                    "name": "flow",
                    "value": 25,
                    "unit": "l/s",
                    "evidence_ids": ["e1"],
                }
            ],
            "evidence": [{"id": "e1", "kind": "dxf", "source_id": "plan.dxf"}],
            "history": [],
        }
    )
    assert payload["summary"] == {
        "objects": 2,
        "relations": 1,
        "properties": 1,
        "evidence": 1,
        "referenced_evidence": 1,
        "unreferenced_evidence": 0,
        "dangling_relations": 0,
    }
    node = next(item for item in payload["nodes"] if item["id"] == "o1")
    assert node["property_count"] == 1
    assert node["evidence"][0]["id"] == "e1"
    assert payload["edges"][0]["missing_evidence_ids"] == ["missing"]
    assert payload["metadata"]["graph_mutated"] is False


def test_graph_explorer_endpoint_returns_building_graph(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Graph project", "project_id": "graph-project"})
    evidence = client.post(
        "/api/projects/graph-project/graph/evidence",
        json={"kind": "manual", "source_id": "review", "locator": "row-1"},
    ).json()
    obj = client.post(
        "/api/projects/graph-project/graph/objects",
        json={
            "object_type": "air_terminal",
            "discipline": "vent",
            "name": "TD1",
            "evidence_ids": [evidence["id"]],
        },
    ).json()

    response = client.get("/api/projects/graph-project/graph/explorer")

    assert response.status_code == 200
    assert response.json()["nodes"][0]["id"] == obj["id"]
    assert response.json()["summary"]["evidence"] == 1
    assert response.json()["metadata"]["read_only"] is True
