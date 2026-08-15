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
        ("typed_by", "#30", "#999"),
    ]
    assert extraction.unsupported_relation_entity_counts == {}
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
        "IFCRELASSIGNSTOGROUP": 9,
        "IFCRELASSOCIATESMATERIAL": 2,
        "IFCRELCONTAINEDINSPATIALSTRUCTURE": 1,
        "IFCRELCOVERSBLDGELEMENTS": 19,
        "IFCRELDEFINESBYTYPE": 104,
        "IFCRELSERVICESBUILDINGS": 9,
    }
    assert extraction.unsupported_relation_entity_counts == {}
    assert not extraction.malformed_supported_entities
    assert len(extraction.relations) >= 4


def test_extracts_extended_explicit_ifc_relationships() -> None:
    text = """
#200=IFCRELDEFINESBYTYPE('d',$,$,$,(#30,#31),#900);
#201=IFCRELASSIGNSTOGROUP('g',$,$,$,(#30,#31),$,#901);
#202=IFCRELSERVICESBUILDINGS('s',$,$,$,#902,(#10,#11));
#203=IFCRELASSOCIATESMATERIAL('m',$,$,$,(#30,#31),#903);
#204=IFCRELCOVERSBLDGELEMENTS('c',$,$,$,#40,(#41,#42));
"""
    extraction = IfcRelationExtractor().extract_text(text, source_id="fixture.ifc")

    relation_tuples = [
        (item.relation_type.value, item.source_ifc_id, item.target_ifc_id)
        for item in extraction.relations
    ]
    assert relation_tuples == [
        ("typed_by", "#30", "#900"),
        ("typed_by", "#31", "#900"),
        ("assigned_to", "#30", "#901"),
        ("assigned_to", "#31", "#901"),
        ("serves", "#902", "#10"),
        ("serves", "#902", "#11"),
        ("associated_with_material", "#30", "#903"),
        ("associated_with_material", "#31", "#903"),
        ("covers", "#40", "#41"),
        ("covers", "#40", "#42"),
    ]
    assert extraction.unsupported_relation_entity_counts == {}
    assert extraction.metadata["schema"] == "crow-ifc-explicit-relations-v0.2"


def test_extended_ifc_relation_mapping_remains_explicit_and_evidence_bound() -> None:
    extraction = IfcRelationExtractor().extract_text(
        "#200=IFCRELDEFINESBYTYPE('d',$,$,$,(#30),#900);",
        source_id="fixture.ifc",
    )
    mapped = IfcRelationExtractor().map_to_assertions(
        extraction,
        {"#30": "ccm:terminal", "#900": "ccm:terminal-type"},
    )

    assert len(mapped.assertions) == 1
    assertion = mapped.assertions[0]
    assert assertion.relation_type.value == "typed_by"
    assert assertion.source_id == "ccm:terminal"
    assert assertion.target_id == "ccm:terminal-type"
    assert assertion.evidence.locator == "#200"
    assert mapped.metadata["automatic_object_creation_performed"] is False
