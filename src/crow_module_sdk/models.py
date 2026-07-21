from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Provenance:
    document_id: str
    revision: str | None = None
    page: int | None = None
    location: str | None = None

    def is_complete(self) -> bool:
        return bool(self.document_id.strip())


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    namespace: str
    subject: str
    property: str
    value: Any
    unit: str | None
    provenance: Provenance
    confidence: Decimal = Decimal("1.0")

    # NOTE: the dataclass field ``property`` shadows the ``property`` builtin
    # inside this class body, so the decorator must be qualified explicitly.
    @builtins.property
    def conflict_key(self) -> tuple[str, str, str]:
        return (self.namespace, self.subject, self.property)


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    kind: str
    statement: str
    source_claim_ids: tuple[str, ...] = ()
    rule_id: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimSchema:
    namespace: str
    property: str
    value_type: str
    unit_required: bool = False


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    module_id: str
    name: str
    version: str
    domain: str
    backbone_api: str
    domain_model: str


@dataclass(frozen=True, slots=True)
class ModuleCapabilities:
    claim_types: tuple[str, ...]
    rule_providers: tuple[str, ...] = ()
    technical_delta: bool = False
    commercial_impact: bool = False
    pricing_adapter: bool = False
    exports: tuple[str, ...] = ()
    human_review_supported: bool = True


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleHealth:
    status: HealthStatus
    checks: dict[str, bool] = field(default_factory=dict)
    message: str = ""
