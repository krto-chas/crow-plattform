from crow_geometry_framework import (
    BoundingBox2D,
    build_topology,
    connected_objects,
    consolidate_observations,
    discover_system_observations,
    dwg_adapter_status,
    geometry_from_import_manifest,
    geometry_index,
    identify_systems,
    nearest_objects,
    object_payload,
    object_system,
    objects_in_bbox,
    related_objects,
    search_geometry,
    segment_network,
    spatial_index_summary,
    system_observations,
    trace_network,
)


def test_dxf_manifest_normalizes_geometry():
    manifest = {
        "checksum_sha256": "a" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "VENT", "x1": 0, "y1": 0, "x2": 10, "y2": 20},
                {"type": "CIRCLE", "layer": "DON", "cx": 3, "cy": 4, "r": 2},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    assert len(doc.objects) == 2
    assert {layer.name for layer in doc.layers} == {"VENT", "DON"}
    assert doc.bounds is not None
    assert doc.bounds.max_y == 20


def test_dwg_status_never_claims_geometry_without_adapter(tmp_path):
    source = tmp_path / "sample.dwg"
    source.write_bytes(b"AC1032" + b"x" * 32)
    status = dwg_adapter_status(source)
    assert status["source_header"] == "AC1032"
    assert status["native_metadata"] is True
    assert status["conversion_target"] == "DXF"


def test_object_identity_is_stable_and_source_anchored():
    manifest = {
        "checksum_sha256": "b" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "VENT", "x1": 0, "y1": 0, "x2": 10, "y2": 20},
            ],
        },
    }
    first = geometry_from_import_manifest(manifest)
    second = geometry_from_import_manifest(manifest)
    assert first.objects[0].object_id == second.objects[0].object_id
    assert first.objects[0].identity.source_checksum == "b" * 64
    assert first.metadata["identity_version"] == "crow-object-id-v1"


def test_layer_state_is_applied_without_changing_objects():
    manifest = {
        "checksum_sha256": "c" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "CIRCLE", "layer": "DON", "cx": 3, "cy": 4, "r": 2},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest, {"DON": {"visible": False, "locked": True}})
    assert doc.layers[0].visible is False
    assert doc.layers[0].locked is True
    assert len(doc.objects) == 1


def test_geometry_search_filters_text_kind_and_layer():
    manifest = {
        "checksum_sha256": "d" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "TEXT", "layer": "VENT-TEXT", "x": 1, "y": 2, "text": "TD1-100"},
                {"type": "INSERT", "layer": "VENT-DON", "x": 3, "y": 4, "name": "TD1"},
                {"type": "LINE", "layer": "ARK", "x1": 0, "y1": 0, "x2": 5, "y2": 0},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    assert len(search_geometry(doc, text="TD1")) == 2
    assert len(search_geometry(doc, kinds=["text"])) == 1
    assert len(search_geometry(doc, layers=["ARK"])) == 1
    index = geometry_index(doc)
    assert index["kind_counts"]["text"] == 1
    assert index["blocks"][0]["name"] == "TD1"


def test_object_payload_contains_bounds_and_measurements():
    manifest = {
        "checksum_sha256": "e" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "VENT", "x1": 0, "y1": 0, "x2": 3, "y2": 4},
            ],
        },
    }
    item = geometry_from_import_manifest(manifest).objects[0]
    payload = object_payload(item)
    assert payload["measurements"]["length"] == 5.0
    assert payload["bounds"]["max_x"] == 3.0


def test_spatial_queries_find_nearest_and_bbox_objects():
    manifest = {
        "checksum_sha256": "f" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "TEXT", "layer": "TEXT", "x": 10, "y": 10, "text": "TD1"},
                {"type": "INSERT", "layer": "DON", "x": 12, "y": 10, "name": "TD1"},
                {"type": "LINE", "layer": "KANAL", "x1": 100, "y1": 100, "x2": 120, "y2": 100},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    nearest = nearest_objects(doc, x=10, y=10, max_distance=5, limit=10)
    assert [item.kind.value for item, _ in nearest][:2] == ["text", "insert"]
    inside = objects_in_bbox(doc, BoundingBox2D(9, 9, 13, 11))
    assert {item.kind.value for item in inside} == {"text", "insert"}
    summary = spatial_index_summary(doc)
    assert summary["indexed_object_count"] == 3


def test_related_objects_classifies_text_near_block():
    manifest = {
        "checksum_sha256": "1" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "TEXT", "layer": "TEXT", "x": 5, "y": 5, "text": "FD1"},
                {"type": "INSERT", "layer": "DON", "x": 6, "y": 5, "name": "FD1"},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    source = next(item for item in doc.objects if item.kind.value == "text")
    result = related_objects(doc, source.object_id, radius=10)
    assert result["items"][0]["relation"] == "text-near-block"


