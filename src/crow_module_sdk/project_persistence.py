from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .audit import AuditEvent, AuditEventType
from .decision_models import AuthorityPolicy, AuthorityRule
from .models import Claim, Provenance
from .project import (
    CrowProject,
    DocumentRole,
    ProjectDocument,
    ProjectModule,
    ProjectStatus,
)


class JsonProjectRepository:
    SCHEMA_VERSION = "1.0"

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, project: CrowProject) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status.value,
                "documents": [
                    {
                        **asdict(document),
                        "role": document.role.value,
                    }
                    for document in project.documents
                ],
                "claims": [
                    {
                        "id": claim.id,
                        "namespace": claim.namespace,
                        "subject": claim.subject,
                        "property": claim.property,
                        "value": str(claim.value),
                        "value_type": "decimal" if isinstance(claim.value, Decimal) else "string",
                        "unit": claim.unit,
                        "provenance": asdict(claim.provenance),
                        "confidence": str(claim.confidence),
                    }
                    for claim in project.claims
                ],
                "authority_policy": self._serialize_policy(project.authority_policy),
                "modules": [asdict(module) for module in project.modules],
                "invalidated_claim_ids": list(project.invalidated_claim_ids),
                "audit_events": [
                    {
                        "id": event.id,
                        "project_id": event.project_id,
                        "event_type": event.event_type.value,
                        "occurred_at": event.occurred_at.isoformat(),
                        "actor": event.actor,
                        "details": dict(event.details),
                    }
                    for event in project.audit_events
                ],
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            },
        }
        self._path(project.id).write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def load(self, project_id: str) -> CrowProject | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("Unsupported CrowProject persistence schema")
        item = payload["project"]
        documents = tuple(
            ProjectDocument(
                id=document["id"],
                name=document["name"],
                role=DocumentRole(document["role"]),
                revision=document.get("revision"),
                checksum=document.get("checksum"),
                active=bool(document.get("active", True)),
            )
            for document in item["documents"]
        )
        claims = tuple(
            Claim(
                id=claim["id"],
                namespace=claim["namespace"],
                subject=claim["subject"],
                property=claim["property"],
                value=(
                    Decimal(claim["value"]) if claim["value_type"] == "decimal" else claim["value"]
                ),
                unit=claim.get("unit"),
                provenance=Provenance(**claim["provenance"]),
                confidence=Decimal(claim["confidence"]),
            )
            for claim in item["claims"]
        )
        modules = tuple(ProjectModule(**module) for module in item["modules"])
        audit_events = tuple(
            AuditEvent(
                id=event["id"],
                project_id=event["project_id"],
                event_type=AuditEventType(event["event_type"]),
                occurred_at=datetime.fromisoformat(event["occurred_at"]),
                actor=event["actor"],
                details=event["details"],
            )
            for event in item.get("audit_events", [])
        )
        return CrowProject(
            id=item["id"],
            name=item["name"],
            status=ProjectStatus(item["status"]),
            documents=documents,
            claims=claims,
            authority_policy=self._deserialize_policy(item.get("authority_policy")),
            modules=modules,
            runs=(),
            invalidated_claim_ids=tuple(item.get("invalidated_claim_ids", [])),
            audit_events=audit_events,
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    def _path(self, project_id: str) -> Path:
        safe_id = project_id.replace("/", "_").replace("\\", "_")
        return self._directory / f"{safe_id}.json"

    @staticmethod
    def _serialize_policy(policy: AuthorityPolicy | None) -> dict[str, Any] | None:
        if policy is None:
            return None
        return {
            "id": policy.id,
            "confirmed": policy.confirmed,
            "rules": [asdict(rule) for rule in policy.rules],
        }

    @staticmethod
    def _deserialize_policy(payload: dict[str, Any] | None) -> AuthorityPolicy | None:
        if payload is None:
            return None
        raw_rules = payload["rules"]
        if not isinstance(raw_rules, list):
            raise ValueError("Authority policy rules must be a list")
        return AuthorityPolicy(
            id=str(payload["id"]),
            confirmed=bool(payload["confirmed"]),
            rules=tuple(AuthorityRule(**rule) for rule in raw_rules),
        )
