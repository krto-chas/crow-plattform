from crow_takeoff_consolidation import (
    LineStatus,
    consolidate_takeoffs,
    takeoff_from_geometry,
    takeoff_from_table,
    takeoff_from_text,
)
from crow_vent.lexicon import VentLexicon


def geometry_payload() -> dict:
    return {
        "schema_version": "crow-vent-quantity-v0.3",
        "lines": [
            {
                "component_code": "T",
                "component_name": "Tilluftskanal",
                "dimension": "Ø125",
                "quantity": 14,
                "length_m": 118.0,
                "system_ids": ["LB01"],
            },
            {
                "component_code": "TD",
                "component_name": "Tilluftsdon",
                "dimension": "Ej angiven",
                "quantity": 24,
                "length_m": None,
                "system_ids": ["LB01"],
            },
        ],
    }


def test_geometry_extractor_maps_lengths_and_counts() -> None:
    takeoff = takeoff_from_geometry(geometry_payload(), source_id="dxf:V-57-1-01")
    assert len(takeoff.lines) == 2
    duct = next(line for line in takeoff.lines if line.kind.value == "duct")
    assert duct.quantity == 118.0
    assert duct.unit == "m"


def test_table_extractor_reads_duct_rows_with_units() -> None:
    rows = [
        ["Benämning", "Mängd", "Enhet"],
        ["T-125", "132", "m"],
        ["TD1", "24", "st"],
        ["Anteckning utan mängd", "", ""],
    ]
    takeoff = takeoff_from_table(
        rows, source_id="xlsx:mangdforteckning", lexicon=VentLexicon.default()
    )
    assert len(takeoff.lines) == 2
    duct = takeoff.lines[0]
    assert duct.dimension == "Ø125"
    assert duct.quantity == 132.0
    assert duct.unit == "m"
    assert any(item["reason"] == "no_lexicon_match" for item in takeoff.skipped)


def test_text_extractor_counts_components_and_reports_duct_mentions() -> None:
    segments = [
        "I entréplan monteras 24 st TD1 jämnt fördelade.",
        "T-125",
    ]
    takeoff = takeoff_from_text(
        segments, source_id="pdf:beskrivning", lexicon=VentLexicon.default()
    )
    assert len(takeoff.lines) == 1
    assert takeoff.lines[0].quantity == 24.0
    assert any(item["reason"] == "duct_mention_without_length" for item in takeoff.skipped)


def test_consolidation_flags_discrepancy_and_corroborates_counts() -> None:
    geometry = takeoff_from_geometry(geometry_payload(), source_id="dxf:V-57-1-01")
    table = takeoff_from_table(
        [["T-125", "132", "m"], ["TD1", "24", "st"]],
        source_id="xlsx:mangdforteckning",
        lexicon=VentLexicon.default(),
    )
    text = takeoff_from_text(
        ["I entréplan monteras 24 st TD1 jämnt fördelade."],
        source_id="pdf:beskrivning",
        lexicon=VentLexicon.default(),
    )
    result = consolidate_takeoffs([geometry, table, text])

    assert result["schema_version"].startswith("crow-takeoff-consolidation")
    by_key = {(line["kind"], line["code"], line["dimension"]): line for line in result["lines"]}

    duct = by_key[("duct", "T", "Ø125")]
    assert duct["status"] == LineStatus.DISCREPANT.value
    assert duct["selected_quantity"] is None

    component = by_key[("component", "TD", "Ej angiven")]
    assert component["status"] == LineStatus.CORROBORATED.value
    assert component["selected_quantity"] == 24

    assert len(result["client_questions"]) == 1
    assert "Ø125" in result["client_questions"][0]["question"]
    assert result["total_component_count"] == 24
    assert result["total_duct_length_m"] == 0


def test_consolidation_within_tolerance_is_corroborated() -> None:
    geometry = takeoff_from_geometry(
        {
            "lines": [
                {
                    "component_code": "T",
                    "component_name": "Tilluftskanal",
                    "dimension": "Ø125",
                    "quantity": 14,
                    "length_m": 118.0,
                    "system_ids": ["LB01"],
                }
            ]
        },
        source_id="dxf:V-57-1-01",
    )
    table = takeoff_from_table(
        [["T-125", "119,5", "m"]], source_id="xlsx:mangd", lexicon=VentLexicon.default()
    )
    result = consolidate_takeoffs([geometry, table])
    line = result["lines"][0]
    assert line["status"] == LineStatus.CORROBORATED.value
    assert line["selected_quantity"] == 118.0
    assert result["total_duct_length_m"] == 118.0


def test_unit_mismatch_is_never_averaged() -> None:
    geometry = takeoff_from_geometry(
        {
            "lines": [
                {
                    "component_code": "T",
                    "component_name": "Tilluftskanal",
                    "dimension": "Ø125",
                    "quantity": 14,
                    "length_m": 118.0,
                    "system_ids": ["LB01"],
                }
            ]
        },
        source_id="dxf:V-57-1-01",
    )
    table = takeoff_from_table(
        [["T-125", "118", "st"]], source_id="xlsx:fel-enhet", lexicon=VentLexicon.default()
    )
    result = consolidate_takeoffs([geometry, table])
    line = result["lines"][0]
    assert line["status"] == LineStatus.UNIT_MISMATCH.value
    assert line["selected_quantity"] is None
    assert len(result["client_questions"]) == 1
