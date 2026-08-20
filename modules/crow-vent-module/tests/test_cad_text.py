from crow_vent import CadVentTextPipeline

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


def test_pipeline_preserves_unknown_text_and_creates_only_supported_objects() -> None:
    result = CadVentTextPipeline().run_dxf_text(DXF, source_id="drawing.dxf")
    assert len(result.interpretations) == 3
    assert len(result.canonical_objects) == 2
    assert result.interpretations[2].kind == "unknown"
    assert result.interpretations[2].status == "needs_review"
    assert result.canonical_objects[0].evidence.locator == "A1"
