"""Pass 101: besiktningstäckning — alla fläktar/aggregat måste adresseras explicit."""

from __future__ import annotations

import pytest

from crow_ovk_workflow import (
    AggregatCoverage,
    AggregatStatus,
    BekraftelseRoll,
    CoverageError,
    FastighetsnivaStatus,
    InspectionCoverage,
    SystemForteckningBekraftelse,
    coverage_from_payload,
    coverage_to_payload,
    validate_coverage_for_finalization,
)

_CONFIRMATION = SystemForteckningBekraftelse(
    confirmed_by="Stina Besiktning", role=BekraftelseRoll.BESIKTNINGSMAN
)


def _agg(status: AggregatStatus, **kwargs: str) -> AggregatCoverage:
    return AggregatCoverage(
        aggregat_id=kwargs.get("aggregat_id", "agg-1"),
        label=kwargs.get("label", "LB01"),
        status=status,
        justification=kwargs.get("justification", ""),
        stated_by=kwargs.get("stated_by", ""),
    )


def test_ej_besiktigad_requires_written_justification_and_stated_by() -> None:
    with pytest.raises(ValueError, match="justification"):
        _agg(AggregatStatus.EJ_BESIKTIGAD)
    with pytest.raises(ValueError, match="stated_by"):
        _agg(AggregatStatus.EJ_BESIKTIGAD, justification="Avstängt aggregat, ej i drift")
    item = _agg(
        AggregatStatus.EJ_BESIKTIGAD,
        justification="Låst fläktrum, nyckel saknades vid förrättningen",
        stated_by="Stina Besiktning",
    )
    assert item.status is AggregatStatus.EJ_BESIKTIGAD


def test_finalization_gate_rejects_missing_or_empty_coverage() -> None:
    with pytest.raises(CoverageError, match="saknas"):
        validate_coverage_for_finalization(None)
    with pytest.raises(CoverageError, match="tom"):
        validate_coverage_for_finalization(InspectionCoverage(inspection_id="ovk-1"))
    validate_coverage_for_finalization(
        InspectionCoverage(
            inspection_id="ovk-1",
            aggregat=(_agg(AggregatStatus.BESIKTIGAD),),
        )
    )


def test_fastighetsniva_derivation_is_deterministic() -> None:
    unconfirmed = InspectionCoverage(
        inspection_id="ovk-1", aggregat=(_agg(AggregatStatus.BESIKTIGAD),)
    )
    assert unconfirmed.fastighetsniva is FastighetsnivaStatus.SYSTEMFORTECKNING_EJ_BEKRAFTAD

    partial = InspectionCoverage(
        inspection_id="ovk-1",
        aggregat=(
            _agg(AggregatStatus.BESIKTIGAD),
            _agg(
                AggregatStatus.EJ_BESIKTIGAD,
                aggregat_id="agg-2",
                label="FF2",
                justification="Aggregatet demonterat inför utbyte",
                stated_by="Stina Besiktning",
            ),
        ),
        system_list_confirmation=_CONFIRMATION,
    )
    assert partial.is_delbesiktning
    assert partial.fastighetsniva is FastighetsnivaStatus.DELVIS_BESIKTADE
    assert tuple(item.label for item in partial.uninspected) == ("FF2",)

    complete = InspectionCoverage(
        inspection_id="ovk-1",
        aggregat=(
            _agg(AggregatStatus.BESIKTIGAD),
            _agg(AggregatStatus.EJ_TILLAMPLIG, aggregat_id="agg-3", label="Kolfilterfläkt"),
        ),
        system_list_confirmation=_CONFIRMATION,
    )
    assert not complete.is_delbesiktning
    assert complete.fastighetsniva is FastighetsnivaStatus.SAMTLIGA_BESIKTADE


def test_duplicate_aggregat_ids_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        InspectionCoverage(
            inspection_id="ovk-1",
            aggregat=(_agg(AggregatStatus.BESIKTIGAD), _agg(AggregatStatus.EJ_TILLAMPLIG)),
        )


