from pathlib import Path

from crow_accepted_claims import AcceptedClaimSet, load_accepted_claims, save_accepted_claims


def test_accepted_claims_round_trip(tmp_path: Path) -> None:
    value = AcceptedClaimSet(project_id="project")
    path = tmp_path / "accepted.json"
    save_accepted_claims(value, path)
    assert load_accepted_claims(path) == value
