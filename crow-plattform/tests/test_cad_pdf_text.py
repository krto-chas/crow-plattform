from crow_document_intelligence.cad_pdf_text import repair_cad_pdf_text


def test_repairs_shifted_mandelblomman_samples() -> None:
    result = repair_cad_pdf_text("(175e +$1'/b**$5( ),71(6663c1*$ XQGHUYnQLQJ Pð")
    assert "ENTRÉ" in result.text
    assert "HANDLÄGGARE" in result.text
    assert "FITNESSSPÅNGA" in result.text
    assert "undervåning" in result.text
    assert "m²" in result.text
    assert result.was_remapped
    assert result.raw.startswith("(175e")


def test_leaves_clean_swedish_text_untouched() -> None:
    clean = "RELATIONSRITNING kv MANDELBLOMMAN 2014-02-12 1:50 TRAPPHUS"
    result = repair_cad_pdf_text(clean)
    assert result.text == clean
    assert not result.was_remapped


def test_mixed_text_repairs_only_garbled_tokens() -> None:
    result = repair_cad_pdf_text("TRAPPHUS (175e+$// DATUM")
    assert result.text.startswith("TRAPPHUS ")
    assert "ENTRÉHALL" in result.text
    assert result.text.endswith(" DATUM")
