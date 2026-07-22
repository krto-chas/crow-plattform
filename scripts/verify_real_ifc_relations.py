from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from crow_ifc_relations import IfcRelationExtractor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ifc", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    extraction = IfcRelationExtractor().extract_path(args.ifc)
    payload = {
        "schema": "crow-rc-011-ifc-explicit-relations-v0.1",
        "source_id": extraction.source_id,
        "source_checksum_sha256": extraction.source_checksum_sha256,
        "relation_entity_counts": extraction.relation_entity_counts,
        "supported_relation_entity_counts": extraction.supported_relation_entity_counts,
        "unsupported_relation_entity_counts": extraction.unsupported_relation_entity_counts,
        "malformed_supported_entities": list(extraction.malformed_supported_entities),
        "canonical_relation_counts": dict(
            sorted(Counter(item.relation_type.value for item in extraction.relations).items())
        ),
        "explicit_relations_extracted": len(extraction.relations),
        "metadata": extraction.metadata,
        "acceptance": {
            "parser_completed": True,
            "supported_relationships_extracted": len(extraction.relations) > 0,
            "unsupported_relationships_reported": bool(
                extraction.unsupported_relation_entity_counts
            ),
            "malformed_supported_relationships": len(
                extraction.malformed_supported_entities
            ),
            "inference_performed": False,
        },
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
