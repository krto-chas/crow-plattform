from pathlib import Path
from typing import cast

from crow_ovk_legacy import LegacyHistoryCommitRepository, historical_commit_from_payload


def _payload() -> dict[str, object]:
    digest = "a" * 64
    return {
        "inspection_id": "legacy-2018-001",
        "project_id": "project-1",
        "inspector": "Historisk import",
        "inspection_date": "2018-05-14",
        "source_sha256": digest,
        "source_filename": "ovk-2018.xlsx",
        "facts": [
            {
                "field": "inspection_date",
                "value": "2018-05-14",
                "source_id": "legacy:aaa:sheet:1",
                "filename": "ovk-2018.xlsx",
                "locator": "sheet:OVK:cells:A1-D1",
                "source_sha256": digest,
            },
            {
                "field": "apartment_number",
                "value": "1203",
                "source_id": "legacy:aaa:sheet:2",
                "filename": "ovk-2018.xlsx",
                "locator": "sheet:OVK:cells:A2-D2",
                "source_sha256": digest,
            },
            {
                "field": "measured_airflow",
                "value": "8 l/s",
                "source_id": "legacy:aaa:sheet:2",
                "filename": "ovk-2018.xlsx",
                "locator": "sheet:OVK:cells:A2-D2",
                "source_sha256": digest,
            },
            {
                "field": "finding",
                "value": "Lågt frånluftsflöde",
                "source_id": "legacy:aaa:sheet:2",
                "filename": "ovk-2018.xlsx",
                "locator": "sheet:OVK:cells:A2-D2",
                "source_sha256": digest,
            },
        ],
    }


def test_legacy_commit_materializes_field_history(tmp_path: Path) -> None:
    historical = historical_commit_from_payload(_payload())
    digest = LegacyHistoryCommitRepository(tmp_path).commit(historical)

    assert len(digest) == 64
    assert (tmp_path / "ovk-field-sync" / "legacy-2018-001.json").is_file()
    assert (tmp_path / "ovk-field-context" / "legacy-2018-001.json").is_file()
    assert (tmp_path / "ovk-legacy-import" / "legacy-2018-001.json").is_file()

    context = (tmp_path / "ovk-field-context" / "legacy-2018-001.json").read_text()
    snapshot = (tmp_path / "ovk-field-sync" / "legacy-2018-001.json").read_text()
    assert '"source_kind": "legacy_import"' in context
    assert '"number": "1203"' in snapshot
    assert '"legacy_source"' in snapshot
    assert '"measured_airflow"' in snapshot


def test_legacy_commit_rejects_mixed_source_hashes(tmp_path: Path) -> None:
    payload = _payload()
    facts = list(cast(list[dict[str, object]], payload["facts"]))
    facts[0] = {**facts[0], "source_sha256": "b" * 64}
    payload["facts"] = facts
    historical = historical_commit_from_payload(payload)

    try:
        LegacyHistoryCommitRepository(tmp_path).commit(historical)
    except ValueError as exc:
        assert "source SHA-256" in str(exc)
    else:
        raise AssertionError("mixed provenance SHA must be rejected")
