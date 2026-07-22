from pathlib import Path

from crow_building_graph import BuildingGraphService, GraphRepository
from crow_canonical import CanonicalGraphBridge, CanonicalObjectType, VentCanonicalAdapter
from crow_vent import VentTextInterpreter


def test_duct_interpretation_becomes_canonical_object() -> None:
    interpretation = VentTextInterpreter().interpret(
        "T13-250x400-V1",
        source_id="drawing-1",
        layer="V-57--",
        entity_handle="ABC1",
    )
    canonical = VentCanonicalAdapter().convert(interpretation)
    assert canonical is not None
    assert canonical.object_type is CanonicalObjectType.DUCT
    assert canonical.properties["medium"] == "Tilluft"
    assert canonical.properties["width_mm"] == 250
    assert canonical.evidence.locator == "ABC1"


def test_component_category_maps_to_canonical_type() -> None:
    interpretation = VentTextInterpreter().interpret(
        "TD1", source_id="drawing-1", layer="DON", entity_handle="D1"
    )
    canonical = VentCanonicalAdapter().convert(interpretation)
    assert canonical is not None
    assert canonical.object_type is CanonicalObjectType.AIR_TERMINAL
    assert canonical.properties["code"] == "TD"


def test_unknown_text_is_not_forced_into_ccm() -> None:
    interpretation = VentTextInterpreter().interpret(
        "HELT OKÄND", source_id="drawing-1", layer="MYSTERY"
    )
    assert VentCanonicalAdapter().convert(interpretation) is None


def test_canonical_object_persists_with_shared_evidence(tmp_path: Path) -> None:
    interpretation = VentTextInterpreter().interpret(
        "T13-250x400-V1",
        source_id="drawing-1",
        layer="V-57--",
        entity_handle="ABC1",
    )
    canonical = VentCanonicalAdapter().convert(interpretation)
    assert canonical is not None
    graph = BuildingGraphService(GraphRepository(tmp_path / "graph.json"))
    result = CanonicalGraphBridge(graph).persist(canonical)

    assert result["object"]["object_type"] == "duct"
    evidence_id = result["evidence"]["id"]
    assert result["object"]["evidence_ids"] == (evidence_id,)
    assert result["properties"]
    assert all(item["evidence_ids"] == (evidence_id,) for item in result["properties"])
    assert graph.graph()["summary"]["objects"] == 1


def test_assembler_creates_system_and_explicit_membership() -> None:
    interpreter = VentTextInterpreter()
    rows = [
        interpreter.interpret(
            "TD1", source_id="drawing-1", layer="DON", entity_handle="D1", system_context="LB01"
        ),
        interpreter.interpret(
            "SP1", source_id="drawing-1", layer="V-57--", entity_handle="S1", system_context="LB01"
        ),
    ]
    from crow_canonical import VentCanonicalAssembler

    assembly = VentCanonicalAssembler().assemble(rows)
    systems = [
        item
        for item in assembly.objects
        if item.object_type is CanonicalObjectType.VENTILATION_SYSTEM
    ]
    assert len(systems) == 1
    assert systems[0].name == "LB01"
    assert len(assembly.relations) == 2
    assert all(item.relation_type == "belongs_to" for item in assembly.relations)
    assert all(item.target_id == systems[0].canonical_id for item in assembly.relations)


def test_assembly_persists_objects_before_relations(tmp_path: Path) -> None:
    interpreter = VentTextInterpreter()
    rows = [
        interpreter.interpret(
            "TD1", source_id="drawing-1", layer="DON", entity_handle="D1", system_context="LB01"
        )
    ]
    from crow_canonical import VentCanonicalAssembler

    assembly = VentCanonicalAssembler().assemble(rows)
    graph = BuildingGraphService(GraphRepository(tmp_path / "assembly-graph.json"))
    result = CanonicalGraphBridge(graph).persist_assembly(assembly)
    assert len(result["objects"]) == 2
    assert len(result["relations"]) == 1
    snapshot = graph.graph()
    assert snapshot["summary"]["objects"] == 2
    assert snapshot["summary"]["relations"] == 1
    assert snapshot["relations"][0]["relation_type"] == "belongs_to"


