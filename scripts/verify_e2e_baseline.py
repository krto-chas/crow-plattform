from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from crow_module_sdk import AuthorityPolicy, AuthorityRule, Claim, Provenance, RoundingPolicy
from crow_module_sdk.pipeline import run_claim_to_estimate

BASELINE_ID = "claim-to-estimate-reference-v1"


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda pair: str(pair[0]))
        return {str(key): _json_value(item) for key, item in ordered}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def build_result() -> dict[str, Any]:
    claims = (
        Claim(
            id="drawing-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("160"),
            unit="mm",
            provenance=Provenance("DRAWING", "B", 4, "Section A-A"),
        ),
        Claim(
            id="spec-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("125"),
            unit="mm",
            provenance=Provenance("SPEC", "B", 7, "3.2"),
        ),
    )
    policy = AuthorityPolicy(
        id="authority-2026",
        confirmed=True,
        rules=(
            AuthorityRule(
                "AF-1.3",
                "SPEC",
                "DRAWING",
                "Beskrivning gäller före ritning.",
            ),
        ),
    )
    result = run_claim_to_estimate(
        claims,
        policy,
        base_unit_cost=Decimal("500"),
        alternative_unit_cost=Decimal("684.20"),
        quantity=Decimal("100"),
        rounding=RoundingPolicy(),
    )
    payload = {
        "baseline_id": BASELINE_ID,
        "accepted_claim_id": result.accepted_claim.claim.id if result.accepted_claim else None,
        "conflict_id": result.conflict.id,
        "authority_decision_id": result.authority_decision.id,
        "technical_delta_id": result.technical_delta.id if result.technical_delta else None,
        "technical_absolute_delta": (
            result.technical_delta.absolute_delta if result.technical_delta else None
        ),
        "commercial_impact_id": result.commercial_impact.id if result.commercial_impact else None,
        "commercial_delta_amount": (
            result.commercial_impact.delta_amount if result.commercial_impact else None
        ),
        "ata_opportunity_id": result.ata_opportunity.id if result.ata_opportunity else None,
        "estimate_line": result.estimate_line,
        "client_question": result.client_question,
        "reservation": result.reservation,
        "evidence_ids": tuple(item.id for item in result.evidence),
    }
    normalized = _json_value(payload)
    canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    normalized["result_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return normalized


def verify(expected_path: Path) -> dict[str, Any]:
    first = build_result()
    second = build_result()
    if first != second:
        raise SystemExit("RC-009 FAIL: two identical executions produced different results")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if first != expected:
        print(json.dumps({"expected": expected, "actual": first}, ensure_ascii=False, indent=2))
        raise SystemExit("RC-009 FAIL: result differs from committed baseline")
    return first


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Crow's deterministic RC-009 baseline")
    parser.add_argument(
        "--expected",
        type=Path,
        default=Path("evidence/rc-009/claim_to_estimate_reference_v1.json"),
    )
    parser.add_argument("--write", action="store_true", help="Write the current result as baseline")
    args = parser.parse_args()

    result = build_result()
    if args.write:
        args.expected.parent.mkdir(parents=True, exist_ok=True)
        args.expected.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {args.expected}")
        return

    verified = verify(args.expected)
    print(
        json.dumps(
            {
                "criterion": "RC-009",
                "status": "pass",
                "baseline_id": verified["baseline_id"],
                "result_sha256": verified["result_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
