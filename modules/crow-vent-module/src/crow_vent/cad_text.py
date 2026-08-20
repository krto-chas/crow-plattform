from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from crow_cad_text import CadTextExtraction, CadTextExtractor
from crow_canonical import CanonicalObject

from .canonical import VentCanonicalAdapter
from .text_interpretation import VentTextInterpretation, VentTextInterpreter


@dataclass(frozen=True)
class CadVentTextResult:
    extraction: CadTextExtraction
    interpretations: tuple[VentTextInterpretation, ...]
    canonical_objects: tuple[CanonicalObject, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "crow-cad-vent-text-v0.1",
            "extraction": self.extraction.to_dict(),
            "interpretation_count": len(self.interpretations),
            "canonical_object_count": len(self.canonical_objects),
            "interpretations": [item.to_dict() for item in self.interpretations],
            "canonical_objects": [asdict(item) for item in self.canonical_objects],
            "automatic_object_merge_performed": False,
            "geometric_association_performed": False,
            "inference_performed": False,
        }


class CadVentTextPipeline:
    """Extract, interpret and adapt explicit CAD text for the Vent domain."""

    def __init__(
        self,
        *,
        extractor: CadTextExtractor | None = None,
        interpreter: VentTextInterpreter | None = None,
        adapter: VentCanonicalAdapter | None = None,
    ) -> None:
        self._extractor = extractor or CadTextExtractor()
        self._interpreter = interpreter or VentTextInterpreter()
        self._adapter = adapter or VentCanonicalAdapter()

    def run_path(self, path: Path, *, source_id: str | None = None) -> CadVentTextResult:
        extraction = self._extractor.extract_path(path, source_id=source_id)
        return self._interpret(extraction)

    def run_dxf_text(self, text: str, *, source_id: str) -> CadVentTextResult:
        return self._interpret(self._extractor.extract_dxf_text(text, source_id=source_id))

    def _interpret(self, extraction: CadTextExtraction) -> CadVentTextResult:
        interpretations = tuple(
            self._interpreter.interpret(
                entity.text,
                source_id=entity.source_id,
                layer=entity.layer,
                entity_handle=entity.handle,
            )
            for entity in extraction.entities
        )
        canonical = tuple(
            item
            for interpretation in interpretations
            if (item := self._adapter.convert(interpretation)) is not None
        )
        return CadVentTextResult(
            extraction=extraction,
            interpretations=interpretations,
            canonical_objects=canonical,
        )
