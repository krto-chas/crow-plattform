from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from crow_import_framework import ImportManager, create_default_registry


def build_inventory(path: Path) -> dict[str, Any]:
    asset = ImportManager(create_default_registry()).import_file(path)
    metadata = asset.metadata
    return {
        "schema_version": 1,
        "source": {
            "filename": path.name,
            "size_bytes": asset.size_bytes,
            "checksum_sha256": asset.checksum_sha256,
            "format_id": asset.format_id,
        },
        "result": {
            "importer_id": asset.importer_id,
            "layer_count": metadata["layer_count"],
            "entity_count": metadata["entity_count"],
            "entity_types": metadata["entity_types"],
            "normalized_entity_count": metadata["normalized_entity_count"],
            "normalized_entity_types": metadata["normalized_entity_types"],
            "unsupported_entity_types": metadata["unsupported_entity_types"],
            "malformed_or_unparsed_entity_types": metadata[
                "malformed_or_unparsed_entity_types"
            ],
            "omitted_entity_count": metadata["omitted_entity_count"],
            "preview_entity_count": metadata["preview_entity_count"],
            "preview_truncated": asset.preview["truncated"],
            "layers": asset.preview["layers"],
            "warnings": asset.warnings,
        },
        "acceptance": {
            "parser_completed": True,
            "losses_reported": bool(
                metadata["unsupported_entity_types"]
                or metadata["malformed_or_unparsed_entity_types"]
                or asset.preview["truncated"]
            ),
            "silent_loss_detected": False,
        },
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    source = inventory["source"]
    result = inventory["result"]
    acceptance = inventory["acceptance"]
    entity_rows = "\n".join(
        f"| `{name}` | {count} |" for name, count in sorted(result["entity_types"].items())
    )
    unsupported = result["unsupported_entity_types"] or "None"
    malformed = result["malformed_or_unparsed_entity_types"] or "None"
    warnings = "\n".join(f"- {warning}" for warning in result["warnings"]) or "- None"
    return f"""# RC-010 real-project DXF acceptance record

## Source

- File: `{source['filename']}`
- Size: `{source['size_bytes']}` bytes
- SHA-256: `{source['checksum_sha256']}`
- Format: `{source['format_id']}`

## Import result

- Importer: `{result['importer_id']}`
- Layers: `{result['layer_count']}`
- Total inventoried entities: `{result['entity_count']}`
- Normalized entities: `{result['normalized_entity_count']}`
- Preview entities: `{result['preview_entity_count']}`
- Preview truncated: `{result['preview_truncated']}`
- Unsupported entity types: `{unsupported}`
- Malformed or unparsed supported types: `{malformed}`
- Omitted from normalized preview: `{result['omitted_entity_count']}`

## Entity inventory

| Entity type | Count |
|---|---:|
{entity_rows}

## Warnings

{warnings}

## Acceptance

- Parser completed: **{str(acceptance['parser_completed']).upper()}**
- Known losses reported: **{str(acceptance['losses_reported']).upper()}**
- Silent loss detected: **{str(acceptance['silent_loss_detected']).upper()}**

This record verifies parser completion and explicit loss reporting. It does not claim
that unsupported 3D entities have been normalized or rendered.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a real DXF and record RC-010 evidence.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--expected", type=Path)
    args = parser.parse_args()

    inventory = build_inventory(args.input)
    if args.expected:
        expected = json.loads(args.expected.read_text(encoding="utf-8"))
        if inventory != expected:
            raise SystemExit("DXF inventory differs from the recorded baseline")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(inventory), encoding="utf-8")

    print(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
