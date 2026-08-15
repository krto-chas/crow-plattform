from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class AuditEventType(StrEnum):
    PROJECT_CREATED = "project_created"
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_REVISED = "document_revised"
    CLAIMS_ADDED = "claims_added"
    AUTHORITY_POLICY_SET = "authority_policy_set"
    MODULE_ENABLED = "module_enabled"
    PROJECT_READY = "project_ready"
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    SOURCES_INVALIDATED = "sources_invalidated"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    project_id: str
    event_type: AuditEventType
    occurred_at: datetime
    actor: str
    details: Mapping[str, str]

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        project_id: str,
        event_type: AuditEventType,
        actor: str = "system",
        details: Mapping[str, str] | None = None,
    ) -> AuditEvent:
        return cls(
            id=event_id,
            project_id=project_id,
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            actor=actor,
            details=dict(details or {}),
        )
