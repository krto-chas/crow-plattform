from pathlib import Path

from crow_module_conformance import review_repository


def test_current_repository_passes_architecture_review() -> None:
    root = Path(__file__).parents[1]

    review = review_repository(root, release="0.7.0-alpha.1")

    assert review.passed, review.checks
