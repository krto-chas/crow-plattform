from pathlib import Path

from crow_authority import (
    AuthorityResolution,
    ab04_framework,
    load_resolution,
    save_resolution,
)


def test_resolution_round_trip(tmp_path: Path) -> None:
    resolution = AuthorityResolution(
        project_id="project",
        framework=ab04_framework(),
        decisions=(),
    )
    path = tmp_path / "resolution.json"

    save_resolution(resolution, path)

    assert load_resolution(path) == resolution
