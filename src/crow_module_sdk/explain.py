from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict

from .models import Evidence


def evidence_to_markdown(title: str, evidence: Iterable[Evidence]) -> str:
    lines = [f"# {title}", ""]
    for item in evidence:
        lines.append(f"- **{item.kind}**: {item.statement}")
        if item.rule_id:
            lines.append(f"  - Regel: `{item.rule_id}`")
        if item.source_claim_ids:
            claim_refs = ", ".join(f"`{value}`" for value in item.source_claim_ids)
            lines.append("  - Claims: " + claim_refs)
    return "\n".join(lines) + "\n"


def evidence_to_json(evidence: Iterable[Evidence]) -> str:
    payload = [asdict(item) for item in evidence]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
