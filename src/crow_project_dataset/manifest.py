from __future__ import annotations

import json
from pathlib import Path

from .models import ProjectDataset


def write_manifest(dataset: ProjectDataset, output: Path) -> None:
    dataset.validate()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dataset.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
