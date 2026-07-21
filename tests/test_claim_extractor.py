from crow_claim_extraction import ClaimCandidateType, extract_claim_candidates
from crow_observation_engine import (
    Observation,
    ObservationCollection,
    ObservationEvidence,
    ObservationSource,
    ObservationType,
    SourceLocator,
)


def observation(
    value: str,
    observation_type: ObservationType,
    start: int = 0,
    end: int | None = None,
) -> Observation:
    final_end = len(value) if end is None else end
    locator = SourceLocator(
        document_id="doc:1",
        page_id="page:1",
        page_number=1,
        region_id="region:1",
        character_start=start,
        character_end=final_end,
    )
    return Observation(
        id=f"obs:{observation_type.value}:{start}:{value}",
        observation_type=observation_type,
        value=value,
        normalized_value=value,
        content_sha256=f"hash:{observation_type.value}:{value}",
        evidence=ObservationEvidence(
            source=ObservationSource.EMBEDDED_PDF_TEXT,
            source_text=value,
            confidence=0.95,
            locator=locator,
            page_sha256="pagehash",
        ),
    )


def test_extracts_key_value_claim_with_unit() -> None:
    collection = ObservationCollection(
        project_id="project",
        observations=(observation("Luftflöde: 320 l/s", ObservationType.TEXT),),
    )

    result = extract_claim_candidates(collection)

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.candidate_type == ClaimCandidateType.KEY_VALUE
    assert candidate.subject == "Luftflöde"
    assert candidate.normalized_value == "320"
    assert candidate.unit == "L/S"


def test_extracts_unqualified_quantity() -> None:
    collection = ObservationCollection(
        project_id="project",
        observations=(observation("Kanal Ø160 mm", ObservationType.TEXT),),
    )

    result = extract_claim_candidates(collection)

    assert any(
        item.candidate_type == ClaimCandidateType.QUANTITY
        and item.normalized_value == "160"
        and item.unit == "MM"
        for item in result.candidates
    )


def test_extracts_reference_candidate() -> None:
    collection = ObservationCollection(
        project_id="project",
        observations=(
            observation("Se V-57.1-100", ObservationType.TEXT),
            observation("V-57.1-100", ObservationType.REFERENCE, 3, 13),
        ),
    )

    result = extract_claim_candidates(collection)

    assert any(
        item.candidate_type == ClaimCandidateType.REFERENCE and item.value == "V-57.1-100"
        for item in result.candidates
    )


def test_candidate_id_is_stable() -> None:
    collection = ObservationCollection(
        project_id="project",
        observations=(observation("Tryck: 200 Pa", ObservationType.TEXT),),
    )

    first = extract_claim_candidates(collection)
    second = extract_claim_candidates(collection)

    assert first == second
