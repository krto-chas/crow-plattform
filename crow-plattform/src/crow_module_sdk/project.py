from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .audit import AuditEvent, AuditEventType
from .batch_pipeline import (
    BatchPipelineResult,
    PricingInput,
    run_batch_claim_to_estimate,
)
from .decision_graph import DecisionGraph
from .decision_models import AuthorityPolicy, RoundingPolicy
from .graph_builder import build_decision_graph
from .models import Claim
from .module_registry import ModuleRegistry


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DocumentRole(StrEnum):
    AF = "af"
    SPECIFICATION = "specification"
    DRAWING = "drawing"
    DRAWING_LEGEND = "drawing_legend"
    ROOM_DESCRIPTION = "room_description"
    MANUFACTURER_DOCUMENTATION = "manufacturer_documentation"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    id: str
    name: str
    role: DocumentRole
    revision: str | None = None
    checksum: str | None = None
    active: bool = True


@dataclass(frozen=True, slots=True)
class DocumentRevisionResult:
    project: CrowProject
    invalidated_claim_ids: tuple[str, ...]
    invalidated_run_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectModule:
    module_id: str
    version: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ProjectRun:
    id: str
    started_at: datetime
    completed_at: datetime
    result: BatchPipelineResult
    graph_ids: tuple[str, ...]
    status: ProjectStatus
    invalidated: bool = False


