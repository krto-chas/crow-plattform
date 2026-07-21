from __future__ import annotations

import csv
import json
import re
import struct
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from pypdf import PdfReader

from .base import BasePlugin
from .models import (
    ImportCapability,
    ImportedAsset,
    ImportSource,
    NormalizedLocator,
    NormalizedObservation,
)


def text_observation(value: str, kind: str, locator: dict[str, Any]) -> NormalizedObservation:
    return NormalizedObservation("text", value, NormalizedLocator(kind, locator))


class PdfPlugin(BasePlugin):
    id = "crow.import.pdf"
    format_id = "pdf"
    extensions = (".pdf",)
    media_types = ("application/pdf",)
    priority = 10
    capabilities = (
        ImportCapability.METADATA,
        ImportCapability.TEXT,
        ImportCapability.STRUCTURE,
        ImportCapability.PREVIEW,
    )

    def sniff(self, source: ImportSource, header: bytes) -> bool:
        return header.startswith(b"%PDF-")

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        reader = PdfReader(source.path)
        observations = []
        structure = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            structure.append({"kind": "page", "index": index, "text_length": len(text)})
            if text.strip():
                observations.append(text_observation(text, "pdf_page", {"page": index}))
        return self.build(
            source,
            metadata={"page_count": len(reader.pages)},
            structure=structure,
            observations=observations,
        )


class ImagePlugin(BasePlugin):
    id = "crow.import.image"
    format_id = "image"
    extensions = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp")
    priority = 20
    capabilities = (ImportCapability.METADATA, ImportCapability.PREVIEW)

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        data = source.path.read_bytes()[:32]
        metadata: dict[str, Any] = {}
        if data.startswith(b"\x89PNG") and len(data) >= 24:
            metadata["width"], metadata["height"] = struct.unpack(">II", data[16:24])
        return self.build(
            source, metadata=metadata, warnings=["OCR ingår inte i den generiska bildimportören."]
        )


class JsonPlugin(BasePlugin):
    id = "crow.import.json"
    format_id = "json"
    extensions = (".json", ".geojson")
    priority = 30
    capabilities = (ImportCapability.METADATA, ImportCapability.TEXT, ImportCapability.STRUCTURE)

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        payload = json.loads(source.path.read_text(encoding="utf-8-sig"))
        structure = [{"kind": "root", "type": type(payload).__name__}]
        observations = [
            text_observation(json.dumps(payload, ensure_ascii=False), "json", {"path": "$"})
        ]
        return self.build(
            source,
            metadata={"root_type": type(payload).__name__},
            structure=structure,
            observations=observations,
        )


class CsvPlugin(BasePlugin):
    id = "crow.import.csv"
    format_id = "csv"
    extensions = (".csv",)
    priority = 30
    capabilities = (ImportCapability.METADATA, ImportCapability.TEXT, ImportCapability.STRUCTURE)

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        with source.path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        observations = [
            text_observation(" | ".join(row), "csv_row", {"row": i})
            for i, row in enumerate(rows, 1)
        ]
        return self.build(
            source,
            metadata={
                "row_count": len(rows),
                "column_count": max((len(r) for r in rows), default=0),
            },
            observations=observations,
        )


class DocxPlugin(BasePlugin):
    id = "crow.import.docx"
    format_id = "docx"
    extensions = (".docx",)
    priority = 30
    capabilities = (ImportCapability.METADATA, ImportCapability.TEXT, ImportCapability.STRUCTURE)

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        with zipfile.ZipFile(source.path) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        paragraphs = []
        for paragraph in root.iter():
            if paragraph.tag.endswith("}p"):
                text = "".join(
                    node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")
                )
                if text:
                    paragraphs.append(text)
        obs = [
            text_observation(text, "docx_paragraph", {"paragraph": i})
            for i, text in enumerate(paragraphs, 1)
        ]
        return self.build(source, metadata={"paragraph_count": len(paragraphs)}, observations=obs)


