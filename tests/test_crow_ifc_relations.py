from pathlib import Path

from crow_canonical.assembly import CanonicalAssembly
from crow_canonical.models import CanonicalEvidence, CanonicalObject, CanonicalObjectType
from crow_canonical.relations import CanonicalRelationshipEngine
from crow_ifc_relations import IfcRelationExtractor


def _obj(object_id: str, object_type: CanonicalObjectType) -> CanonicalObject:
    return CanonicalObject(
        canonical_id=object_id,
        object_type=object_type,
        discipline="VENT",
        name=object_id,
        confidence=1.0,
        properties={},
        evidence=CanonicalEvidence("fixture.ifc", "ifc_entity", "#1", 1.0),
    )


def test_extracts_explicit_aggregate_and_spatial_relations() -> None:
    text = """ISO-10303-21;
#10=IFCBUILDING('b',$,'Building',$,$,$,$,$,$,$,$,$);
#20=IFCBUILDINGSTOREY('s',$,'Plan 1',$,$,$,$,$,$,$);
#30=IFCFLOWTERMINAL('t',$,'TD1',$,$,$,$,$);
#100=IFCRELAGGREGATES('r',$,$,$,#10,(#20));
#101=IFCRELCONTAINEDINSPATIALSTRUCTURE('c',$,$,$,(#30),#20);
#102=IFCRELDEFINESBYTYPE('d',$,$,$,(#30),#999);
ENDSEC;
"""
    extraction = IfcRelationExtractor().extract_text(text, source_id="fixture.ifc")

    relation_tuples = [
        (item.relation_type.value, item.source_ifc_id, item.target_ifc_id)
        for item in extraction.relations
    ]
    assert relation_tuples == [
        ("contains", "#10", "#20"),
        ("located_in", "#30", "#20"),
    ]
    assert extraction.unsupported_relation_entity_counts == {"IFCRELDEFINESBYTYPE": 1}
    assert extraction.metadata["inference_performed"] is False


def test_maps_only_when_both_ifc_objects_are_known() -> None:
    extraction = IfcRelationExtractor().extract_text(
        "#100=IFCRELAGGREGATES('r',$,$,$,#10,(#20,#21));",
        source_id="fixture.ifc",
    )
    mapped = IfcRelationExtractor().map_to_assertions(
        extraction,
        {"#10": "ccm:building", "#20": "ccm:storey"},
    )

    assert len(mapped.assertions) == 1
    assert mapped.unmapped_ifc_ids == ("#21",)
    assert mapped.skipped_relation_entity_ids == ("#100",)
    assertion = mapped.assertions[0]
    assert assertion.source_id == "ccm:building"
    assert assertion.target_id == "ccm:storey"
    assert assertion.evidence.locator == "#100"
    assert assertion.metadata["derivation_source"] == "explicit_ifc_relationship"


def test_explicit_ifc_assertion_can_be_persisted_in_canonical_assembly() -> None:
    extraction = IfcRelationExtractor().extract_text(
        "#101=IFCRELCONTAINEDINSPATIALSTRUCTURE('c',$,$,$,(#30),#20);",
        source_id="fixture.ifc",
    )
    mapped = IfcRelationExtractor().map_to_assertions(
        extraction,
        {"#30": "ccm:terminal", "#20": "ccm:storey"},
    )
    assembly = CanonicalAssembly(
        objects=(
            _obj("ccm:terminal", CanonicalObjectType.AIR_TERMINAL),
            _obj("ccm:storey", CanonicalObjectType.ACCESSORY),
        ),
        relations=(),
    )

    result = CanonicalRelationshipEngine().apply(assembly, list(mapped.assertions))

    assert len(result.relations) == 1
    relation = result.relations[0]
    assert relation.relation_type == "located_in"
    assert relation.metadata["ifc_relation_entity_type"] == "IFCRELCONTAINEDINSPATIALSTRUCTURE"
    assert relation.metadata["inference_performed"] is False


def test_real_ifc_relation_inventory_is_reproducible() -> None:
    path = Path("/mnt/data/V-50-1-01.ifc")
    if not path.exists():
        return

    extraction = IfcRelationExtractor().extract_path(path)

    assert extraction.relation_entity_counts["IFCRELAGGREGATES"] == 3
    assert extraction.relation_entity_counts["IFCRELCONTAINEDINSPATIALSTRUCTURE"] == 1
    assert extraction.supported_relation_entity_counts == {
        "IFCRELAGGREGATES": 3,
        "IFCRELCONTAINEDINSPATIALSTRUCTURE": 1,
    }
    assert not extraction.malformed_supported_entities
    assert len(extraction.relations) >= 4