def test_exact_designation_in_same_system_creates_identity_candidate() -> None:
    interpreter = VentTextInterpreter()
    rows = [
        interpreter.interpret(
            "TD1",
            source_id="drawing-plan-1",
            layer="DON",
            entity_handle="D1",
            system_context="LB01",
        ),
        interpreter.interpret(
            "TD1",
            source_id="drawing-detail-1",
            layer="V-57--",
            entity_handle="D99",
            system_context="LB01",
        ),
    ]
    from crow_canonical import VentCanonicalAssembler

    assembly = VentCanonicalAssembler().assemble(rows)
    candidates = [item for item in assembly.relations if item.relation_type == "same_as_candidate"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.metadata["derivation"] == "exact_designation_and_system_context"
    assert candidate.metadata["status"] == "review_required"
    assert candidate.metadata["identity_key"] == {
        "object_type": "air_terminal",
        "code": "TD",
        "number": "1",
        "system_context": "LB01",
    }


def test_same_designation_in_different_systems_is_not_linked() -> None:
    interpreter = VentTextInterpreter()
    rows = [
        interpreter.interpret(
            "TD1", source_id="drawing-1", layer="DON", system_context="LB01"
        ),
        interpreter.interpret(
            "TD1", source_id="drawing-2", layer="DON", system_context="LB02"
        ),
    ]
    from crow_canonical import VentCanonicalAssembler

    assembly = VentCanonicalAssembler().assemble(rows)
    assert not any(item.relation_type == "same_as_candidate" for item in assembly.relations)


def test_duct_text_is_not_used_as_component_identity_candidate() -> None:
    interpreter = VentTextInterpreter()
    rows = [
        interpreter.interpret(
            "T1-250", source_id="drawing-1", layer="KANAL", system_context="LB01"
        ),
        interpreter.interpret(
            "T1-250", source_id="drawing-2", layer="KANAL", system_context="LB01"
        ),
    ]
    from crow_canonical import VentCanonicalAssembler

    assembly = VentCanonicalAssembler().assemble(rows)
    assert not any(item.relation_type == "same_as_candidate" for item in assembly.relations)


def _identity_candidate():
    from crow_canonical import VentCanonicalAssembler

    interpreter = VentTextInterpreter()
    assembly = VentCanonicalAssembler().assemble(
        [
            interpreter.interpret(
                "TD1",
                source_id="drawing-plan-1",
                layer="DON",
                entity_handle="D1",
                system_context="LB01",
            ),
            interpreter.interpret(
                "TD1",
                source_id="drawing-detail-1",
                layer="V-57--",
                entity_handle="D99",
                system_context="LB01",
            ),
        ]
    )
    return next(item for item in assembly.relations if item.relation_type == "same_as_candidate")


def test_identity_candidate_can_be_confirmed_without_merging_observations() -> None:
    from crow_canonical import IdentityReviewDecision, IdentityReviewService

    result = IdentityReviewService().decide(
        _identity_candidate(),
        decision=IdentityReviewDecision.CONFIRM_SAME,
        reviewer="reviewer@example.test",
        rationale="Plan- och detaljritning avser samma märkta don.",
        decided_at="2026-07-21T06:30:00+00:00",
    )
    assert result.resolved_relation.relation_type == "same_as_confirmed"
    assert result.resolved_relation.metadata["status"] == "reviewed"
    assert result.resolved_relation.metadata["automatic_merge_performed"] is False
    assert result.resolved_relation.metadata["source_observations_preserved"] is True
    assert (
        result.resolved_relation.metadata["candidate_relation_id"]
        == _identity_candidate().canonical_id
    )


def test_identity_candidate_can_be_rejected_explicitly() -> None:
    from crow_canonical import IdentityReviewDecision, IdentityReviewService

    result = IdentityReviewService().decide(
        _identity_candidate(),
        decision=IdentityReviewDecision.REJECT_SAME,
        reviewer="reviewer@example.test",
        rationale="Beteckningen återanvänds för två separata don.",
        decided_at="2026-07-21T06:31:00+00:00",
    )
    assert result.resolved_relation.relation_type == "not_same_as"
    assert result.resolved_relation.metadata["decision"] == "reject_same"


def test_identity_review_rejects_non_candidate_relation() -> None:
    import pytest

    from crow_canonical import IdentityReviewDecision, IdentityReviewService

    candidate = _identity_candidate()
    not_candidate = type(candidate)(
        canonical_id=candidate.canonical_id,
        source_id=candidate.source_id,
        relation_type="belongs_to",
        target_id=candidate.target_id,
        confidence=candidate.confidence,
        evidence=candidate.evidence,
        metadata=candidate.metadata,
    )
    with pytest.raises(ValueError, match="same_as_candidate"):
        IdentityReviewService().decide(
            not_candidate,
            decision=IdentityReviewDecision.CONFIRM_SAME,
            reviewer="reviewer@example.test",
            rationale="irrelevant",
        )


def test_reviewed_identity_relation_persists_with_audit_metadata(tmp_path: Path) -> None:
    from crow_canonical import (
        IdentityReviewDecision,
        IdentityReviewService,
        VentCanonicalAssembler,
    )

    interpreter = VentTextInterpreter()
    assembly = VentCanonicalAssembler().assemble(
        [
            interpreter.interpret(
                "TD1",
                source_id="drawing-plan-1",
                layer="DON",
                entity_handle="D1",
                system_context="LB01",
            ),
            interpreter.interpret(
                "TD1",
                source_id="drawing-detail-1",
                layer="V-57--",
                entity_handle="D99",
                system_context="LB01",
            ),
        ]
    )
    candidate = next(
        item for item in assembly.relations if item.relation_type == "same_as_candidate"
    )
    reviewed = IdentityReviewService().decide(
        candidate,
        decision=IdentityReviewDecision.CONFIRM_SAME,
        reviewer="reviewer@example.test",
        rationale="Verifierad mot båda ritningarna.",
        decided_at="2026-07-21T06:32:00+00:00",
    )
    graph = BuildingGraphService(GraphRepository(tmp_path / "reviewed-identity.json"))
    bridge = CanonicalGraphBridge(graph)
    for item in assembly.objects:
        bridge.persist(item)
    persisted = bridge.persist_relation(reviewed.resolved_relation)
    assert persisted["relation"]["relation_type"] == "same_as_confirmed"
    assert persisted["relation"]["metadata"]["reviewer"] == "reviewer@example.test"
    assert persisted["relation"]["metadata"]["automatic_merge_performed"] is False


def test_explicit_relationship_assertion_creates_evidence_bearing_relation() -> None:
    from crow_canonical import (
        CanonicalEvidence,
        CanonicalRelationshipEngine,
        CanonicalRelationType,
        ExplicitRelationAssertion,
        VentCanonicalAssembler,
    )

    interpreter = VentTextInterpreter()
    assembly = VentCanonicalAssembler().assemble(
        [
            interpreter.interpret(
                "TA1", source_id="drawing-1", layer="V-57--", entity_handle="A1"
            ),
            interpreter.interpret(
                "TD1", source_id="drawing-1", layer="DON", entity_handle="D1"
            ),
        ]
    )
    source, target = assembly.objects
    evidence = CanonicalEvidence(
        source_id="ifc-1",
        source_kind="ifc",
        locator="#4242",
        confidence=1.0,
        metadata={"ifc_relation": "IfcRelConnectsElements"},
    )
    result = CanonicalRelationshipEngine().apply(
        assembly,
        [
            ExplicitRelationAssertion(
                source_id=source.canonical_id,
                relation_type=CanonicalRelationType.FEEDS,
                target_id=target.canonical_id,
                evidence=evidence,
                metadata={"source_semantics": "explicit_ifc_relation"},
            )
        ],
    )
    relation = next(item for item in result.relations if item.relation_type == "feeds")
    assert relation.evidence.source_kind == "ifc"
    assert relation.metadata["derivation"] == "explicit_relation_assertion"
    assert relation.metadata["inference_performed"] is False


def test_relationship_engine_rejects_unknown_endpoint() -> None:
    import pytest

    from crow_canonical import (
        CanonicalEvidence,
        CanonicalRelationshipEngine,
        CanonicalRelationType,
        ExplicitRelationAssertion,
        VentCanonicalAssembler,
    )

    assembly = VentCanonicalAssembler().assemble(
        [VentTextInterpreter().interpret("TD1", source_id="drawing-1", layer="DON")]
    )
    with pytest.raises(KeyError, match="missing-object"):
        CanonicalRelationshipEngine().apply(
            assembly,
            [
                ExplicitRelationAssertion(
                    source_id=assembly.objects[0].canonical_id,
                    relation_type=CanonicalRelationType.LOCATED_IN,
                    target_id="missing-object",
                    evidence=CanonicalEvidence(
                        source_id="manual-1",
                        source_kind="manual",
                        locator=None,
                        confidence=1.0,
                    ),
                )
            ],
        )


def test_explicit_relation_persists_in_building_graph(tmp_path: Path) -> None:
    from crow_canonical import (
        CanonicalEvidence,
        CanonicalRelationshipEngine,
        CanonicalRelationType,
        ExplicitRelationAssertion,
        VentCanonicalAssembler,
    )

    interpreter = VentTextInterpreter()
    assembly = VentCanonicalAssembler().assemble(
        [
            interpreter.interpret("FF1", source_id="drawing-1", layer="V-57--"),
            interpreter.interpret("FD1", source_id="drawing-1", layer="DON"),
        ]
    )
    source, target = assembly.objects
    assembly = CanonicalRelationshipEngine().apply(
        assembly,
        [
            ExplicitRelationAssertion(
                source_id=target.canonical_id,
                relation_type=CanonicalRelationType.RETURNS_FROM,
                target_id=source.canonical_id,
                evidence=CanonicalEvidence(
                    source_id="ifc-1",
                    source_kind="ifc",
                    locator="#500",
                    confidence=0.98,
                ),
            )
        ],
    )
    graph = BuildingGraphService(GraphRepository(tmp_path / "relations.json"))
    result = CanonicalGraphBridge(graph).persist_assembly(assembly)
    assert any(item["relation"]["relation_type"] == "returns_from" for item in result["relations"])


def test_provenance_trace_exposes_source_and_canonical_stages() -> None:
    from crow_canonical import CanonicalProvenanceService, VentCanonicalAdapter

    interpretation = VentTextInterpreter().interpret(
        "TD1", source_id="drawing-1", layer="DON", entity_handle="D1"
    )
    canonical = VentCanonicalAdapter().convert(interpretation)
    assert canonical is not None
    trace = CanonicalProvenanceService().for_object(canonical)
    assert [step.stage for step in trace.steps] == [
        "source",
        "interpretation",
        "canonical_object",
    ]
    assert trace.steps[0].reference == "drawing-1"
    assert trace.steps[-1].reference == canonical.canonical_id
