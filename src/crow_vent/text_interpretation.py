from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

from .lexicon import ComponentMatch, DuctStringMatch, LayerMatch, LayerProfileEngine, VentLexicon


def _stable_id(source_id: str, raw_text: str, layer: str | None) -> str:
    digest = sha256(f"{source_id}:{layer or ''}:{raw_text}".encode()).hexdigest()[:16]
    return f"vent-text-{digest}"


@dataclass(frozen=True)
class VentTextInterpretation:
    interpretation_id: str
    source_id: str
    raw_text: str
    normalized_text: str
    kind: str
    confidence: float
    status: str
    layer: str | None
    layer_match: LayerMatch | None
    duct: DuctStringMatch | None
    component: ComponentMatch | None
    review_reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VentTextInterpreter:
    """Interpret drawing text without forcing unknown text into a classification."""

    def __init__(
        self,
        *,
        lexicon: VentLexicon | None = None,
        layer_engine: LayerProfileEngine | None = None,
    ) -> None:
        self._lexicon = lexicon or VentLexicon.default()
        self._layers = layer_engine or LayerProfileEngine()

    def interpret(
        self,
        raw_text: str,
        *,
        source_id: str,
        layer: str | None = None,
        system_context: str | None = None,
        entity_handle: str | None = None,
    ) -> VentTextInterpretation:
        normalized = " ".join(raw_text.strip().upper().replace("×", "X").split())
        layer_match = self._layers.resolve(layer) if layer else None
        layer_semantic = layer_match.semantic if layer_match else None
        duct = self._lexicon.parse_duct_string(normalized, layer=layer)
        component = (
            None
            if duct
            else self._lexicon.lookup_component(
                normalized,
                layer_semantic=layer_semantic,
                system_context=system_context,
            )
        )

        review_reasons: list[str] = []
        if duct is not None:
            kind = "duct"
            confidence = duct.confidence
        elif component is not None:
            kind = "component"
            confidence = component.confidence
            if component.evidence.get("ambiguous") and confidence < 0.75:
                review_reasons.append("ambiguous_component_code")
        else:
            kind = "unknown"
            confidence = 0.0
            review_reasons.append("no_lexicon_match")

        if layer and layer_match is None:
            review_reasons.append("unknown_layer")
        if layer_match and kind != "unknown":
            # Layer context strengthens traceability, but never overrides lexical ambiguity.
            confidence = min(1.0, round(confidence + (0.02 * layer_match.confidence), 4))
        status = "interpreted" if kind != "unknown" and confidence >= 0.75 else "needs_review"

        evidence: dict[str, Any] = {
            "source_id": source_id,
            "entity_handle": entity_handle,
            "layer": layer,
            "layer_profile": layer_match.profile if layer_match else None,
            "layer_pattern": layer_match.pattern if layer_match else None,
            "system_context": system_context,
            "lexicon_version": self._lexicon.metadata.get("version"),
        }
        return VentTextInterpretation(
            interpretation_id=_stable_id(source_id, normalized, layer),
            source_id=source_id,
            raw_text=raw_text,
            normalized_text=normalized,
            kind=kind,
            confidence=confidence,
            status=status,
            layer=layer,
            layer_match=layer_match,
            duct=duct,
            component=component,
            review_reasons=tuple(review_reasons),
            evidence=evidence,
        )

    def interpret_many(self, rows: list[dict[str, Any]], *, source_id: str) -> dict[str, Any]:
        interpretations = [
            self.interpret(
                str(row.get("text", "")),
                source_id=source_id,
                layer=str(row["layer"]) if row.get("layer") is not None else None,
                system_context=(
                    str(row["system_context"]) if row.get("system_context") is not None else None
                ),
                entity_handle=(
                    str(row["entity_handle"]) if row.get("entity_handle") is not None else None
                ),
            )
            for row in rows
        ]
        return {
            "schema_version": "crow-vent-text-v0.1",
            "source_id": source_id,
            "interpretation_count": len(interpretations),
            "interpreted_count": sum(item.status == "interpreted" for item in interpretations),
            "review_count": sum(item.status == "needs_review" for item in interpretations),
            "interpretations": [item.to_dict() for item in interpretations],
        }
