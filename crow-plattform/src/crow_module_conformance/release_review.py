from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ReviewStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class ReviewCheck:
    id: str
    description: str
    status: ReviewStatus
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ArchitectureReview:
    release: str
    checks: tuple[ReviewCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.status == ReviewStatus.PASS for check in self.checks)


REQUIRED_DOCUMENTS = (
    "docs/CONSTITUTION.md",
    "docs/PHILOSOPHY.md",
    "docs/DOMAIN_HANDBOOK.md",
    "docs/MODULE_CONTRACT.md",
    "docs/PROJECT_MODEL.md",
    "docs/PROJECT_TRANSACTIONS.md",
    "docs/AUDIT_AND_REVISION.md",
    "docs/TRUST_POLICY.md",
    "docs/MIGRATION_POLICY.md",
)


def review_repository(root: Path, *, release: str) -> ArchitectureReview:
    checks: list[ReviewCheck] = []

    missing = tuple(path for path in REQUIRED_DOCUMENTS if not (root / path).exists())
    checks.append(
        ReviewCheck(
            "ARC-001",
            "Required architecture documents exist",
            ReviewStatus.FAIL if missing else ReviewStatus.PASS,
            ", ".join(missing),
        )
    )

    adr_dir = root / "docs" / "adr"
    adr_files = tuple(sorted(adr_dir.glob("ADR-*.md"))) if adr_dir.exists() else ()
    checks.append(
        ReviewCheck(
            "ARC-002",
            "Foundational decisions are recorded as ADRs",
            ReviewStatus.PASS if len(adr_files) >= 5 else ReviewStatus.FAIL,
            f"{len(adr_files)} ADR files found",
        )
    )

    workflow = root / ".github" / "workflows" / "ci.yml"
    checks.append(
        ReviewCheck(
            "ARC-003",
            "CI workflow exists",
            ReviewStatus.PASS if workflow.exists() else ReviewStatus.FAIL,
        )
    )

    changelog = root / "CHANGELOG.md"
    has_release = changelog.exists() and release in changelog.read_text(encoding="utf-8")
    checks.append(
        ReviewCheck(
            "ARC-004",
            "Release is documented in changelog",
            ReviewStatus.PASS if has_release else ReviewStatus.FAIL,
        )
    )

    return ArchitectureReview(release=release, checks=tuple(checks))
