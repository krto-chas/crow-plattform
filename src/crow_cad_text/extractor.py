from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CadTextEntity:
    entity_type: str
    handle: str | None
    layer: str
    text: str
    x: float | None
    y: float | None
    z: float | None
    rotation: float | None
    height: float | None
    source_id: str
    source_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CadTextExtraction:
    schema_version: str
    source_id: str
    source_format: str
    source_sha256: str
    entity_count: int
    text_entity_count: int
    unsupported_text_entity_count: int
    entities: tuple[CadTextEntity, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "entities": [entity.to_dict() for entity in self.entities],
        }


def _decode_dxf_text(value: str) -> str:
    """Normalize only DXF transport escapes; preserve technical content."""
    return (
        value.replace("\\P", "\n")
        .replace("\\~", " ")
        .replace("%%d", "°")
        .replace("%%D", "°")
        .strip()
    )


def _pairs(lines: list[str]) -> Iterable[tuple[str, str]]:
    for index in range(0, len(lines) - 1, 2):
        yield lines[index].strip(), lines[index + 1].rstrip("\r\n")


class CadTextExtractor:
    """Extract explicit text entities from ASCII DXF without geometric inference."""

    _SUPPORTED = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}

    def extract_path(self, path: Path, *, source_id: str | None = None) -> CadTextExtraction:
        raw = path.read_bytes()
        resolved_source_id = source_id or path.name
        suffix = path.suffix.lower()
        if suffix == ".dwg":
            return CadTextExtraction(
                schema_version="crow-cad-text-v0.1",
                source_id=resolved_source_id,
                source_format="dwg",
                source_sha256=sha256(raw).hexdigest(),
                entity_count=0,
                text_entity_count=0,
                unsupported_text_entity_count=0,
                entities=(),
                warnings=(
                    "Binary DWG text extraction is not implemented; convert to DXF "
                    "or use an explicit DWG adapter.",
                ),
            )
        if suffix != ".dxf":
            raise ValueError(f"Unsupported CAD text source format: {suffix or '<none>'}")
        text = raw.decode("utf-8", errors="replace")
        return self.extract_dxf_text(
            text,
            source_id=resolved_source_id,
            source_sha256=sha256(raw).hexdigest(),
        )

    def extract_dxf_text(
        self,
        text: str,
        *,
        source_id: str,
        source_sha256: str | None = None,
    ) -> CadTextExtraction:
        lines = text.splitlines()
        digest = source_sha256 or sha256(text.encode()).hexdigest()
        entities: list[CadTextEntity] = []
        current: dict[str, Any] | None = None
        entity_count = 0
        unsupported_text_count = 0

        def flush() -> None:
            nonlocal current, unsupported_text_count
            if current is None:
                return
            entity_type = str(current.get("entity_type", ""))
            if entity_type not in self._SUPPORTED:
                current = None
                return
            chunks = current.get("text_chunks", [])
            value = _decode_dxf_text("".join(str(chunk) for chunk in chunks))
            if not value:
                unsupported_text_count += 1
                current = None
                return
            entities.append(
                CadTextEntity(
                    entity_type=entity_type,
                    handle=current.get("handle"),
                    layer=str(current.get("layer", "0")),
                    text=value,
                    x=current.get("x"),
                    y=current.get("y"),
                    z=current.get("z"),
                    rotation=current.get("rotation"),
                    height=current.get("height"),
                    source_id=source_id,
                    source_sha256=digest,
                )
            )
            current = None

        for code, value in _pairs(lines):
            if code == "0":
                flush()
                if value in self._SUPPORTED:
                    entity_count += 1
                    current = {
                        "entity_type": value,
                        "layer": "0",
                        "text_chunks": [],
                    }
                elif value not in {"SECTION", "ENDSEC", "EOF", "TABLE", "ENDTAB"}:
                    entity_count += 1
                continue
            if current is None:
                continue
            if code == "5":
                current["handle"] = value.strip()
            elif code == "8":
                current["layer"] = value.strip()
            elif code in {"1", "3"}:
                current["text_chunks"].append(value)
            elif code in {"10", "20", "30", "40", "50"}:
                try:
                    number = float(value.strip())
                except ValueError:
                    continue
                key = {"10": "x", "20": "y", "30": "z", "40": "height", "50": "rotation"}[code]
                current[key] = number
        flush()

        return CadTextExtraction(
            schema_version="crow-cad-text-v0.1",
            source_id=source_id,
            source_format="dxf",
            source_sha256=digest,
            entity_count=entity_count,
            text_entity_count=len(entities),
            unsupported_text_entity_count=unsupported_text_count,
            entities=tuple(entities),
            warnings=(),
        )
