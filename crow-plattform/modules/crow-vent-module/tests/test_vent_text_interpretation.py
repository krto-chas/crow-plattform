from crow_vent import LayerProfileEngine, VentTextInterpreter


def test_interprets_duct_with_traceable_evidence() -> None:
    result = VentTextInterpreter().interpret(
        " T13-250×400-V1 ",
        source_id="drawing-1",
        layer="V-57--",
        entity_handle="ABC1",
    )
    assert result.kind == "duct"
    assert result.status == "interpreted"
    assert result.duct is not None
    assert result.duct.dimension.width_mm == 250
    assert result.evidence["entity_handle"] == "ABC1"
    assert result.evidence["layer_profile"] == "sb11"


def test_ambiguous_af_requires_review_without_context() -> None:
    result = VentTextInterpreter().interpret("AF01", source_id="drawing-1", layer="TEXT")
    assert result.kind == "component"
    assert result.status == "needs_review"
    assert "ambiguous_component_code" in result.review_reasons
    assert result.component is not None and len(result.component.alternatives) == 1


def test_af_is_resolved_by_system_context() -> None:
    result = VentTextInterpreter().interpret(
        "AF01",
        source_id="drawing-1",
        layer="V-57--",
        system_context="QH avfuktare",
    )
    assert result.status == "interpreted"
    assert result.component is not None
    assert result.component.label.startswith("Avfuktare")


def test_profile_chain_project_customer_sb11_coclass_freehand() -> None:
    engine = LayerProfileEngine(
        {"KANAL": "project_duct"},
        customer_layers={"CUST-DON": "customer_terminal"},
        coclass_patterns={r"^V-[A-Z]{2}-": "coclass_ventilation"},
    )
    assert engine.resolve("KANAL").profile == "project"  # type: ignore[union-attr]
    assert engine.resolve("CUST-DON").profile == "customer"  # type: ignore[union-attr]
    assert engine.resolve("V-57--").profile == "sb11"  # type: ignore[union-attr]
    assert engine.resolve("V-QM-01").profile == "coclass"  # type: ignore[union-attr]
    assert LayerProfileEngine().resolve("DON").profile == "freehand"  # type: ignore[union-attr]


def test_batch_keeps_unknowns_for_review() -> None:
    batch = VentTextInterpreter().interpret_many(
        [
            {"text": "TD1", "layer": "DON", "entity_handle": "1"},
            {"text": "HELT OKÄND", "layer": "MYSTERY", "entity_handle": "2"},
        ],
        source_id="drawing-2",
    )
    assert batch["interpretation_count"] == 2
    assert batch["interpreted_count"] == 1
    assert batch["review_count"] == 1
    unknown = batch["interpretations"][1]
    assert unknown["kind"] == "unknown"
    assert set(unknown["review_reasons"]) == {"no_lexicon_match", "unknown_layer"}
