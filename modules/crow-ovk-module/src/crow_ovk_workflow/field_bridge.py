"""Protokollbrygga (pass 110): fältsnapshot → protokollutkast.

Anmärkningar grupperas per (feltyp, rum, klass) med lägenhetsnummer i
mallens format — "Smutsigt frånluftsdon – Badrum: 1201, 1202, 1501" — och
positionskod ur taxonomin 1.1–4.6. Besiktningsresultatet härleds
deterministiskt ur klassningen: minst en klass 2 ger EG, enbart klass 1 ger
godkänd med anmärkning, annars godkänd; klass 0 redovisas som upplysningar
och påverkar aldrig resultatet.

Alla grunddata är STATED/OBSERVED i fält; bryggan tillför inga bedömningar,
bara deterministisk aggregering. Täckningsförslaget från teknikutrymmena är
just ett förslag — systemförteckningens bekräftelse förblir ett manuellt
STATED-steg (pass 101).
"""

from __future__ import annotations

from dataclasses import dataclass

from crow_ovk import (
    CheckStatus,
    FindingSeverity,
    OvkAction,
    OvkCheckpoint,
    OvkFinding,
    OvkObject,
)
from crow_ovk_field.models import FieldInspectionData
from crow_ovk_field.positions import default_position_for

from .coverage import AggregatCoverage, AggregatStatus, InspectionCoverage


class Besiktningsresultat:
    GODKAND = "godkand"
    GODKAND_MED_ANMARKNING = "godkand_med_anmarkning"
    EJ_GODKAND = "ej_godkand"


@dataclass(frozen=True, slots=True)
class ProtokollAnmarkning:
    """En grupperad protokollrad: feltyp + rum + klass + lägenhetsnummer."""

    pos: str
    pos_label: str
    text: str
    classification: int
    defect_type: str
    defect_label: str
    room_label: str
    unit_numbers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FaltProtokollUtkast:
    inspection_id: str
    besiktningsresultat: str
    anmarkningar: tuple[ProtokollAnmarkning, ...]
    upplysningar: tuple[ProtokollAnmarkning, ...]
    suggested_coverage: InspectionCoverage


def _classification_of(severity: FindingSeverity, classification: int | None) -> int:
    if classification is not None:
        return classification
    if severity is FindingSeverity.MAJOR:
        return 2
    if severity is FindingSeverity.MINOR:
        return 1
    return 0


def _unit_sort_key(number: str) -> tuple[int, str]:
    return (int(number), "") if number.isdigit() else (10**9, number)


def _severity_for(classification: int) -> FindingSeverity:
    if classification == 2:
        return FindingSeverity.MAJOR
    if classification == 1:
        return FindingSeverity.MINOR
    return FindingSeverity.INFO


def build_protokoll_utkast(data: FieldInspectionData) -> FaltProtokollUtkast:
    from crow_ovk_field.defects import defect_type_by_id

    unit_numbers = {unit.unit_id: unit.number for unit in data.units}
    room_names = {room.room_id: room.name for room in data.rooms}

    grouped: dict[tuple[str, str, int], list[str]] = {}
    for finding in data.findings:
        classification = _classification_of(finding.severity, finding.classification)
        room_label = room_names.get(finding.room_id or "", "")
        key = (finding.defect_type, room_label, classification)
        number = unit_numbers.get(finding.unit_id, finding.unit_id)
        grouped.setdefault(key, []).append(number)

    rows: list[ProtokollAnmarkning] = []
    for (defect_type, room_label, classification), numbers in grouped.items():
        try:
            defect_label = defect_type_by_id(defect_type).label
        except KeyError:
            defect_label = defect_type
        position = default_position_for(defect_type)
        unique_numbers = tuple(sorted(set(numbers), key=_unit_sort_key))
        location = f" – {room_label}" if room_label else ""
        text = f"{defect_label}{location}: {', '.join(unique_numbers)}"
        rows.append(
            ProtokollAnmarkning(
                pos=position.position_id if position else "",
                pos_label=position.label if position else "",
                text=text,
                classification=classification,
                defect_type=defect_type,
                defect_label=defect_label,
                room_label=room_label,
                unit_numbers=unique_numbers,
            )
        )

    def _row_key(row: ProtokollAnmarkning) -> tuple[int, str, str]:
        return (-row.classification, row.pos, row.text)

    anmarkningar = tuple(sorted((row for row in rows if row.classification > 0), key=_row_key))
    upplysningar = tuple(sorted((row for row in rows if row.classification == 0), key=_row_key))

    if any(row.classification == 2 for row in anmarkningar):
        resultat = Besiktningsresultat.EJ_GODKAND
    elif anmarkningar:
        resultat = Besiktningsresultat.GODKAND_MED_ANMARKNING
    else:
        resultat = Besiktningsresultat.GODKAND

    suggested_coverage = InspectionCoverage(
        inspection_id=data.inspection_id,
        aggregat=tuple(
            AggregatCoverage(
                aggregat_id=space.space_id,
                label=space.label,
                status=AggregatStatus.BESIKTIGAD,
            )
            for space in data.technical_spaces
        ),
        system_list_confirmation=None,
    )

    return FaltProtokollUtkast(
        inspection_id=data.inspection_id,
        besiktningsresultat=resultat,
        anmarkningar=anmarkningar,
        upplysningar=upplysningar,
        suggested_coverage=suggested_coverage,
    )


