from pathlib import Path

from crow_module_conformance import review_repository


def test_sprint_a_repository_passes_architecture_review() -> None:
    root = Path(__file__).parents[1]

    review = review_repository(root, release="0.5.0")

    assert review.passed, review.checks
