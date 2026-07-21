from __future__ import annotations

import json
from pathlib import Path

import pytest

from crow_project_dataset import (
    ProjectDataset,
    ReferenceQuality,
    SourceRole,
    detect_format,
    inspect_source,
    write_manifest,
)


def test_detects_dwg_signature_and_version(tmp_path: Path) -> None:
    path = tmp_path / "drawing.dwg"
    path.write_bytes(b"AC1032" + b"\x00" * 20)
    assert detect_format(path) == ("dwg", "application/acad", "AutoCAD 2018+")


def test_detects_ifc_schema(tmp_path: Path) -> None:
    path = tmp_path / "model.ifc"
    path.write_text("ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('IFC4'));\n", encoding="ascii")
    assert detect_format(path) == ("ifc", "application/x-step", "IFC4")


def test_manifest_is_deterministic_and_validated(tmp_path: Path) -> None:
    source_path = tmp_path / "offer.pdf"
    source_path.write_bytes(b"%PDF-1.7\nexample")
    source = inspect_source(
        source_path,
        source_id="offer",
        role=SourceRole.QUANTITY_REFERENCE,
        reference_quality=ReferenceQuality.PARTIAL,
    )
    dataset = ProjectDataset(dataset_id="demo", title="Demo", sources=(source,))
    output = tmp_path / "manifest.json"
    write_manifest(dataset, output)
    first = output.read_bytes()
    write_manifest(dataset, output)
    assert output.read_bytes() == first
    parsed = json.loads(first)
    assert parsed["sources"][0]["format_id"] == "pdf"
    assert parsed["sources"][0]["format_version"] == "1.7"


def test_duplicate_source_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "a.pdf"
    path.write_bytes(b"%PDF-1.4")
    source = inspect_source(
        path,
        source_id="same",
        role=SourceRole.DRAWING,
        reference_quality=ReferenceQuality.SUPPORTING,
    )
    dataset = ProjectDataset(dataset_id="demo", title="Demo", sources=(source, source))
    with pytest.raises(ValueError, match="source_id values must be unique"):
        dataset.validate()
