from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from crow_project_dataset import (
    ProjectDataset,
    ReferenceQuality,
    SourceRole,
    inspect_source,
    write_manifest,
)


def _enum(enum_type: type[SourceRole] | type[ReferenceQuality], value: str) -> Any:
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise argparse.ArgumentTypeError(f"expected one of: {allowed}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an evidence-only project dataset manifest.")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument(
        "--source",
        action="append",
        nargs=4,
        metavar=("ID", "ROLE", "QUALITY", "PATH"),
        required=True,
    )
    parser.add_argument("--limitation", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--external-base", type=Path)
    args = parser.parse_args()

    sources = []
    for source_id, role_value, quality_value, path_value in args.source:
        path = Path(path_value)
        sources.append(
            inspect_source(
                path,
                source_id=source_id,
                role=_enum(SourceRole, role_value),
                reference_quality=_enum(ReferenceQuality, quality_value),
                external_base=args.external_base,
            )
        )

    dataset = ProjectDataset(
        dataset_id=args.dataset_id,
        title=args.title,
        description=args.description,
        sources=tuple(sources),
        known_limitations=tuple(args.limitation),
    )
    write_manifest(dataset, args.output)
    print(json.dumps(dataset.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
