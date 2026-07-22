from crow_vent import VentGraphAudit


def _object(object_id: str, object_type: str, evidence: bool = True) -> dict[str, object]:
    return {
        "id": object_id,
        "object_type": object_type,
        "discipline": "VENT",
        "evidence_ids": [f"evidence:{object_id}"] if evidence else [],
    }


def _relation(
    relation_id: str,
    source_id: str,
    relation_type: str,
    target_id: str,
    evidence: bool = True,
) -> dict[str, object]:
    return {
        "id": relation_id,
        "source_id": source_id,
        "relation_type": relation_type,
        "target_id": target_id,
        "evidence_ids": [f"evidence:{relation_id}"] if evidence else [],
    }


def test_missing_feed_is_evidence_gap_not_design_defect() -> None:
    result = VentGraphAudit().audit({"objects": [_object("td1", "air_terminal")], "relations": []})

    finding = next(item for item in result.findings if item.rule_id == "VENT-EVID-001")
    assert finding.category == "evidence_gap"
    assert finding.status == "review_required"
    assert finding.metadata["design_defect_asserted"] is False
    assert result.summary["proven_design_defect"] == 0
    assert result.metadata["missing_information_treated_as_defect"] is False


def test_explicit_feed_removes_feed_gap_but_not_system_gap() -> None:
    graph = {
        "objects": [_object("duct1", "duct"), _object("td1", "air_terminal")],
        "relations": [_relation("r1", "duct1", "feeds", "td1")],
    }

    result = VentGraphAudit().audit(graph)

    assert not any(item.rule_id == "VENT-EVID-001" for item in result.findings)
    assert {item.object_ids for item in result.findings if item.rule_id == "VENT-EVID-002"} == {
        ("duct1",),
        ("td1",),
    }


def test_explicit_system_membership_removes_system_gap() -> None:
    graph = {
        "objects": [
            _object("lb01", "ventilation_system"),
            _object("td1", "air_terminal"),
            _object("duct1", "duct"),
        ],
        "relations": [
            _relation("r1", "duct1", "feeds", "td1"),
            _relation("r2", "td1", "belongs_to", "lb01"),
            _relation("r3", "duct1", "belongs_to", "lb01"),
        ],
    }

    result = VentGraphAudit().audit(graph)

    assert result.findings == ()
    assert result.summary["total"] == 0


def test_relation_without_evidence_is_verified_data_quality_finding() -> None:
    graph = {
        "objects": [_object("duct1", "duct"), _object("td1", "air_terminal")],
        "relations": [_relation("r1", "duct1", "feeds", "td1", evidence=False)],
    }

    result = VentGraphAudit().audit(graph)

    finding = next(item for item in result.findings if item.rule_id == "VENT-DQ-002")
    assert finding.category == "data_quality"
    assert finding.status == "verified"
    assert finding.relation_ids == ("r1",)


def test_dangling_relation_is_reported_deterministically() -> None:
    graph = {
        "objects": [_object("duct1", "duct")],
        "relations": [_relation("r1", "duct1", "feeds", "missing")],
    }

    first = VentGraphAudit().audit(graph)
    second = VentGraphAudit().audit(graph)

    finding = next(item for item in first.findings if item.rule_id == "VENT-DQ-001")
    assert finding.object_ids == ("missing",)
    assert finding.finding_id == next(
        item.finding_id for item in second.findings if item.rule_id == "VENT-DQ-001"
    )
