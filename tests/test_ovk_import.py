from crow_observation_engine.models import Observation, ObservationCollection, ObservationEvidence, ObservationSource, ObservationType, SourceLocator
from crow_ovk import EvidenceOrigin, FindingSeverity
from crow_ovk_import import import_observations


def make_observation(identifier: str, text: str) -> Observation:
    return Observation(id=identifier, observation_type=ObservationType.TEXT, value=text, normalized_value=text, content_sha256=f"sha-{identifier}", evidence=ObservationEvidence(source=ObservationSource.EMBEDDED_PDF_TEXT, source_text=text, confidence=1.0, locator=SourceLocator(document_id="doc-1", page_id="page-1", page_number=1, region_id=identifier, character_start=0, character_end=len(text)), page_sha256="page-sha"))


def test_imports_explicit_measurement() -> None:
    result = import_observations(ObservationCollection(project_id="p1", observations=(make_observation("o1", "System FTX01, B1 uppmätt 34,5 l/s, projekterat 40 l/s"),)))
    assert [item.system_id for item in result.systems] == ["FTX01"]
    measurement = result.measurements[0]
    assert str(measurement.measured_value) == "34.5"
    assert str(measurement.designed_value) == "40"
    assert measurement.system_id == "FTX01"
    assert measurement.point_id == "B1"
    assert measurement.origin is EvidenceOrigin.STATED


def test_does_not_guess_unlabelled_values() -> None:
    result = import_observations(ObservationCollection(project_id="p1", observations=(make_observation("o2", "B1 FTX01 34 l/s 40 l/s"),)))
    assert [item.system_id for item in result.systems] == ["FTX01"]
    assert result.measurements == ()


def test_imports_explicit_finding_conservatively() -> None:
    result = import_observations(ObservationCollection(project_id="p1", observations=(make_observation("o3", "Anmärkning: Filter i FTX02 är smutsigt"),)))
    finding = result.findings[0]
    assert finding.severity is FindingSeverity.INFO
    assert finding.action_required is False
    assert finding.system_id == "FTX02"
    assert finding.origin is EvidenceOrigin.STATED


def test_unrelated_observation_is_kept_for_review() -> None:
    result = import_observations(ObservationCollection(project_id="p1", observations=(make_observation("o4", "Besiktning utförd 2025-04-02"),)))
    assert len(result.unmapped) == 1
    assert result.unmapped[0].reason == "no_explicit_ovk_pattern"