class XlsxPlugin(BasePlugin):
    id = "crow.import.xlsx"
    format_id = "xlsx"
    extensions = (".xlsx",)
    priority = 30
    capabilities = (ImportCapability.METADATA, ImportCapability.TEXT, ImportCapability.STRUCTURE)

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        with zipfile.ZipFile(source.path) as archive:
            names = archive.namelist()
            sheet_names = [
                name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
            ]
            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(t.text or "" for t in si.iter() if t.tag.endswith("}t"))
                    for si in root
                    if si.tag.endswith("}si")
                ]
            observations = []
            for sheet_index, name in enumerate(sorted(sheet_names), 1):
                root = ET.fromstring(archive.read(name))
                for cell in root.iter():
                    if not cell.tag.endswith("}c"):
                        continue
                    ref = cell.attrib.get("r", "")
                    value_node = next((n for n in cell if n.tag.endswith("}v")), None)
                    if value_node is None or value_node.text is None:
                        continue
                    value = value_node.text
                    if cell.attrib.get("t") == "s" and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    observations.append(
                        text_observation(value, "xlsx_cell", {"sheet": sheet_index, "cell": ref})
                    )
        return self.build(
            source,
            metadata={"sheet_count": len(sheet_names), "cell_count": len(observations)},
            structure=[{"kind": "sheet", "index": i} for i in range(1, len(sheet_names) + 1)],
            observations=observations,
        )


class IfcPlugin(BasePlugin):
    id = "crow.import.ifc"
    format_id = "ifc"
    extensions = (".ifc",)
    priority = 15
    capabilities = (
        ImportCapability.METADATA,
        ImportCapability.TEXT,
        ImportCapability.STRUCTURE,
        ImportCapability.PREVIEW,
        ImportCapability.GEOMETRY_3D,
    )

    def sniff(self, source: ImportSource, header: bytes) -> bool:
        return b"ISO-10303-21" in header

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        text = source.path.read_text(encoding="utf-8", errors="replace")
        schema = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text, re.I)
        rows = re.findall(r"^(#\d+)\s*=\s*(IFC[A-Z0-9_]+)\s*\((.*)\);\s*$", text, re.I | re.M)
        counts: dict[str, int] = {}
        instances: list[dict[str, Any]] = []
        spatial = {"IFCPROJECT", "IFCSITE", "IFCBUILDING", "IFCBUILDINGSTOREY", "IFCSPACE"}
        for entity_id, entity_type, args in rows:
            key = entity_type.upper()
            counts[key] = counts.get(key, 0) + 1
            quoted = re.findall(r"'([^']*)'", args)
            name = next(
                (value for value in quoted[1:] if value and value != "$"),
                quoted[0] if quoted else entity_id,
            )
            instances.append(
                {"id": entity_id, "type": key, "name": name[:160], "spatial": key in spatial}
            )
        structure = [
            {"kind": "ifc_entity_type", "name": key, "count": value}
            for key, value in sorted(counts.items())
        ]
        structure.extend({"kind": "ifc_spatial", **item} for item in instances if item["spatial"])
        observations = [
            NormalizedObservation(
                "ifc_entity",
                {"type": key, "count": value},
                NormalizedLocator("ifc_type", {"entity_type": key}),
            )
            for key, value in sorted(counts.items())
        ]
        preview = {
            "kind": "ifc_model_tree",
            "schema": schema.group(1) if schema else None,
            "instances": instances[:5000],
            "entity_types": [
                {"type": key, "count": value}
                for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            ],
        }
        return self.build(
            source,
            metadata={
                "schema": schema.group(1) if schema else None,
                "entity_count": len(rows),
                "entity_type_count": len(counts),
                "spatial_count": sum(1 for item in instances if item["spatial"]),
            },
            structure=structure,
            observations=observations,
            preview=preview,
            warnings=[
                "Full IFC-geometri kräver en separat tesselleringsadapter; Workbench visar "
                "nu modellträd, spatial struktur och entitetsfördelning."
            ],
        )


