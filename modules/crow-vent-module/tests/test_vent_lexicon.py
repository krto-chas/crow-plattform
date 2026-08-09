from crow_vent.lexicon import LayerProfileEngine, VentLexicon


def test_parse_complete_rectangular_duct_string() -> None:
    match = VentLexicon.default().parse_duct_string("T13-250x400-V1", layer="V-57--")
    assert match is not None
    assert match.medium_label == "Tilluft"
    assert match.material_code == "1"
    assert match.material_subgroup == "3"
    assert match.dimension.shape == "rectangular"
    assert match.dimension.width_mm == 250
    assert match.dimension.height_mm == 400
    assert match.insulation_label == "Värmeisolering"
    assert match.insulation_subgroup == "1"
    assert match.evidence["layer"] == "V-57--"


def test_parse_circular_duct_without_optional_parts() -> None:
    match = VentLexicon.default().parse_duct_string("F-315")
    assert match is not None
    assert match.medium_label == "Frånluft"
    assert match.dimension.shape == "circular"
    assert match.dimension.diameter_mm == 315
    assert match.material_code is None
    assert match.insulation_code is None


def test_component_lookup_and_af_context_resolution() -> None:
    lexicon = VentLexicon.default()
    fan = lexicon.lookup_component("AF01", layer_semantic="avluftsfläkt")
    dryer = lexicon.lookup_component("AF2", system_context="QH avfuktare")
    unknown_context = lexicon.lookup_component("AF3")
    assert fan is not None and fan.label.startswith("Avluftsfläkt") and fan.confidence == 0.9
    assert dryer is not None and dryer.label.startswith("Avfuktare") and dryer.confidence == 0.9
    assert unknown_context is not None and unknown_context.confidence == 0.55
    assert unknown_context.evidence["ambiguous"] is True


def test_layer_profile_fallback_order() -> None:
    engine = LayerProfileEngine({"KANAL": "projektspecifik_kanal"})
    project = engine.resolve("kanal")
    sb11 = engine.resolve("V-57--")
    freehand = LayerProfileEngine().resolve("KANAL_ISO")
    assert project is not None and project.profile == "project" and project.confidence == 1.0
    assert sb11 is not None and sb11.profile == "sb11"
    assert freehand is not None and freehand.profile == "freehand"
    assert engine.resolve("A-40-VÄGG") is None


def test_invalid_text_is_not_forced_into_a_match() -> None:
    lexicon = VentLexicon.default()
    assert lexicon.parse_duct_string("KANAL 250") is None
    assert lexicon.lookup_component("HELT OKÄND") is None
