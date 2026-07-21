from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_authority import load_resolution
from crow_knowledge_fusion import load_fusion_result

from .canonicalize import canonicalize_claims
from .models import (
    AcceptanceBasis,
    AcceptedClaim,
    AcceptedClaimProvenance,
    AcceptedClaimSet,
    PendingClaim,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_accepted_claims(claims: AcceptedClaimSet, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(claims), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_accepted_claims(path: Path) -> AcceptedClaimSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    claims = tuple(
        AcceptedClaim(
            id=item["id"],
            semantic_key=item["semantic_key"],
            subject=item["subject"],
            predicate=item["predicate"],
            value=item["value"],
            unit=item.get("unit"),
            confidence=float(item["confidence"]),
            acceptance_basis=AcceptanceBasis(item["acceptance_basis"]),
            provenance=AcceptedClaimProvenance(
                cluster_id=item["provenance"]["cluster_id"],
                authority_decision_id=item["provenance"]["authority_decision_id"],
                candidate_ids=tuple(item["provenance"]["candidate_ids"]),
                document_ids=tuple(item["provenance"]["document_ids"]),
                framework_id=item["provenance"]["framework_id"],
                applied_rule=item["provenance"]["applied_rule"],
                trace=tuple(item["provenance"]["trace"]),
            ),
            fingerprint=item["fingerprint"],
        )
        for item in raw.get("claims", [])
    )
    pending = tuple(
        PendingClaim(
            cluster_id=item["cluster_id"],
            authority_decision_id=item["authority_decision_id"],
            reason=item["reason"],
            status=item["status"],
        )
        for item in raw.get("pending", [])
    )
    return AcceptedClaimSet(project_id=raw["project_id"], claims=claims, pending=pending)


class AcceptedClaimsSummary(TypedDict):
    project_id: str
    accepted: int
    pending: int
    by_basis: dict[str, int]
    average_confidence: float


def summarize_accepted_claims(claims: AcceptedClaimSet) -> AcceptedClaimsSummary:
    by_basis: dict[str, int] = {}
    for claim in claims.claims:
        key = claim.acceptance_basis.value
        by_basis[key] = by_basis.get(key, 0) + 1
    average = (
        round(sum(item.confidence for item in claims.claims) / len(claims.claims), 6)
        if claims.claims
        else 0.0
    )
    return {
        "project_id": claims.project_id,
        "accepted": claims.accepted_count,
        "pending": claims.pending_count,
        "by_basis": dict(sorted(by_basis.items())),
        "average_confidence": average,
    }


def build_project_accepted_claims(
    project_file: Path,
    fusion_file: Path | None = None,
    resolution_file: Path | None = None,
) -> tuple[AcceptedClaimSet, Path]:
    fusion_path = fusion_file or project_file.with_name("crow-knowledge-fusion.json")
    resolution_path = resolution_file or project_file.with_name("crow-authority-resolution.json")
    fusion = load_fusion_result(fusion_path)
    resolution = load_resolution(resolution_path)
    claims = canonicalize_claims(fusion, resolution)
    output = project_file.with_name("crow-accepted-claims.json")
    save_accepted_claims(claims, output)
    return claims, output
