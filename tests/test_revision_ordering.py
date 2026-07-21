from crow_document_intelligence import normalize_revision


def test_revision_ordering_supports_letters_and_numbers() -> None:
    assert normalize_revision("B") > normalize_revision("A")
    assert normalize_revision("10") > normalize_revision("2")
    assert normalize_revision("2B") > normalize_revision("2A")
    assert normalize_revision(None) < normalize_revision("A")