def test_coverage_payload_roundtrip() -> None:
    coverage = InspectionCoverage(
        inspection_id="ovk-1",
        aggregat=(
            _agg(AggregatStatus.BESIKTIGAD),
            _agg(
                AggregatStatus.EJ_BESIKTIGAD,
                aggregat_id="agg-2",
                label="FF2",
                justification="Boende nekade tillträde till vindsfläktrum",
                stated_by="Stina Besiktning",
            ),
        ),
        system_list_confirmation=_CONFIRMATION,
    )
    payload = coverage_to_payload(coverage)
    assert payload["is_delbesiktning"] is True
    assert payload["fastighetsniva"] == "delvis_besiktade"
    restored = coverage_from_payload(payload)
    assert restored == coverage


def test_record_without_coverage_is_never_protocol_ready() -> None:
    from crow_ovk import CheckStatus, OvkCheckpoint, OvkObject, VentilationSystemRef
    from crow_ovk_workflow import build_record

    record = build_record(
        inspection_id="ovk-x",
        ovk_object=OvkObject(
            object_id="o1", project_id="p1", building_id="b1", name="Hus", address=None
        ),
        systems=(VentilationSystemRef("F01", "F", "System F01"),),
        checkpoints=(OvkCheckpoint(checkpoint_id="c1", label="Flöden", status=CheckStatus.PASS),),
    )
    assert record.coverage is None
    assert not record.coverage_complete
    assert not record.protocol_ready


def test_intyg_carries_delbesiktningsmarkering_and_justifications(tmp_path: object) -> None:
    from datetime import date

    from crow_ovk import CheckStatus, OvkCheckpoint, OvkObject, VentilationSystemRef
    from crow_ovk_intyg import Behorighet, Byggnadsagare, Funktionskontrollant, build_intyg
    from crow_ovk_intyg.service import intyg_from_payload, intyg_to_payload
    from crow_ovk_pricing import BuildingCategory, InspectionType
    from crow_ovk_workflow import build_record

    coverage = InspectionCoverage(
        inspection_id="ovk-d",
        aggregat=(
            _agg(AggregatStatus.BESIKTIGAD),
            _agg(
                AggregatStatus.EJ_BESIKTIGAD,
                aggregat_id="agg-2",
                label="FF2 vind",
                justification="Låst vindsutrymme, förvaltaren saknade nyckel",
                stated_by="Stina Besiktning",
            ),
        ),
        system_list_confirmation=_CONFIRMATION,
    )
    record = build_record(
        inspection_id="ovk-d",
        ovk_object=OvkObject(
            object_id="o1", project_id="p1", building_id="b1", name="Hus", address=None
        ),
        systems=(VentilationSystemRef("F01", "F", "System F01"),),
        checkpoints=(OvkCheckpoint(checkpoint_id="c1", label="Flöden", status=CheckStatus.PASS),),
        coverage=coverage,
    )
    assert record.protocol_ready
    intyg = build_intyg(
        intyg_id="intyg-d",
        record=record,
        fastighetsbeteckning="Berget 1",
        byggnadsagare=Byggnadsagare(name="Brf Berget"),
        funktionskontrollant=Funktionskontrollant(
            name="Stina Besiktning",
            behorighet=Behorighet.K,
            certification_body="RISE",
            certificate_number="1234",
        ),
        inspection_type=InspectionType.ATERKOMMANDE,
        inspection_date=date(2026, 8, 1),
        building_category=BuildingCategory.FLERBOSTADSHUS,
    )
    assert intyg.delbesiktning is True
    assert intyg.fastighetsniva is FastighetsnivaStatus.DELVIS_BESIKTADE
    assert tuple(item.label for item in intyg.uninspected_aggregat) == ("FF2 vind",)
    restored = intyg_from_payload(intyg_to_payload(intyg))
    assert restored.delbesiktning is True
    assert restored.uninspected_aggregat == intyg.uninspected_aggregat

    from crow_ovk_export import intyg_pdf

    payload = intyg_pdf(intyg)
    assert payload.startswith(b"%PDF")

    from crow_ovk_besiktningsbevakning import build_watchlist

    watchlist = build_watchlist(project_id="p1", intyg=(intyg,), cases=(), today=date(2026, 8, 17))
    assert watchlist.items[0].delbesiktning is True
