from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from crow_module_sdk import CrowModulePlugin

from .import_guard import scan_forbidden_imports
from .versioning import Version, satisfies

_MODULE_ID = re.compile(r"^crow\.[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ConformanceIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    passed: bool
    issues: tuple[ConformanceIssue, ...]


def validate_plugin(
    plugin: CrowModulePlugin,
    *,
    module_source_root: Path | None = None,
    backbone_version: str = "1.0.0",
    domain_model_version: str = "1.0.0",
) -> ConformanceReport:
    issues: list[ConformanceIssue] = []
    manifest = plugin.manifest()
    capabilities = plugin.capabilities()
    schemas = plugin.claim_schemas()
    health = plugin.healthcheck()

    if not _MODULE_ID.fullmatch(manifest.module_id):
        issues.append(ConformanceIssue("CMC-001", "Invalid module id"))

    try:
        Version.parse(manifest.version)
    except ValueError as error:
        issues.append(ConformanceIssue("CMC-002", str(error)))

    try:
        if not satisfies(backbone_version, manifest.backbone_api):
            issues.append(
                ConformanceIssue(
                    "CMC-003",
                    f"Backbone {backbone_version} is outside {manifest.backbone_api}",
                )
            )
    except ValueError as error:
        issues.append(ConformanceIssue("CMC-003", str(error)))

    try:
        domain_expression = (
            manifest.domain_model
            if any(symbol in manifest.domain_model for symbol in "<>=")
            else f"=={manifest.domain_model}"
        )
        if not satisfies(domain_model_version, domain_expression):
            issues.append(
                ConformanceIssue(
                    "CMC-004",
                    f"Domain model {domain_model_version} is outside {domain_expression}",
                )
            )
    except ValueError as error:
        issues.append(ConformanceIssue("CMC-004", str(error)))

    if not schemas:
        issues.append(ConformanceIssue("CMC-005", "At least one Claim schema is required"))
    if not capabilities.human_review_supported:
        issues.append(ConformanceIssue("CMC-006", "Human Review support is required"))
    if health.status.value != "ok":
        issues.append(ConformanceIssue("CMC-007", "Module healthcheck did not pass"))
    if manifest != plugin.manifest() or capabilities != plugin.capabilities():
        issues.append(ConformanceIssue("CMC-008", "Plugin metadata must be deterministic"))

    if module_source_root is not None:
        for violation in scan_forbidden_imports(module_source_root):
            issues.append(
                ConformanceIssue(
                    "CMC-009",
                    f"Forbidden import {violation.module} in {violation.path}:{violation.line}",
                )
            )

    return ConformanceReport(passed=not issues, issues=tuple(issues))
