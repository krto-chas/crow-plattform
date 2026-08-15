from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_accepted_claims import load_accepted_claims

from .models import (
    RequiredClaim,
    TechnicalValidationIssue,
    TechnicalValidationResult,
    ValidationIssueType,
    ValidationProfile,
    ValidationRequirement,
    ValidationSeverity,
)
from .validator import validate_claims


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def load_profile(path: Path) -> ValidationProfile:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    requirements = tuple(
        ValidationRequirement(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            severity=ValidationSeverity(item["severity"]),
            required_claims=tuple(
                RequiredClaim(
                    alias=required["alias"],
                    subject=required.get("subject"),
                    subject_regex=required.get("subject_regex"),
                    predicate=required.get("predicate"),
                    unit=required.get("unit"),
                    semantic_key_contains=required.get("semantic_key_contains"),
                    minimum_confidence=float(required.get("minimum_confidence", 0.0)),
                    numeric=bool(required.get("numeric", False)),
                    allowed_values=tuple(required.get("allowed_values", [])),
                )
                for required in item.get("required_claims", [])
            ),
            source=item.get("source", "unspecified"),
            enabled=bool(item.get("enabled", True)),
            version=item.get("version", "1.0.0"),
        )
        for item in raw.get("requirements", [])
    )
    return ValidationProfile(
        id=raw["id"],
        name=raw["name"],
        version=raw.get("version", "1.0.0"),
        requirements=requirements,
    )


def write_profile_template(path: Path) -> None:
    payload = {
        "id": "crow.validation.ventilation.example",
        "name": "Ventilation completeness profile",
        "version": "1.0.0",
        "requirements": [
            {
                "id": "ventilation.duct-sizing-inputs",
                "name": "Duct sizing inputs must be complete",
                "description": "Airflow and duct area are required.",
                "severity": "blocking",
                "source": "Project validation rule",
                "required_claims": [
                    {
                        "alias": "airflow",
                        "subject_regex": "airflow|luftflöde",
                        "unit": "L/S",
                        "minimum_confidence": 0.7,
                        "numeric": True,
                    },
                    {
                        "alias": "area",
                        "subject_regex": "duct area|kanalarea",
                        "unit": "M2",
                        "minimum_confidence": 0.7,
                        "numeric": True,
                    },
                ],
            },
            {
                "id": "ventilation.fire-class",
                "name": "Fire classification must be specified",
                "description": "A fire classification is required.",
                "severity": "error",
                "source": "Project validation rule",
                "required_claims": [
                    {
                        "alias": "fire_class",
                        "subject_regex": "fire class|brandklass",
                        "minimum_confidence": 0.7,
                    }
                ],
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_result(result: TechnicalValidationResult, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(result), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_result(path: Path) -> TechnicalValidationResult:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return TechnicalValidationResult(
        project_id=raw["project_id"],
        profile_id=raw["profile_id"],
        checked_requirements=int(raw["checked_requirements"]),
        issues=tuple(
            TechnicalValidationIssue(
                id=item["id"],
                requirement_id=item["requirement_id"],
                issue_type=ValidationIssueType(item["issue_type"]),
                severity=ValidationSeverity(item["severity"]),
                title=item["title"],
                explanation=item["explanation"],
                missing_aliases=tuple(item["missing_aliases"]),
                related_claim_ids=tuple(item["related_claim_ids"]),
                document_ids=tuple(item["document_ids"]),
                recommended_action=item["recommended_action"],
                fingerprint=item["fingerprint"],
            )
            for item in raw.get("issues", [])
        ),
    )


class ValidationSummary(TypedDict):
    project_id: str
    profile_id: str
    checked_requirements: int
    issues: int
    blocking: int
    by_type: dict[str, int]
    by_severity: dict[str, int]


def summarize_validation(result: TechnicalValidationResult) -> ValidationSummary:
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for issue in result.issues:
        by_type[issue.issue_type.value] = by_type.get(issue.issue_type.value, 0) + 1
        by_severity[issue.severity.value] = by_severity.get(issue.severity.value, 0) + 1
    return {
        "project_id": result.project_id,
        "profile_id": result.profile_id,
        "checked_requirements": result.checked_requirements,
        "issues": len(result.issues),
        "blocking": result.blocking_count,
        "by_type": dict(sorted(by_type.items())),
        "by_severity": dict(sorted(by_severity.items())),
    }


def validate_project(
    project_file: Path,
    profile_file: Path,
    accepted_claims_file: Path | None = None,
) -> tuple[TechnicalValidationResult, Path]:
    claims_path = accepted_claims_file or project_file.with_name("crow-accepted-claims.json")
    claims = load_accepted_claims(claims_path)
    profile = load_profile(profile_file)
    result = validate_claims(claims, profile)
    output = project_file.with_name("crow-technical-validation.json")
    save_result(result, output)
    return result, output
