from __future__ import annotations

import pytest

from crow_ovk import FindingSeverity
from crow_ovk_field import (
    FieldFinding,
    FieldInspectionData,
    FieldRoom,
    FieldUnit,
    OvkPhotoEvidence,
    UnitKind,
    defect_type_by_id,
    validate_field_data,
)


def _photo(**overrides: object) -> OvkPhotoEvidence:
    values: dict[str, object] = {
        "photo_id": "photo-1",
        "inspection_id": "inspection-1",
        "unit_id": "unit-1203",
        "unit_number": "1203",
        "defect_type": "contaminated_extract_terminal",
        "captured_at": "2026-08-09T00:30:00+02:00",
        "captured_by": "inspector-1",
        "local_uri": "indexeddb://photos/photo-1.jpg",
        "sha256": "a" * 64,
        "mime_type": "image/jpeg",
        "room_id": "room-bath",
        "finding_id": "finding-1",
        "rule_refs": ("PBF:5:1-7",),
    }
    values.update(overrides)
    return OvkPhotoEvidence(**values)  # type: ignore[arg-type]


def test_photo_requires_apartment_number_and_defect_type() -> None:
    with pytest.raises(ValueError, match="unit binding or a technical space"):
        _photo(unit_number="")
    with pytest.raises(ValueError, match="defect_type"):
        _photo(defect_type="")


def test_photo_requires_image_mime_and_sha256() -> None:
    with pytest.raises(ValueError, match="sha256"):
        _photo(sha256="not-a-digest")
    with pytest.raises(ValueError, match="image media type"):
        _photo(mime_type="application/pdf")


def test_field_graph_and_rule_refs_validate() -> None:
    data = FieldInspectionData(
        inspection_id="inspection-1",
        units=(FieldUnit("unit-1203", "inspection-1", "1203", UnitKind.APARTMENT),),
        rooms=(FieldRoom("room-bath", "unit-1203", "Badrum"),),
        findings=(
            FieldFinding(
                finding_id="finding-1",
                inspection_id="inspection-1",
                unit_id="unit-1203",
                room_id="room-bath",
                defect_type="contaminated_extract_terminal",
                description="Synligt dammbelagt frånluftsdon.",
                severity=FindingSeverity.MINOR,
                rule_refs=("PBF:5:1-7", "OVKAR:PBF-5:2-1"),
            ),
        ),
        photos=(_photo(),),
    )

    validate_field_data(data)


def test_photo_number_must_match_unit_number() -> None:
    data = FieldInspectionData(
        inspection_id="inspection-1",
        units=(FieldUnit("unit-1203", "inspection-1", "1203"),),
        photos=(_photo(unit_number="1303", room_id=None, finding_id=None),),
    )
    with pytest.raises(ValueError, match="unit_number does not match"):
        validate_field_data(data)


def test_unknown_defect_and_rule_reference_are_rejected() -> None:
    with pytest.raises(KeyError):
        defect_type_by_id("invented_defect")

    data = FieldInspectionData(
        inspection_id="inspection-1",
        units=(FieldUnit("unit-1203", "inspection-1", "1203"),),
        findings=(
            FieldFinding(
                finding_id="finding-1",
                inspection_id="inspection-1",
                unit_id="unit-1203",
                defect_type="other_observation",
                description="Observation",
                rule_refs=("FAKE:RULE",),
            ),
        ),
    )
    with pytest.raises(KeyError):
        validate_field_data(data)


def test_field_finding_projects_to_existing_ovk_finding() -> None:
    field_finding = FieldFinding(
        finding_id="finding-1",
        inspection_id="inspection-1",
        unit_id="unit-1203",
        defect_type="blocked_terminal",
        description="Frånluftsdon blockerat.",
        severity=FindingSeverity.MAJOR,
    )

    finding = field_finding.to_ovk_finding(photo_evidence_ref="photo:photo-1")
    assert finding.finding_id == "finding-1"
    assert finding.action_required is True
    assert finding.evidence_ref == "photo:photo-1"
