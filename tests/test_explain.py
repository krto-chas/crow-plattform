import json

from crow_module_sdk import Evidence
from crow_module_sdk.explain import evidence_to_json, evidence_to_markdown


def test_explain_outputs_are_deterministic() -> None:
    evidence = (
        Evidence("e1", "observation", "Ritning visar 160.", ("c1",)),
        Evidence("e2", "rule", "Beskrivning gäller före ritning.", ("c1", "c2"), "AF-1.3"),
    )
    markdown = evidence_to_markdown("Förklaring", evidence)
    payload = json.loads(evidence_to_json(evidence))

    assert markdown.startswith("# Förklaring")
    assert "AF-1.3" in markdown
    assert payload[1]["rule_id"] == "AF-1.3"