class DxfPlugin(BasePlugin):
    id = "crow.import.dxf"
    format_id = "dxf"
    extensions = (".dxf",)
    priority = 15
    capabilities = (
        ImportCapability.METADATA,
        ImportCapability.TEXT,
        ImportCapability.STRUCTURE,
        ImportCapability.PREVIEW,
        ImportCapability.GEOMETRY_2D,
    )

    _PREVIEWABLE_TYPES = {
        "LINE",
        "CIRCLE",
        "LWPOLYLINE",
        "POLYLINE",
        "ARC",
        "TEXT",
        "MTEXT",
        "INSERT",
    }
    _NON_GRAPHICAL_TYPES = {"BLOCK", "ENDBLK"}

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        lines = source.path.read_text(encoding="utf-8", errors="replace").splitlines()
        pairs = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
        layers: dict[str, int] = {}
        entities: dict[str, int] = {}
        geometry: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        def flush() -> None:
            nonlocal current
            if not current:
                return
            kind = str(current.get("type", ""))
            if kind == "LINE" and all(key in current for key in ("x1", "y1", "x2", "y2")):
                geometry.append(current)
            elif kind == "CIRCLE" and all(key in current for key in ("cx", "cy", "r")):
                geometry.append(current)
            elif kind in {"LWPOLYLINE", "POLYLINE"} and current.get("points"):
                geometry.append(current)
            elif kind == "ARC" and all(
                key in current for key in ("cx", "cy", "r", "start_angle", "end_angle")
            ):
                geometry.append(current)
            elif kind in {"TEXT", "MTEXT"} and all(key in current for key in ("x", "y", "text")):
                geometry.append(current)
            elif kind == "INSERT" and all(key in current for key in ("x", "y", "name")):
                geometry.append(current)
            current = None

        for code, value in pairs:
            if code == "0":
                flush()
                if value not in {"SECTION", "ENDSEC", "EOF", "TABLE", "ENDTAB", "VERTEX", "SEQEND"}:
                    entities[value] = entities.get(value, 0) + 1
                    current = {"type": value, "layer": "0", "points": []}
                continue
            if current is None:
                continue
            if code == "8":
                current["layer"] = value
                layers[value] = layers.get(value, 0) + 1
            kind = str(current.get("type"))
            if kind in {"TEXT", "MTEXT"} and code in {"1", "3"}:
                current["text"] = str(current.get("text", "")) + value
                continue
            if kind == "INSERT" and code == "2":
                current["name"] = value
                continue
            if code == "5":
                current["handle"] = value
                continue
            try:
                number = float(value)
            except ValueError:
                continue
            if kind == "LINE":
                key = {"10": "x1", "20": "y1", "11": "x2", "21": "y2"}.get(code)
                if key:
                    current[key] = number
            elif kind == "CIRCLE":
                key = {"10": "cx", "20": "cy", "40": "r"}.get(code)
                if key:
                    current[key] = number
            elif kind in {"LWPOLYLINE", "POLYLINE"}:
                if code == "10":
                    current["points"].append([number, None])
                elif code == "20" and current["points"] and current["points"][-1][1] is None:
                    current["points"][-1][1] = number
                elif code == "70":
                    current["closed"] = bool(int(number) & 1)
            elif kind == "ARC":
                key = {
                    "10": "cx",
                    "20": "cy",
                    "40": "r",
                    "50": "start_angle",
                    "51": "end_angle",
                }.get(code)
                if key:
                    current[key] = number
            elif kind in {"TEXT", "MTEXT", "INSERT"}:
                key = {
                    "10": "x",
                    "20": "y",
                    "40": "height",
                    "41": "scale_x",
                    "42": "scale_y",
                    "50": "rotation",
                }.get(code)
                if key:
                    current[key] = number
        flush()

        clean_geometry = []
        for item in geometry[:20000]:
            if "points" in item:
                item = {
                    **item,
                    "points": [point for point in item["points"] if point[1] is not None],
                }
            clean_geometry.append(item)

        parsed_types: dict[str, int] = {}
        for item in geometry:
            entity_type = str(item["type"])
            parsed_types[entity_type] = parsed_types.get(entity_type, 0) + 1

        unsupported_types = {
            key: value
            for key, value in entities.items()
            if key not in self._PREVIEWABLE_TYPES and key not in self._NON_GRAPHICAL_TYPES
        }
        malformed_or_unparsed = {
            key: count - parsed_types.get(key, 0)
            for key, count in entities.items()
            if key in self._PREVIEWABLE_TYPES and count > parsed_types.get(key, 0)
        }
        omitted_types = {
            **unsupported_types,
            **malformed_or_unparsed,
        }
        omitted_count = sum(omitted_types.values())

        warnings: list[str] = []
        if unsupported_types:
            detail = ", ".join(f"{key}={value}" for key, value in sorted(unsupported_types.items()))
            warnings.append(
                "DXF contains entity types without preview support; they were inventoried but "
                f"not converted to normalized preview geometry: {detail}."
            )
        if malformed_or_unparsed:
            detail = ", ".join(
                f"{key}={value}" for key, value in sorted(malformed_or_unparsed.items())
            )
            warnings.append(
                "DXF contains supported entity types that could not be normalized because "
                f"required fields were missing or unsupported encoding was used: {detail}."
            )
        if len(geometry) > len(clean_geometry):
            warnings.append(
                "Preview was truncated at "
                f"{len(clean_geometry)} of {len(geometry)} normalized entities."
            )

        structure = [
            {"kind": "layer", "name": key, "entity_count": value}
            for key, value in sorted(layers.items())
        ]
        obs = [
            NormalizedObservation(
                "cad_layer",
                {"name": key, "entity_count": value},
                NormalizedLocator("dxf_layer", {"layer": key}),
            )
            for key, value in sorted(layers.items())
        ]
        preview = {
            "kind": "dxf_2d",
            "geometry": clean_geometry,
            "layers": sorted(layers),
            "truncated": len(geometry) > len(clean_geometry),
        }
        return self.build(
            source,
            metadata={
                "layer_count": len(layers),
                "entity_count": sum(entities.values()),
                "entity_types": entities,
                "normalized_entity_count": len(geometry),
                "normalized_entity_types": parsed_types,
                "unsupported_entity_types": unsupported_types,
                "malformed_or_unparsed_entity_types": malformed_or_unparsed,
                "omitted_entity_count": omitted_count,
                "preview_entity_count": len(clean_geometry),
            },
            structure=structure,
            observations=obs,
            preview=preview,
            warnings=warnings,
        )


class DwgPlugin(BasePlugin):
    id = "crow.import.dwg"
    format_id = "dwg"
    extensions = (".dwg",)
    priority = 15
    capabilities = (ImportCapability.METADATA,)

    def sniff(self, source: ImportSource, header: bytes) -> bool:
        return header.startswith(b"AC10")

    def import_asset(self, source: ImportSource) -> ImportedAsset:
        header = source.path.read_bytes()[:6].decode("ascii", errors="replace")
        return self.build(
            source,
            metadata={"dwg_version_code": header},
            warnings=[
                "DWG är binärt och kräver en licensierad eller extern "
                "konverteringsadapter för geometri och lager. "
                "Filen är registrerad utan semantisk tolkning."
            ],
        )


DEFAULT_PLUGINS = (
    PdfPlugin,
    IfcPlugin,
    DxfPlugin,
    DwgPlugin,
    ImagePlugin,
    JsonPlugin,
    CsvPlugin,
    DocxPlugin,
    XlsxPlugin,
)