@dataclass(frozen=True, slots=True)
class CrowProject:
    id: str
    name: str
    status: ProjectStatus = ProjectStatus.DRAFT
    documents: tuple[ProjectDocument, ...] = ()
    claims: tuple[Claim, ...] = ()
    authority_policy: AuthorityPolicy | None = None
    modules: tuple[ProjectModule, ...] = ()
    runs: tuple[ProjectRun, ...] = ()
    invalidated_claim_ids: tuple[str, ...] = ()
    audit_events: tuple[AuditEvent, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(cls, project_id: str, name: str, *, actor: str = "system") -> CrowProject:
        project = cls(id=project_id, name=name)
        return project._with_event(
            AuditEventType.PROJECT_CREATED,
            actor=actor,
            details={"name": name},
        )

    def add_document(self, document: ProjectDocument, *, actor: str = "system") -> CrowProject:
        if any(existing.id == document.id for existing in self.documents):
            raise ValueError(f"Document already exists: {document.id}")
        updated = self._updated(documents=self.documents + (document,))
        return updated._with_event(
            AuditEventType.DOCUMENT_ADDED,
            actor=actor,
            details={"document_id": document.id, "revision": document.revision or ""},
        )

    def revise_document(
        self,
        document_id: str,
        *,
        revision: str | None,
        checksum: str | None,
        actor: str = "system",
    ) -> DocumentRevisionResult:
        existing = next((item for item in self.documents if item.id == document_id), None)
        if existing is None:
            raise KeyError(f"Unknown project document: {document_id}")
        if existing.revision == revision and existing.checksum == checksum:
            return DocumentRevisionResult(self, (), ())

        revised = replace(existing, revision=revision, checksum=checksum, active=True)
        documents = tuple(revised if item.id == document_id else item for item in self.documents)
        invalid_claim_ids = tuple(
            sorted(claim.id for claim in self.claims if claim.provenance.document_id == document_id)
        )
        invalid_claim_set = set(invalid_claim_ids)
        invalid_run_ids: list[str] = []
        runs: list[ProjectRun] = []
        for run in self.runs:
            depends_on_invalid_claim = any(
                claim_id in invalid_claim_set
                for item in run.result.items
                for claim_id in item.result.conflict.claim_ids
            )
            if depends_on_invalid_claim:
                invalid_run_ids.append(run.id)
                runs.append(replace(run, invalidated=True))
            else:
                runs.append(run)

        updated = self._updated(
            documents=documents,
            runs=tuple(runs),
            invalidated_claim_ids=tuple(
                sorted(set(self.invalidated_claim_ids) | invalid_claim_set)
            ),
            status=ProjectStatus.DRAFT,
        )
        updated = updated._with_event(
            AuditEventType.DOCUMENT_REVISED,
            actor=actor,
            details={
                "document_id": document_id,
                "old_revision": existing.revision or "",
                "new_revision": revision or "",
            },
        )
        if invalid_claim_ids:
            updated = updated._with_event(
                AuditEventType.SOURCES_INVALIDATED,
                actor=actor,
                details={
                    "document_id": document_id,
                    "claim_ids": ",".join(invalid_claim_ids),
                    "run_ids": ",".join(sorted(invalid_run_ids)),
                },
            )
        return DocumentRevisionResult(
            project=updated,
            invalidated_claim_ids=invalid_claim_ids,
            invalidated_run_ids=tuple(sorted(invalid_run_ids)),
        )

    def replace_claims_for_document(
        self,
        document_id: str,
        claims: Iterable[Claim],
        *,
        actor: str = "system",
    ) -> CrowProject:
        additions = tuple(claims)
        if any(claim.provenance.document_id != document_id for claim in additions):
            raise ValueError("All replacement Claims must reference the revised document")
        retained = tuple(
            claim for claim in self.claims if claim.provenance.document_id != document_id
        )
        base = self._updated(
            claims=retained,
            invalidated_claim_ids=tuple(
                claim_id
                for claim_id in self.invalidated_claim_ids
                if claim_id
                not in {
                    claim.id for claim in self.claims if claim.provenance.document_id == document_id
                }
            ),
        )
        return base.add_claims(additions, actor=actor)

    def add_claims(self, claims: Iterable[Claim], *, actor: str = "system") -> CrowProject:
        additions = tuple(claims)
        existing_ids = {claim.id for claim in self.claims}
        duplicate_ids = sorted(claim.id for claim in additions if claim.id in existing_ids)
        if duplicate_ids:
            raise ValueError("Duplicate Claim ids: " + ", ".join(duplicate_ids))

        addition_ids = [claim.id for claim in additions]
        if len(addition_ids) != len(set(addition_ids)):
            raise ValueError("Duplicate Claim ids in supplied batch")

        document_ids = {document.id for document in self.documents if document.active}
        unknown_sources = sorted(
            {
                claim.provenance.document_id
                for claim in additions
                if claim.provenance.document_id not in document_ids
            }
        )
        if unknown_sources:
            raise ValueError(
                "Claims reference documents not active in the project: "
                + ", ".join(unknown_sources)
            )
        updated = self._updated(claims=self.claims + additions)
        return updated._with_event(
            AuditEventType.CLAIMS_ADDED,
            actor=actor,
            details={"claim_ids": ",".join(sorted(addition_ids))},
        )

    def set_authority_policy(
        self,
        policy: AuthorityPolicy,
        *,
        actor: str = "system",
    ) -> CrowProject:
        return self._updated(authority_policy=policy)._with_event(
            AuditEventType.AUTHORITY_POLICY_SET,
            actor=actor,
            details={"policy_id": policy.id, "confirmed": str(policy.confirmed).lower()},
        )

    def enable_module(
        self,
        module_id: str,
        registry: ModuleRegistry,
        *,
        actor: str = "system",
    ) -> CrowProject:
        registered = registry.get(module_id)
        module = ProjectModule(
            module_id=registered.module_id,
            version=registered.version,
            enabled=True,
        )
        retained = tuple(item for item in self.modules if item.module_id != module_id)
        return self._updated(modules=retained + (module,))._with_event(
            AuditEventType.MODULE_ENABLED,
            actor=actor,
            details={"module_id": module.module_id, "version": module.version},
        )

    def mark_ready(self, *, actor: str = "system") -> CrowProject:
        errors = self.readiness_errors()
        if errors:
            raise ValueError("Project is not ready: " + "; ".join(errors))
        return self._updated(status=ProjectStatus.READY)._with_event(
            AuditEventType.PROJECT_READY,
            actor=actor,
        )

    def readiness_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not any(document.active for document in self.documents):
            errors.append("at least one active document is required")
        active_claims = [
            claim for claim in self.claims if claim.id not in set(self.invalidated_claim_ids)
        ]
        if not active_claims:
            errors.append("at least one non-invalidated Claim is required")
        if self.invalidated_claim_ids:
            errors.append("invalidated Claims must be replaced")
        if self.authority_policy is None:
            errors.append("authority policy is required")
        if not any(module.enabled for module in self.modules):
            errors.append("at least one module must be enabled")
        return tuple(errors)

    def execute(
        self,
        *,
        run_id: str,
        pricing_by_conflict_key: dict[tuple[str, str, str], PricingInput],
        rounding: RoundingPolicy,
        actor: str = "system",
    ) -> tuple[CrowProject, ProjectRun, tuple[DecisionGraph, ...]]:
        if self.status not in (ProjectStatus.READY, ProjectStatus.REVIEW_REQUIRED):
            raise ValueError(f"Project cannot execute from status {self.status.value}")
        authority_policy = self.authority_policy
        if authority_policy is None:
            raise ValueError("Authority policy is required")

        processing = self._updated(status=ProjectStatus.PROCESSING)._with_event(
            AuditEventType.RUN_STARTED,
            actor=actor,
            details={"run_id": run_id},
        )
        started_at = datetime.now(UTC)
        result = run_batch_claim_to_estimate(
            processing.claims,
            authority_policy,
            pricing_by_conflict_key,
            rounding,
        )

        graphs: list[DecisionGraph] = []
        graph_ids: list[str] = []
        review_required = False
        for index, item in enumerate(result.items, start=1):
            pipeline_result = item.result
            graph = build_decision_graph(
                tuple(
                    claim
                    for claim in processing.claims
                    if claim.id in pipeline_result.conflict.claim_ids
                ),
                pipeline_result.conflict,
                pipeline_result,
            )
            graphs.append(graph)
            graph_ids.append(f"{run_id}:graph:{index}")
            if pipeline_result.authority_decision.selected_claim_id is None:
                review_required = True

        final_status = ProjectStatus.REVIEW_REQUIRED if review_required else ProjectStatus.COMPLETED
        run = ProjectRun(
            id=run_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            result=result,
            graph_ids=tuple(graph_ids),
            status=final_status,
        )
        updated = processing._updated(
            status=final_status,
            runs=processing.runs + (run,),
        )._with_event(
            AuditEventType.RUN_COMPLETED,
            actor=actor,
            details={"run_id": run_id, "status": final_status.value},
        )
        return updated, run, tuple(graphs)

    def _with_event(
        self,
        event_type: AuditEventType,
        *,
        actor: str,
        details: dict[str, str] | None = None,
    ) -> CrowProject:
        event = AuditEvent.create(
            event_id=f"{self.id}:event:{len(self.audit_events) + 1}",
            project_id=self.id,
            event_type=event_type,
            actor=actor,
            details=details,
        )
        return self._updated(audit_events=self.audit_events + (event,))

    def _updated(self, **changes: Any) -> CrowProject:
        return replace(self, **changes, updated_at=datetime.now(UTC))
