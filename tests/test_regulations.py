from datetime import date

import pytest

from crow_regulations import (
    RuleStatus,
    load_regulation_library,
    reference_by_id,
    search_regulations,
    source_by_id,
)


def test_library_loads_unique_sources_and_references() -> None:
    sources = load_regulation_library()
    assert len(sources) >= 10
    assert len({source.source_id for source in sources}) == len(sources)
    reference_ids = [ref.reference_id for source in sources for ref in source.references]
    assert len(reference_ids) == len(set(reference_ids))


def test_ovk_core_sources_are_present() -> None:
    assert source_by_id("PBL-2010-900").status is RuleStatus.CURRENT
    assert source_by_id("PBF-2011-338").status is RuleStatus.CURRENT
    ovk = source_by_id("BFS-2011-16-OVK")
    assert "BFS 2025:6" in ovk.amended_by
    assert source_by_id("BFS-2012-7-OVKAR").status is RuleStatus.GUIDANCE


def test_bbr_is_historical_after_transition() -> None:
    bbr = source_by_id("BFS-2011-6-BBR")
    assert bbr.status is RuleStatus.HISTORICAL
    assert bbr.active_on(date(2026, 6, 30))
    assert not bbr.active_on(date(2026, 7, 1))


def test_afs_2023_12_supersedes_old_workplace_rules() -> None:
    current = source_by_id("AFS-2023-12")
    assert "AFS-2020-1" in current.supersedes
    assert current.active_on(date(2026, 8, 9))
    old = source_by_id("AFS-2020-1")
    assert old.status is RuleStatus.HISTORICAL
    assert not old.active_on(date(2025, 1, 1))


def test_reference_lookup_keeps_source_context() -> None:
    source, reference = reference_by_id("AFS-2023-12:5:3")
    assert source.source_id == "AFS-2023-12"
    assert reference.locator == "5 kap. 3 §"
    assert "ventilation" in reference.topics


def test_topic_search_can_include_legacy_rules() -> None:
    ventilation = search_regulations(topics=("ventilation",))
    ids = {source.source_id for source in ventilation}
    assert "BFS-2024-8-HHM" in ids
    assert "BFS-2011-6-BBR" in ids

    current_only = search_regulations(
        topics=("ventilation",),
        active_on=date(2026, 8, 9),
        include_historical=False,
    )
    current_ids = {source.source_id for source in current_only}
    assert "BFS-2011-6-BBR" not in current_ids
    assert "AFS-2023-12" in current_ids


def test_unknown_identifiers_fail_closed() -> None:
    with pytest.raises(KeyError):
        source_by_id("NOT-A-RULE")
    with pytest.raises(KeyError):
        reference_by_id("NOT:A:REFERENCE")
