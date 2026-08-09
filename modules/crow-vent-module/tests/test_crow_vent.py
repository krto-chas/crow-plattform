from crow_vent import build_vent_model, component_registry, resolve_component


def test_registry_resolves_numbered_symbols():
    assert resolve_component("TD1").name_sv == "Tilluftsdon"
    assert resolve_component("FD-03").airflow_role == "extract"
    assert resolve_component("okänd") is None


def test_build_vent_model_keeps_geometry_provenance():
    payload = {
        "candidates": [
            {
                "candidate_group_id": "candidate-1",
                "system_id": "system-1",
                "display_value": "TD1",
                "score": 0.9,
                "conflict": False,
                "observation_ids": ["obs-1"],
                "candidate_object_ids": ["obj-1"],
            }
        ]
    }
    result = build_vent_model(payload)
    assert result["classified_count"] == 1
    assert result["systems"][0]["airflow_role"] == "supply"
    assert result["classifications"][0]["evidence"]["geometry_candidate"] == "candidate-1"


def test_registry_has_initial_component_set():
    assert len(component_registry()) >= 15


def test_vent_02_detects_mixed_airflow_roles():
    payload = {
        "candidates": [
            {"candidate_group_id": "c1", "system_id": "s1", "display_value": "TD1", "score": 0.9},
            {"candidate_group_id": "c2", "system_id": "s1", "display_value": "FD1", "score": 0.9},
        ]
    }
    result = build_vent_model(payload)
    assert result["vent_schema_version"] == "crow-vent-v0.3"
    assert any(item["code"] == "VENT.MIXED_AIRFLOW_ROLES" for item in result["findings"])
    assert result["systems"][0]["status"] == "needs_review"


def test_vent_02_builds_relations_between_unit_and_terminal():
    payload = {
        "candidates": [
            {"candidate_group_id": "c1", "system_id": "s1", "display_value": "TA01", "score": 0.9},
            {"candidate_group_id": "c2", "system_id": "s1", "display_value": "TD1", "score": 0.9},
            {"candidate_group_id": "c3", "system_id": "s1", "display_value": "LD1", "score": 0.9},
        ]
    }
    result = build_vent_model(payload)
    relation_types = {item["relation_type"] for item in result["relations"]}
    assert "serves" in relation_types
    assert "inline_component" in relation_types
    assert result["systems"][0]["system_kind"] == "tilluft"


def test_vent_03_builds_quantity_takeoff_and_dimensions():
    payload = {
        "candidates": [
            {
                "candidate_group_id": "c1",
                "system_id": "s1",
                "display_value": "TD1 Ø160",
                "score": 0.95,
            },
            {
                "candidate_group_id": "c2",
                "system_id": "s1",
                "display_value": "TD2 Ø160",
                "score": 0.95,
            },
            {
                "candidate_group_id": "c3",
                "system_id": "s1",
                "display_value": "FD1 300x200",
                "score": 0.95,
            },
        ]
    }
    result = build_vent_model(payload)
    assert result["vent_schema_version"] == "crow-vent-v0.3"
    takeoff = result["quantity_takeoff"]
    assert takeoff["total_component_count"] == 3
    assert any(line["dimension"] == "Ø160" and line["quantity"] == 2 for line in takeoff["lines"])
    assert any(line["dimension"] == "300x200" for line in takeoff["lines"])


def test_vent_03_exports_semicolon_csv():
    from crow_vent import quantity_takeoff_csv

    takeoff = {
        "lines": [
            {
                "component_code": "TD",
                "component_name": "Tilluftsdon",
                "category": "terminal",
                "dimension": "Ø160",
                "quantity": 2,
                "length_m": None,
                "system_ids": ["vent:s1"],
            }
        ]
    }
    csv_text = quantity_takeoff_csv(takeoff)
    assert "Komponentkod;Komponent" in csv_text
    assert "TD;Tilluftsdon;terminal;Ø160;2;;vent:s1" in csv_text
