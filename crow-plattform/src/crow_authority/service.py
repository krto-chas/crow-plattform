from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_knowledge_fusion import fuse_project, load_fusion_result

from .frameworks import ab04_framework, project_framework
from .models import (
    AuthorityDecision,
    AuthorityDecisionStatus,
    AuthorityFramework,
    AuthorityResolution,
    DocumentAuthorityMetadata,
    DocumentAuthorityType,
    EvaluatedVariant,
)
from .resolver import resolve_authority


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def save_resolution(resolution: AuthorityResolution, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(resolution), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_authority_manifest(
    path: Path,
) -> tuple[AuthorityFramework, tuple[DocumentAuthorityMetadata, ...]]:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    hierarchy_raw = raw.get("hierarchy")
    if hierarchy_raw:
        framework = project_framework(
            tuple(DocumentAuthorityType(item) for item in hierarchy_raw),
            source=str(raw.get("source", "Project authority manifest")),
            framework_id=str(raw.get("framework_id", "project.override")),
            name=str(raw.get("framework_name", "Project-specific authority framework")),
        )
    else:
        framework = ab04_framework()

    documents = tuple(
        DocumentAuthorityMetadata(
            document_id=item["document_id"],
            authority_type=DocumentAuthorityType(item["authority_type"]),
            title=str(item.get("title", "")),
            issue_date=date.fromisoformat(item["issue_date"]) if item.get("issue_date") else None,
            revision=str(item["revision"]) if item.get("revision") is not None else None,
        )
        for item in raw.get("documents", [])
    )
    return framework, documents


def write_manifest_template(path: Path) -> None:
    framework = ab04_framework()
    payload = {
        "framework_id": framework.id,
        "framework_name": framework.name,
        "source": framework.source,
        "hierarchy": [item.value for item in framework.hierarchy],
        "documents": [
            {
                "document_id": "replace-with-document-id",
                "authority_type": "technical_description",
                "title": "Teknisk beskrivning",
                "issue_date": "2026-01-15",
                "revision": "A",
            }
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class AuthoritySummary(TypedDict):
    project_id: str
    framework_id: str
    project_override: bool
    decisions: int
    resolved: int
    unresolved: int
    by_status: dict[str, int]


def summarize_resolution(resolution: AuthorityResolution) -> AuthoritySummary:
    by_status: dict[str, int] = {}
    for decision in resolution.decisions:
        key = decision.status.value
        by_status[key] = by_status.get(key, 0) + 1
    return {
        "project_id": resolution.project_id,
        "framework_id": resolution.framework.id,
        "project_override": resolution.framework.project_override,
        "decisions": len(resolution.decisions),
        "resolved": resolution.resolved_count,
        "unresolved": resolution.unresolved_count,
        "by_status": dict(sorted(by_status.items())),
    }


def resolve_project(
    project_file: Path,
    manifest_file: Path,
) -> tuple[AuthorityResolution, Path]:
    fusion_file = project_file.with_name("crow-knowledge-fusion.json")
    if fusion_file.exists():
        fusion = load_fusion_result(fusion_file)
    else:
        fusion, _ = fuse_project(project_file)

    framework, documents = load_authority_manifest(manifest_file)
    resolution = resolve_authority(fusion, framework, documents)
    output = project_file.with_name("crow-authority-resolution.json")
    save_resolution(resolution, output)
    return resolution, output


def load_resolution(path: Path) -> AuthorityResolution:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    framework_raw = raw["framework"]
    framework = AuthorityFramework(
        id=framework_raw["id"],
        name=framework_raw["name"],
        hierarchy=tuple(DocumentAuthorityType(item) for item in framework_raw["hierarchy"]),
        source=framework_raw["source"],
        project_override=bool(framework_raw["project_override"]),
    )
    decisions = tuple(
        AuthorityDecision(
            id=item["id"],
            cluster_id=item["cluster_id"],
            status=AuthorityDecisionStatus(item["status"]),
            accepted_value=item.get("accepted_value"),
            accepted_unit=item.get("accepted_unit"),
            accepted_candidate_ids=tuple(item["accepted_candidate_ids"]),
            accepted_document_ids=tuple(item["accepted_document_ids"]),
            evaluated_variants=tuple(
                EvaluatedVariant(
                    normalized_value=variant["normalized_value"],
                    unit=variant.get("unit"),
                    candidate_ids=tuple(variant["candidate_ids"]),
                    document_ids=tuple(variant["document_ids"]),
                    best_rank=variant.get("best_rank"),
                    latest_date=date.fromisoformat(variant["latest_date"])
                    if variant.get("latest_date")
                    else None,
                )
                for variant in item["evaluated_variants"]
            ),
            applied_rule=item["applied_rule"],
            explanation=item["explanation"],
            framework_id=item["framework_id"],
            trace=tuple(item["trace"]),
        )
        for item in raw.get("decisions", [])
    )
    return AuthorityResolution(
        project_id=raw["project_id"],
        framework=framework,
        decisions=decisions,
    )