def bridge_inspection_inputs(
    data: FieldInspectionData, utkast: FaltProtokollUtkast, *, ovk_object: OvkObject
) -> dict[str, object]:
    """Byggstenar för build_record ur fältdata + utkast.

    Kontrollpunkter tas från teknikutrymmenas fältkontroller; protokollraderna
    blir grupperade findings med severity härledd ur klassen. Mätningarna
    lämnas till flödesprotokollet (pass 111).
    """
    checkpoints = tuple(
        OvkCheckpoint(
            checkpoint_id=item.checkpoint_id,
            label=item.label,
            status=item.status,
            note=item.note,
        )
        for item in data.checkpoints
    ) or (
        OvkCheckpoint(
            checkpoint_id=f"{data.inspection_id}-falt",
            label="Fältrondering genomförd",
            status=CheckStatus.PASS,
        ),
    )
    findings = tuple(
        OvkFinding(
            finding_id=f"{data.inspection_id}-rad-{index + 1}",
            description=(f"[{row.pos}] " if row.pos else "") + row.text,
            severity=_severity_for(row.classification),
            action_required=row.classification > 0,
        )
        for index, row in enumerate((*utkast.anmarkningar, *utkast.upplysningar))
    )
    # Klass 2 (EG) genererar öppna åtgärdspunkter; derive_conclusion ger då
    # DEFICIENCIES tills åtgärderna stängts — exakt ombesiktningens semantik.
    rows = (*utkast.anmarkningar, *utkast.upplysningar)
    actions = tuple(
        OvkAction(
            action_id=f"{data.inspection_id}-atgard-{index + 1}",
            finding_id=f"{data.inspection_id}-rad-{index + 1}",
            description=f"Åtgärda: {row.text}",
        )
        for index, row in enumerate(rows)
        if row.classification == 2
    )
    return {
        "inspection_id": data.inspection_id,
        "ovk_object": ovk_object,
        "checkpoints": checkpoints,
        "findings": findings,
        "actions": actions,
    }


def utkast_to_payload(utkast: FaltProtokollUtkast) -> dict[str, object]:
    def _rows(rows: tuple[ProtokollAnmarkning, ...]) -> list[dict[str, object]]:
        return [
            {
                "pos": row.pos,
                "pos_label": row.pos_label,
                "text": row.text,
                "classification": row.classification,
                "defect_type": row.defect_type,
                "defect_label": row.defect_label,
                "room_label": row.room_label,
                "unit_numbers": list(row.unit_numbers),
            }
            for row in rows
        ]

    return {
        "inspection_id": utkast.inspection_id,
        "besiktningsresultat": utkast.besiktningsresultat,
        "anmarkningar": _rows(utkast.anmarkningar),
        "upplysningar": _rows(utkast.upplysningar),
        "suggested_coverage": {
            "aggregat": [
                {"aggregat_id": item.aggregat_id, "label": item.label, "status": item.status.value}
                for item in utkast.suggested_coverage.aggregat
            ]
        },
    }
