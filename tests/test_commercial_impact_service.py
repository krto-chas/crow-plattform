from pathlib import Path

from crow_commercial_impact import (
    CommercialImpactSet,
    load_commercial_impacts,
    load_price_book,
    save_commercial_impacts,
    summarize_commercial_impacts,
    write_price_book_template,
)


def test_price_book_template_loads(tmp_path: Path) -> None:
    path = tmp_path / "price-book.json"
    write_price_book_template(path)

    book = load_price_book(path)

    assert book.id == "crow.pricebook.ventilation.example"
    assert book.currency == "SEK"
    assert len(book.rates) == 1


def test_commercial_result_round_trip(tmp_path: Path) -> None:
    result = CommercialImpactSet(
        project_id="project",
        baseline_id="baseline",
        price_book_id="book",
        currency="SEK",
    )
    path = tmp_path / "commercial.json"

    save_commercial_impacts(result, path)

    assert load_commercial_impacts(path) == result


def test_empty_summary() -> None:
    summary = summarize_commercial_impacts(
        CommercialImpactSet(
            project_id="project",
            baseline_id="baseline",
            price_book_id="book",
            currency="SEK",
        )
    )

    assert summary["total"] == 0.0
    assert summary["items"] == 0
    assert summary["unresolved"] == 0
