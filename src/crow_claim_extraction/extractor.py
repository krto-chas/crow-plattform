from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass

from crow_observation_engine import Observation, ObservationCollection, ObservationType

from .models import (
    ClaimCandidate,
    ClaimCandidateCollection,
    ClaimCandidateStatus,
    ClaimCandidateType,
    ClaimProvenance,
)

_KEY_VALUE = re.compile(
    r"(?P<subject>[A-Za-zÅÄÖåäö][A-Za-zÅÄÖåäö0-9 /()._-]{1,80}?)"
    r"\s*(?P<separator>:|=)\s*"
    r"(?P<value>[-+]?\d+(?:[.,]\d+)?)"
    r"(?:\s*(?P<unit>mm|cm|m|m²|m3|m³|l/s|m3/s|m³/s|Pa|kPa|W|kW|°C|%))?",
    re.I,
)
_QUANTITY = re.compile(
    r"(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>mm|cm|m|m²|m3|m³|l/s|m3/s|m³/s|Pa|kPa|W|kW|°C|%)",
    re.I,
)


@dataclass(frozen=True, slots=True)
class RegionContext:
    document_id: str
    page_number: int
    region_id: str
    observations: tuple[Observation, ...]


def _normalize(value: str) -> str:
    return " ".join(value.strip().split()).replace(",", ".")


def _fingerprint(
    candidate_type: ClaimCandidateType,
    subject: str,
    predicate: str,
    value: str,
    unit: str | None,
) -> str:
    material = "|".join(
        [
            candidate_type.value,
            subject.casefold(),
            predicate.casefold(),
            _normalize(value).casefold(),
            (unit or "").casefold(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _candidate_id(fingerprint: str, provenance: ClaimProvenance) -> str:
    material = "|".join(
        [
            fingerprint,
            provenance.document_id,
            str(provenance.page_number),
            provenance.region_id,
            ",".join(provenance.observation_ids),
        ]
    )
    return "claim-candidate:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _provenance(observations: tuple[Observation, ...]) -> ClaimProvenance:
    first = observations[0]
    locator = first.evidence.locator
    return ClaimProvenance(
        observation_ids=tuple(observation.id for observation in observations),
        document_id=locator.document_id,
        page_number=locator.page_number,
        region_id=locator.region_id,
        locator_values=tuple(observation.evidence.locator.value for observation in observations),
    )


def group_by_region(collection: ObservationCollection) -> tuple[RegionContext, ...]:
    groups: dict[tuple[str, int, str], list[Observation]] = defaultdict(list)
    for observation in collection.observations:
        locator = observation.evidence.locator
        groups[(locator.document_id, locator.page_number, locator.region_id)].append(observation)

    contexts: list[RegionContext] = []
    for (document_id, page_number, region_id), observations in groups.items():
        contexts.append(
            RegionContext(
                document_id=document_id,
                page_number=page_number,
                region_id=region_id,
                observations=tuple(
                    sorted(
                        observations,
                        key=lambda item: (
                            item.evidence.locator.character_start,
                            item.evidence.locator.character_end,
                            item.id,
                        ),
                    )
                ),
            )
        )
    return tuple(
        sorted(
            contexts,
            key=lambda item: (item.document_id, item.page_number, item.region_id),
        )
    )


def _text_observation(context: RegionContext) -> Observation | None:
    return next(
        (
            observation
            for observation in context.observations
            if observation.observation_type == ObservationType.TEXT
        ),
        None,
    )


def _build_candidate(
    context: RegionContext,
    candidate_type: ClaimCandidateType,
    subject: str,
    predicate: str,
    value: str,
    unit: str | None,
    confidence: float,
    source_observations: tuple[Observation, ...] | None = None,
) -> ClaimCandidate:
    evidence = source_observations or context.observations
    provenance = _provenance(evidence)
    normalized_value = _normalize(value)
    fingerprint = _fingerprint(
        candidate_type,
        subject,
        predicate,
        normalized_value,
        unit,
    )
    return ClaimCandidate(
        id=_candidate_id(fingerprint, provenance),
        candidate_type=candidate_type,
        subject=subject.strip(),
        predicate=predicate,
        value=value.strip(),
        normalized_value=normalized_value,
        unit=unit.upper() if unit else None,
        confidence=confidence,
        status=ClaimCandidateStatus.PROPOSED,
        provenance=provenance,
        fingerprint=fingerprint,
    )


def extract_claim_candidates(
    observations: ObservationCollection,
) -> ClaimCandidateCollection:
    candidates: list[ClaimCandidate] = []

    for context in group_by_region(observations):
        text_observation = _text_observation(context)
        if text_observation is None:
            continue
        text = text_observation.value

        occupied: list[tuple[int, int]] = []
        for match in _KEY_VALUE.finditer(text):
            occupied.append((match.start(), match.end()))
            candidates.append(
                _build_candidate(
                    context=context,
                    candidate_type=ClaimCandidateType.KEY_VALUE,
                    subject=match.group("subject"),
                    predicate="has_value",
                    value=match.group("value"),
                    unit=match.group("unit"),
                    confidence=0.88 if match.group("unit") else 0.80,
                    source_observations=(text_observation,),
                )
            )

        for match in _QUANTITY.finditer(text):
            if any(start <= match.start() and match.end() <= end for start, end in occupied):
                continue
            candidates.append(
                _build_candidate(
                    context=context,
                    candidate_type=ClaimCandidateType.QUANTITY,
                    subject="unspecified",
                    predicate="has_quantity",
                    value=match.group("value"),
                    unit=match.group("unit"),
                    confidence=0.62,
                    source_observations=(text_observation,),
                )
            )

        references = [
            observation
            for observation in context.observations
            if observation.observation_type == ObservationType.REFERENCE
        ]
        for reference in references:
            candidates.append(
                _build_candidate(
                    context=context,
                    candidate_type=ClaimCandidateType.REFERENCE,
                    subject="document_region",
                    predicate="references",
                    value=reference.value,
                    unit=None,
                    confidence=reference.evidence.confidence,
                    source_observations=(reference,),
                )
            )

    unique_by_id = {candidate.id: candidate for candidate in candidates}
    return ClaimCandidateCollection(
        project_id=observations.project_id,
        candidates=tuple(unique_by_id.values()),
    )
