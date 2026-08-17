from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import crow_ovk
import crow_ovk_field
import crow_ovk_import
import crow_ovk_pricing
import crow_ovk_workflow
from crow_observation_engine.models import (
    Observation,
    ObservationCollection,
    ObservationEvidence,
    ObservationSource,
    ObservationType,
    SourceLocator,
)
from crow_ovk import CheckStatus, OvkCheckpoint, OvkMeasurement, OvkObject, build_inspection
from crow_ovk_field import FieldInspectionData, FieldUnit, defect_type_by_id, validate_field_data
from crow_ovk_import import import_observations
from crow_ovk_pricing import (
    BuildingCategory,
    InspectionType,
    OvkObjectPart,
    OvkQuoteRequest,
    build_quote,
    load_taxa,
)
from crow_ovk_workflow import (
    AggregatCoverage,
    AggregatStatus,
    BekraftelseRoll,
    InspectionCoverage,
    SystemForteckningBekraftelse,
    build_record,
    record_to_payload,
)


def _module_path(package_file: str | None) -> str:
    assert package_file is not None
    return Path(package_file).resolve().as_posix()


def test_ovk_packages_are_owned_by_first_party_module() -> None:
    for package_name, package_file in (
        ("crow_ovk", crow_ovk.__file__),
        ("crow_ovk_field", crow_ovk_field.__file__),
        ("crow_ovk_workflow", crow_ovk_workflow.__file__),
        ("crow_ovk_import", crow_ovk_import.__file__),
        ("crow_ovk_pricing", crow_ovk_pricing.__file__),
    ):
        normalized = _module_path(package_file)
        expected = f"/modules/crow-ovk-module/src/{package_name}/"
        assert expected in normalized
        assert f"/src/{package_name}/" not in normalized.replace(expected, "")


def test_relocated_ovk_core_preserves_public_behavior() -> None:
    inspection = build_inspection(
        inspection_id="inspection-1",
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="project-1",
            building_id="building-1",
            name="Testobjekt",
        ),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="checkpoint-1",
                label="Kontrollpunkt",
                status=CheckStatus.PASS,
            ),
        ),
        measurements=(
            OvkMeasurement(
                measurement_id="measurement-1",
                metric="airflow",
                measured_value=Decimal("95"),
                designed_value=Decimal("100"),
                unit="l/s",
            ),
        ),
    )
    assert inspection.conclusion.value == "approved"
    assert inspection.measurements[0].deviation_percent == Decimal("-5.00")


def test_relocated_field_package_keeps_lexicon_and_validation() -> None:
    assert defect_type_by_id("blocked_terminal").label == "Blockerat don"
    validate_field_data(
        FieldInspectionData(
            inspection_id="inspection-1",
            units=(FieldUnit("unit-1", "inspection-1", "1203"),),
        )
    )


def test_relocated_workflow_preserves_serialization() -> None:
    record = build_record(
        inspection_id="inspection-1",
        ovk_object=OvkObject("object-1", "project-1", "building-1", "Testobjekt"),
        checkpoints=(OvkCheckpoint("checkpoint-1", "Kontrollpunkt", CheckStatus.PASS),),
        coverage=InspectionCoverage(
            inspection_id="bevakning-fixture",
            aggregat=(
                AggregatCoverage(
                    aggregat_id="agg-1", label="LB01", status=AggregatStatus.BESIKTIGAD
                ),
            ),
            system_list_confirmation=SystemForteckningBekraftelse(
                confirmed_by="Test Besiktningsman", role=BekraftelseRoll.BESIKTNINGSMAN
            ),
        ),
    )
    payload = record_to_payload(record)
    assert payload["inspection"]["inspection_id"] == "inspection-1"
    assert payload["protocol_ready"] is True


def test_relocated_import_preserves_evidence_mapping() -> None:
    text = "System FTX01, B1 uppmätt 34,5 l/s, projekterat 40 l/s"
    observation = Observation(
        id="o1",
        observation_type=ObservationType.TEXT,
        value=text,
        normalized_value=text,
        content_sha256="sha-o1",
        evidence=ObservationEvidence(
            source=ObservationSource.EMBEDDED_PDF_TEXT,
            source_text=text,
            confidence=1.0,
            locator=SourceLocator(
                document_id="doc-1",
                page_id="page-1",
                page_number=1,
                region_id="o1",
                character_start=0,
                character_end=len(text),
            ),
            page_sha256="page-sha",
        ),
    )
    result = import_observations(
        ObservationCollection(project_id="p1", observations=(observation,))
    )
    assert result.measurements[0].system_id == "FTX01"
    assert result.measurements[0].measured_value == Decimal("34.5")


def test_relocated_pricing_keeps_packaged_taxa_and_quote_behavior() -> None:
    quote = build_quote(
        OvkQuoteRequest(
            inspection_type=InspectionType.ATERKOMMANDE,
            parts=(
                OvkObjectPart(
                    category=BuildingCategory.FLERBOSTADSHUS,
                    apartment_count=10,
                ),
            ),
        ),
        load_taxa(),
    )
    assert quote.currency == "SEK"
    assert quote.total > Decimal("0")
