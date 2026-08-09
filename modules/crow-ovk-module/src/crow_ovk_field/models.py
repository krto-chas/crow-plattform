from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from crow_ovk import EvidenceOrigin, FindingSeverity, OvkFinding


class UnitKind(StrEnum):
    APARTMENT = "apartment"
    PREMISES = "premises"


class PhotoSyncStatus(StrEnum):
    LOCAL = "local"
    QUEUED = "queued"
    SYNCED = "synced"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FieldUnit:
    unit_id: str
    inspection_id: str
    number: str
    kind: UnitKind = UnitKind.APARTMENT
    label: str = ""

    def __post_init__(self) -> None:
        if not self.unit_id.strip():
            raise ValueError("unit_id must not be empty")
        if not self.inspection_id.strip():
            raise ValueError("inspection_id must not be empty")
        if not self.number.strip():
            raise ValueError("unit number must not be empty")


@dataclass(frozen=True, slots=True)
class FieldRoom:
    room_id: str
    unit_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.room_id.strip() or not self.unit_id.strip() or not self.name.strip():
            raise ValueError("room_id, unit_id and name must not be empty")


@dataclass(frozen=True, slots=True)
class FieldFinding:
    finding_id: str
    inspection_id: str
    unit_id: str
    defect_type: str
    description: str
    severity: FindingSeverity = FindingSeverity.INFO
    room_id: str | None = None
    checkpoint_id: str | None = None
    system_id: str | None = None
    rule_refs: tuple[str, ...] = ()
    origin: EvidenceOrigin = EvidenceOrigin.OBSERVED

    def to_ovk_finding(self, *, photo_evidence_ref: str | None = None) -> OvkFinding:
        return OvkFinding(
            finding_id=self.finding_id,
            description=self.description,
            severity=self.severity,
            checkpoint_id=self.checkpoint_id,
            system_id=self.system_id,
            action_required=self.severity in {FindingSeverity.MINOR, FindingSeverity.MAJOR},
            origin=self.origin,
            evidence_ref=photo_evidence_ref,
        )


@dataclass(frozen=True, slots=True)
class OvkPhotoEvidence:
    photo_id: str
    inspection_id: str
    unit_id: str
    unit_number: str
    defect_type: str
    captured_at: str
    captured_by: str
    local_uri: str
    sha256: str
    mime_type: str
    room_id: str | None = None
    finding_id: str | None = None
    checkpoint_id: str | None = None
    system_id: str | None = None
    description: str = ""
    rule_refs: tuple[str, ...] = ()
    sync_status: PhotoSyncStatus = PhotoSyncStatus.LOCAL

    def __post_init__(self) -> None:
        required = {
            "photo_id": self.photo_id,
            "inspection_id": self.inspection_id,
            "unit_id": self.unit_id,
            "unit_number": self.unit_number,
            "defect_type": self.defect_type,
            "captured_at": self.captured_at,
            "captured_by": self.captured_by,
            "local_uri": self.local_uri,
            "sha256": self.sha256,
            "mime_type": self.mime_type,
        }
        empty = [name for name, value in required.items() if not value.strip()]
        if empty:
            raise ValueError(f"photo evidence requires non-empty fields: {', '.join(empty)}")
        valid_digest = len(self.sha256) == 64 and all(
            char in "0123456789abcdefABCDEF" for char in self.sha256
        )
        if not valid_digest:
            raise ValueError("sha256 must be a 64 character hexadecimal digest")
        if not self.mime_type.startswith("image/"):
            raise ValueError("mime_type must be an image media type")


@dataclass(frozen=True, slots=True)
class FieldInspectionData:
    inspection_id: str
    units: tuple[FieldUnit, ...] = ()
    rooms: tuple[FieldRoom, ...] = ()
    findings: tuple[FieldFinding, ...] = ()
    photos: tuple[OvkPhotoEvidence, ...] = ()
