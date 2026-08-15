from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from crow_ovk import CheckStatus, EvidenceOrigin, FindingSeverity, OvkFinding


class UnitKind(StrEnum):
    APARTMENT = "apartment"
    PREMISES = "premises"


class PhotoSyncStatus(StrEnum):
    LOCAL = "local"
    QUEUED = "queued"
    SYNCED = "synced"
    FAILED = "failed"


class UnitStatus(StrEnum):
    EJ_PABORJAD = "ej_paborjad"
    UA = "ua"
    ANMARKNING = "anmarkning"
    BOM = "bom"


class MeasurePointType(StrEnum):
    FRANLUFTSDON = "franluftsdon"
    TILLUFTSDON = "tilluftsdon"
    OVERLUFTSDON = "overluftsdon"


@dataclass(frozen=True, slots=True)
class KeyLog:
    """Nyckelspårning per enhet: mottagen/återlämnad med tidsstämplar.

    Huvudnyckel kräver alltid en skriven kommentar för spårbarhetens skull.
    """

    received: bool = False
    received_at: str | None = None
    returned: bool = False
    returned_at: str | None = None
    master_key_used: bool = False
    master_key_note: str = ""

    def __post_init__(self) -> None:
        if self.received and not (self.received_at or "").strip():
            raise ValueError("key received requires a timestamp")
        if self.returned and not (self.returned_at or "").strip():
            raise ValueError("key returned requires a timestamp")
        if self.returned and not self.received:
            raise ValueError("key cannot be returned before it was received")
        if self.master_key_used and not self.master_key_note.strip():
            raise ValueError("master key use requires a written note")


@dataclass(frozen=True, slots=True)
class FieldUnit:
    unit_id: str
    inspection_id: str
    number: str
    kind: UnitKind = UnitKind.APARTMENT
    label: str = ""
    status: UnitStatus = UnitStatus.EJ_PABORJAD
    checked_at: str | None = None
    bom_at: str | None = None
    bom_note: str = ""
    key: KeyLog | None = None

    def __post_init__(self) -> None:
        if not self.unit_id.strip():
            raise ValueError("unit_id must not be empty")
        if not self.inspection_id.strip():
            raise ValueError("inspection_id must not be empty")
        if not self.number.strip():
            raise ValueError("unit number must not be empty")
        if (
            self.status in (UnitStatus.UA, UnitStatus.ANMARKNING)
            and not (self.checked_at or "").strip()
        ):
            raise ValueError(f"unit status {self.status.value!r} requires checked_at")
        if self.status is UnitStatus.BOM and not (self.bom_at or "").strip():
            raise ValueError("bom status requires bom_at timestamp")


@dataclass(frozen=True, slots=True)
class FieldRoom:
    room_id: str
    unit_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.room_id.strip() or not self.unit_id.strip() or not self.name.strip():
            raise ValueError("room_id, unit_id and name must not be empty")


class TechnicalSpaceKind(StrEnum):
    FLAKTRUM = "flaktrum"
    TAKFLAKT = "takflakt"


@dataclass(frozen=True, slots=True)
class TechnicalSpace:
    """Allmänt teknikutrymme: fläktrum med aggregat eller frånluftsfläkt tak/vind."""

    space_id: str
    inspection_id: str
    kind: TechnicalSpaceKind
    label: str
    location: str = ""
    system_id: str | None = None

    def __post_init__(self) -> None:
        if not self.space_id.strip():
            raise ValueError("space_id must not be empty")
        if not self.label.strip():
            raise ValueError("technical space label must not be empty")


@dataclass(frozen=True, slots=True)
class FieldCheckpoint:
    """Kontrollpunkt i teknikutrymme. Utan kommentar är punkten UA (pass).

    En underkänd punkt kräver alltid en skriven notering.
    """

    checkpoint_id: str
    inspection_id: str
    space_id: str
    label: str
    status: CheckStatus = CheckStatus.PASS
    note: str = ""
    origin: EvidenceOrigin = EvidenceOrigin.OBSERVED

    def __post_init__(self) -> None:
        if not self.checkpoint_id.strip() or not self.space_id.strip():
            raise ValueError("checkpoint_id and space_id must not be empty")
        if not self.label.strip():
            raise ValueError("checkpoint label must not be empty")
        if self.status is CheckStatus.FAIL and not self.note.strip():
            raise ValueError(f"failed checkpoint {self.checkpoint_id!r} requires a written note")


@dataclass(frozen=True, slots=True)
class FieldMeasurement:
    """Flödesmätning vid ett don. Uppmätt värde är MEASURED, projekterat STATED.

    Ej mätbara don kräver skriven orsak; foto binds via en kopplad anmärkning.
    """

    measurement_id: str
    inspection_id: str
    unit_id: str
    point_type: MeasurePointType
    point_label: str
    room_id: str | None = None
    measurable: bool = True
    measured_value: Decimal | None = None
    designed_value: Decimal | None = None
    unit_of_measure: str = "l/s"
    not_measurable_reason: str = ""
    finding_id: str | None = None
    origin: EvidenceOrigin = EvidenceOrigin.MEASURED

    def __post_init__(self) -> None:
        if not self.measurement_id.strip() or not self.unit_id.strip():
            raise ValueError("measurement_id and unit_id must not be empty")
        if not self.point_label.strip():
            raise ValueError("measurement point_label must not be empty")
        if self.measurable:
            if self.measured_value is None:
                raise ValueError(
                    f"measurable point {self.measurement_id!r} requires measured_value"
                )
        else:
            if not self.not_measurable_reason.strip():
                raise ValueError(
                    f"not measurable point {self.measurement_id!r} requires a written reason"
                )
            if self.measured_value is not None:
                raise ValueError(
                    f"not measurable point {self.measurement_id!r} cannot carry a value"
                )

    @property
    def deviation(self) -> Decimal | None:
        if self.measured_value is None or self.designed_value is None:
            return None
        return self.measured_value - self.designed_value


def parse_flow_value(value: object) -> Decimal | None:
    text = str(value).strip().replace(",", ".") if value is not None else ""
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid flow value {text!r}") from exc


@dataclass(frozen=True, slots=True)
class WindowVentCheck:
    """Fönsterventil kontrolleras endast finns/finns ej, aldrig med mätning.

    Kontrolleras inte alls i fastigheter med FT/FTX.
    """

    check_id: str
    inspection_id: str
    unit_id: str
    present: bool
    room_id: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.unit_id.strip():
            raise ValueError("check_id and unit_id must not be empty")


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
    space_id: str | None = None
    description: str = ""
    rule_refs: tuple[str, ...] = ()
    sync_status: PhotoSyncStatus = PhotoSyncStatus.LOCAL

    def __post_init__(self) -> None:
        required = {
            "photo_id": self.photo_id,
            "inspection_id": self.inspection_id,
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
        unit_bound = bool(self.unit_id.strip()) and bool(self.unit_number.strip())
        space_bound = bool((self.space_id or "").strip())
        if not unit_bound and not space_bound:
            raise ValueError(
                "photo evidence requires either a unit binding or a technical space binding"
            )
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
    measurements: tuple[FieldMeasurement, ...] = field(default=())
    window_vents: tuple[WindowVentCheck, ...] = field(default=())
    technical_spaces: tuple[TechnicalSpace, ...] = field(default=())
    checkpoints: tuple[FieldCheckpoint, ...] = field(default=())
