from pathlib import Path

import pytest

from crow_cad_text import CadTextExtractor, CadVentTextPipeline

DXF = """0
SECTION
2
ENTITIES
0
TEXT
5
A1
8
V-57--
10
12.5
20
7.25
40
2.5
50
90
1
TD1
0
MTEXT
5
A2
8
KANAL
10
5
20
6
3
T13-250
1
X400-V1
0
ATTRIB
5
A3
8
TEXT
10
1
20
2
1
HELT OKÄND
0
ENDSEC
0
EOF
"""


def test_extracts_explicit_dxf_text_with_evidence() -> None:
    result = CadTextExtractor().extract_dxf_text(DXF, source_id="drawing.dxf")
    assert result.source_format == "dxf"
    assert result.text_entity_count == 3
    assert result.entities[0].handle == "A1"
    assert result.entities[0].layer == "V-57--"
    assert result.entities[0].x == 12.5
    assert result.entities[1].text == "T13-250X400-V1"
    assert len(result.source_sha256) == 64


def test_pipeline_preserves_unknown_text_and_creates_only_supported_objects() -> None:
    result = CadVentTextPipeline().run_dxf_text(DXF, source_id="drawing.dxf")
    assert len(result.interpretations) == 3
    assert len(result.canonical_objects) == 2
    assert result.interpretations[2].kind == "unknown"
    assert result.interpretations[2].status == "needs_review"
    assert result.canonical_objects[0].evidence.locator == "A1"


def test_dwg_is_reported_as_unsupported_without_guessing(tmp_path: Path) -> None:
    path = tmp_path / "drawing.dwg"
    path.write_bytes(b"AC1032\x00binary")
    result = CadTextExtractor().extract_path(path)
    assert result.source_format == "dwg"
    assert result.text_entity_count == 0
    assert "not implemented" in result.warnings[0]


def test_rejects_other_formats(tmp_path: Path) -> None:
    path = tmp_path / "drawing.txt"
    path.write_text("text")
    with pytest.raises(ValueError, match="Unsupported CAD text source format"):
        CadTextExtractor().extract_path(path)