def test_topology_builds_nodes_edges_components_and_dangling_ends():
    manifest = {
        "checksum_sha256": "2" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10, "y1": 0, "x2": 20, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    graph = build_topology(doc)
    assert graph["node_count"] == 4
    assert graph["edge_count"] == 3
    assert graph["component_count"] == 1
    assert graph["dangling_node_count"] == 3
    assert graph["junction_node_count"] == 1


def test_connected_objects_uses_shared_endpoints_with_tolerance():
    manifest = {
        "checksum_sha256": "3" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10.0004, "y1": 0, "x2": 20, "y2": 0},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    result = connected_objects(doc, doc.objects[0].object_id, tolerance=0.001)
    assert result["items"][0]["object_id"] == doc.objects[1].object_id


def test_trace_network_follows_connected_objects_and_respects_depth():
    manifest = {
        "checksum_sha256": "4" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10, "y1": 0, "x2": 20, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 20, "y1": 0, "x2": 30, "y2": 0},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    full = trace_network(doc, doc.objects[0].object_id)
    limited = trace_network(doc, doc.objects[0].object_id, max_depth=1)
    assert full["object_count"] == 3
    assert full["max_depth_reached"] == 2
    assert limited["object_count"] == 2


def test_segment_network_splits_at_junctions():
    manifest = {
        "checksum_sha256": "5" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10, "y1": 0, "x2": 20, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    result = segment_network(doc)
    assert result["segment_count"] == 3
    assert result["boundary_node_count"] == 4
    assert sorted(segment["length"] for segment in result["segments"]) == [10.0, 10.0, 10.0]


def test_system_identification_classifies_branched_network_and_segments():
    manifest = {
        "checksum_sha256": "6" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10, "y1": 0, "x2": 20, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    result = identify_systems(doc)
    system = result["systems"][0]
    assert result["system_count"] == 1
    assert system["network_class"] == "branched"
    assert system["junction_count"] == 1
    assert system["total_length"] == 30.0
    assert {segment["role"] for segment in system["segments"]} == {"terminal_branch"}


def test_object_system_returns_stable_membership():
    manifest = {
        "checksum_sha256": "7" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 5, "y2": 0},
                {"type": "LINE", "layer": "KANAL", "x1": 5, "y1": 0, "x2": 10, "y2": 0},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    result = object_system(doc, doc.objects[0].object_id)
    assert result["connected_system"] is True
    assert result["system"]["network_class"] == "linear"
    assert result["membership"]["system_id"].startswith("system-")


def test_observations_link_text_and_block_candidates_to_network():
    manifest = {
        "checksum_sha256": "8" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
                {"type": "TEXT", "layer": "TEXT", "x": 5, "y": 2, "text": "TD1"},
                {"type": "INSERT", "layer": "DON", "x": 10, "y": 1, "name": "TD1"},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    result = discover_system_observations(doc, association_radius=5)
    assert result["observation_count"] == 2
    assert {item["observation_type"] for item in result["observations"]} == {
        "label_candidate",
        "component_candidate",
    }
    assert all(item["domain_semantics"] is False for item in result["observations"])


def test_system_observations_filters_to_requested_system_and_is_stable():
    manifest = {
        "checksum_sha256": "9" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "A", "x1": 0, "y1": 0, "x2": 5, "y2": 0},
                {"type": "LINE", "layer": "B", "x1": 100, "y1": 0, "x2": 105, "y2": 0},
                {"type": "TEXT", "layer": "TEXT", "x": 2, "y": 1, "text": "A1"},
            ],
        },
    }
    doc = geometry_from_import_manifest(manifest)
    systems = identify_systems(doc)["systems"]
    target = next(system for system in systems if "A" in system["layers"])
    first = system_observations(doc, target["system_id"], association_radius=10)
    second = system_observations(doc, target["system_id"], association_radius=10)
    assert first == second
    assert first["observation_count"] == 1
    assert first["observations"][0]["candidate_value"] == "A1"


def test_consolidation_merges_duplicate_candidates_and_ranks_them():
    manifest = {
        "checksum_sha256": "a" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 20, "y2": 0},
                {"type": "TEXT", "layer": "TEXT", "x": 2, "y": 1, "text": "TD1"},
                {"type": "TEXT", "layer": "TEXT", "x": 4, "y": 1, "text": " td1 "},
            ],
        },
    }
    result = consolidate_observations(
        geometry_from_import_manifest(manifest), association_radius=10
    )
    assert result["candidate_group_count"] == 1
    assert result["candidates"][0]["evidence_count"] == 2
    assert result["candidates"][0]["rank"] == 1


def test_consolidation_marks_conflicting_labels_for_review():
    manifest = {
        "checksum_sha256": "b" * 64,
        "format_id": "dxf",
        "warnings": [],
        "preview": {
            "kind": "dxf_2d",
            "geometry": [
                {"type": "LINE", "layer": "KANAL", "x1": 0, "y1": 0, "x2": 20, "y2": 0},
                {"type": "TEXT", "layer": "TEXT", "x": 2, "y": 1, "text": "TD1"},
                {"type": "TEXT", "layer": "TEXT", "x": 3, "y": 1, "text": "FD1"},
            ],
        },
    }
    result = consolidate_observations(
        geometry_from_import_manifest(manifest), association_radius=10
    )
    assert result["conflict_set_count"] == 1
    assert all(item["conflict"] for item in result["candidates"])
    assert all(item["review_status"] == "needs_review" for item in result["candidates"])
