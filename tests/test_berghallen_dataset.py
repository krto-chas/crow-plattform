from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

_DATASET_DIR = Path(__file__).resolve().parents[1] / "evidence/reference_datasets/berghallen"


def _load(name: str) -> dict[str, object]:
    payload = json.loads((_DATASET_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_manifest_registers_archive_and_key_documents() -> None:
    manifest = _load("manifest.json")
    assert manifest["dataset_id"] == "berghallen-kfu"
    sources = manifest["sources"]
    assert isinstance(sources, list)
    by_id = {source["source_id"]: source for source in sources}
    assert "forfragan-arkiv" in by_id
    assert by_id["forfragan-arkiv"]["role"] == "project_archive"
    assert "v-57-besk" in by_id
    assert by_id["v-57-besk"]["role"] == "specification"
    checksums = [source["checksum_sha256"] for source in sources]
    assert all(isinstance(item, str) and len(item) == 64 for item in checksums)
    assert len(set(checksums)) == len(checksums)


def test_manifest_declares_raster_limitation() -> None:
    manifest = _load("manifest.json")
    limitations = manifest["known_limitations"]
    assert isinstance(limitations, list)
    assert any("vektortext" in str(item) for item in limitations)


def test_expected_findings_totals_are_internally_consistent() -> None:
    facit = _load("expected_findings.json")
    stairwells = facit["stairwells"]
    totals = facit["totals"]
    assert isinstance(stairwells, list)
    assert isinstance(totals, dict)
    apartments = sum(int(item["apartments"]) for item in stairwells)
    strings = sum(int(item["shaft_strings"]) for item in stairwells)
    shaft_length = sum(int(item["shaft_length_m"]) for item in stairwells)
    rectangular = sum(int(item["rectangular_length_m"]) for item in stairwells)
    assert apartments == totals["apartments"] == 33
    assert strings == totals["shaft_strings"] == 99
    assert shaft_length == totals["shaft_length_m"]
    assert rectangular == totals["rectangular_length_m"]


def test_strings_follow_three_per_apartment_rule() -> None:
    facit = _load("expected_findings.json")
    per_apartment = int(str(facit["strings_per_apartment"]))
    assert per_apartment == 3
    stairwells = facit["stairwells"]
    assert isinstance(stairwells, list)
    for stairwell in stairwells:
        assert int(stairwell["shaft_strings"]) == per_apartment * int(stairwell["apartments"])


def test_known_conflict_and_specification_gap_are_recorded() -> None:
    facit = _load("expected_findings.json")
    tightness = facit["tightness"]
    assert isinstance(tightness, dict)
    conflict = tightness["known_conflict"]
    assert isinstance(conflict, dict)
    assert conflict["duct_family"] == "rektangular"
    assert sorted(conflict["classes"]) == ["B", "C"]
    assert facit["specification_apartment_count"] == 35
    questions = facit["buyer_questions"]
    assert isinstance(questions, list)
    assert len(questions) >= 2


def test_levels_increase_monotonically() -> None:
    facit = _load("expected_findings.json")
    levels = facit["levels_fg"]
    assert isinstance(levels, dict)
    values = [float(levels[key]) for key in sorted(levels)]
    assert values == sorted(values)


def test_archive_checksum_matches_when_customer_files_present() -> None:
    archive_env = os.environ.get("CROW_BERGHALLEN_ARCHIVE")
    if not archive_env:
        pytest.skip("CROW_BERGHALLEN_ARCHIVE not set; customer files stay outside the repo")
    manifest = _load("manifest.json")
    sources = manifest["sources"]
    assert isinstance(sources, list)
    expected = next(
        source["checksum_sha256"] for source in sources if source["source_id"] == "forfragan-arkiv"
    )
    digest = hashlib.sha256(Path(archive_env).read_bytes()).hexdigest()
    assert digest == expected
