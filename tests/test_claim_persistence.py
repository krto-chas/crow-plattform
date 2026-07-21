from pathlib import Path

from crow_claim_extraction import (
    ClaimCandidateCollection,
    extract_claim_candidates,
    load_claim_candidates,
    save_claim_candidates,
)
from crow_observation_engine import (
    Observation,
    ObservationCollection,
    ObservationEvidence,
    ObservationSource,
    ObservationType,
    SourceLocator,
)


def make_collection() -> ObservationCollection:
    locator = SourceLocator(
        document_id="doc:1",
        page_id="page:1",
        page_number=1,
        region_id="region:1",
        character_start=0,
        character_end=17,
    )
    observation = Observation(
        id="obs:1",
        observation_type=ObservationType.TEXT,
        value="Temperatur: 20 °C",
        normalized_value="Temperatur: 20 °C",
        content_sha256="hash",
        evidence=ObservationEvidence(
            source=ObservationSource.EMBEDDED_PDF_TEXT,
            source_text="Temperatur: 20 °C",
            confidence=1.0,
            locator=locator,
            page_sha256="pagehash",
        ),
    )
    return ObservationCollection(project_id="project", observations=(observation,))


def test_claim_candidates_round_trip(tmp_path: Path) -> None:
    original = extract_claim_candidates(make_collection())
    path = tmp_path / "claims.json"

    save_claim_candidates(original, path)
    loaded = load_claim_candidates(path)

    assert loaded == original


def test_duplicate_semantics_are_content_based() -> None:
    original = extract_claim_candidates(make_collection())
    candidate = original.candidates[0]
    duplicated = ClaimCandidateCollection(
        project_id="project",
        candidates=(candidate, candidate),
    )

    assert duplicated.unique_count == 1
    assert duplicated.duplicate_count == 1
