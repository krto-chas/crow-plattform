from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_document_intelligence import load_index

from .discovery import discover_authority
from .models import AuthorityDiscoveryResult


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def save_discovery(result: AuthorityDiscoveryResult, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(result), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_discovered_manifest(result: AuthorityDiscoveryResult, path: Path) -> None:
    payload = {
        "framework_id": result.framework.id,
        "framework_name": result.framework.name,
        "source": result.framework.source,
        "hierarchy": [item.value for item in result.framework.hierarchy],
        "documents": [
            {
                "document_id": item.document_id,
                "authority_type": item.authority_type.value,
                "title": item.title,
                "issue_date": item.issue_date.isoformat() if item.issue_date else None,
                "revision": item.revision,
            }
            for item in result.documents
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class DiscoverySummary(TypedDict):
    project_id: str
    contract_framework: str
    framework_id: str
    project_override: bool
    documents: int
    findings: int
    requires_review: bool


def summarize_discovery(result: AuthorityDiscoveryResult) -> DiscoverySummary:
    return {
        "project_id": result.project_id,
        "contract_framework": result.contract_framework.value,
        "framework_id": result.framework.id,
        "project_override": result.framework.project_override,
        "documents": len(result.documents),
        "findings": len(result.findings),
        "requires_review": result.requires_review,
    }


def discover_project(project_file: Path) -> tuple[AuthorityDiscoveryResult, Path, Path]:
    result = discover_authority(load_index(project_file))
    report = project_file.with_name("crow-authority-discovery.json")
    manifest = project_file.with_name("crow-authority-manifest.discovered.json")
    save_discovery(result, report)
    save_discovered_manifest(result, manifest)
    return result, report, manifest
