from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


@dataclass(frozen=True)
class DuctDimension:
    shape: str
    diameter_mm: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None


@dataclass(frozen=True)
class DuctStringMatch:
    raw_text: str
    medium_code: str
    medium_label: str
    material_code: str | None
    material_label: str | None
    material_subgroup: str | None
    dimension: DuctDimension
    insulation_code: str | None
    insulation_label: str | None
    insulation_subgroup: str | None
    confidence: float
    evidence: Mapping[str, Any]


@dataclass(frozen=True)
class ComponentMatch:
    raw_text: str
    code: str
    number: str | None
    label: str
    category: str
    confidence: float
    alternatives: tuple[str, ...]
    evidence: Mapping[str, Any]


@dataclass(frozen=True)
class LayerMatch:
    layer: str
    profile: str
    semantic: str
    confidence: float
    pattern: str


class VentLexicon:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = payload
        pattern = str(payload["kanal_strang_pattern"]["regex"])
        self._duct_pattern = re.compile(pattern, re.IGNORECASE)
        self._id_pattern = re.compile(str(payload["meta"]["id_pattern"]), re.IGNORECASE)
        self._medium = self._code_map(payload["medium"]["codes"])
        self._materials = self._code_map(payload["kanal_material"]["codes"])
        self._insulation = self._code_map(payload["kanal_isolering"]["codes"])
        self._components = self._component_index(payload["komponenter"])

    @staticmethod
    def _code_map(rows: list[dict[str, Any]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in rows:
            result[str(row["code"]).upper()] = str(row["label"])
            alias = row.get("ascii_alias")
            if alias:
                result[str(alias).upper()] = str(row["label"])
        return result

    @staticmethod
    def _component_index(groups: Mapping[str, Any]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        result: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for category, rows in groups.items():
            if category == "description" or not isinstance(rows, list):
                continue
            for row in rows:
                code = str(row["code"]).upper()
                result.setdefault(code, []).append((category, row))
        return result

    @classmethod
    def default(cls) -> VentLexicon:
        resource = files("crow_vent").joinpath("vent_beteckningar_lexikon.json")
        payload = json.loads(resource.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Vent lexicon root must be an object")
        return cls(payload)

    @property
    def metadata(self) -> Mapping[str, Any]:
        meta = self._payload["meta"]
        if not isinstance(meta, dict):
            raise ValueError("Vent lexicon metadata must be an object")
        return meta

    def parse_duct_string(self, value: str, *, layer: str | None = None) -> DuctStringMatch | None:
        raw = value.strip().upper().replace("×", "X")
        match = self._duct_pattern.fullmatch(raw)
        if match is None:
            return None
        groups = match.groupdict()
        medium_code = groups["medium"].upper()
        material_code = groups.get("material")
        insulation_code = groups.get("isol")
        dim = groups["dim"]
        if "X" in dim.upper():
            width, height = (int(part) for part in dim.upper().split("X", 1))
            dimension = DuctDimension(shape="rectangular", width_mm=width, height_mm=height)
        else:
            dimension = DuctDimension(shape="circular", diameter_mm=int(dim))
        evidence: dict[str, Any] = {
            "rule": "kanal_strang_pattern",
            "matched_text": raw,
        }
        if layer:
            evidence["layer"] = layer
        return DuctStringMatch(
            raw_text=value,
            medium_code=medium_code,
            medium_label=self._medium[medium_code],
            material_code=material_code,
            material_label=self._materials.get(material_code or ""),
            material_subgroup=groups.get("mat_sub"),
            dimension=dimension,
            insulation_code=insulation_code,
            insulation_label=self._insulation.get(insulation_code or ""),
            insulation_subgroup=groups.get("isol_sub"),
            confidence=1.0,
            evidence=evidence,
        )

    def lookup_component(
        self,
        value: str,
        *,
        layer_semantic: str | None = None,
        system_context: str | None = None,
    ) -> ComponentMatch | None:
        raw = value.strip().upper()
        matched = self._id_pattern.fullmatch(raw)
        if matched is None:
            return None
        code = matched.group("code").upper()
        options = self._components.get(code)
        if not options:
            return None
        selected = options[0]
        confidence = 0.95 if len(options) == 1 else 0.55
        alternatives = tuple(str(row["label"]) for _, row in options[1:])
        context = " ".join(part for part in (layer_semantic, system_context) if part).lower()
        if code == "AF" and len(options) > 1:
            if "fläkt" in context or "avluft" in context:
                selected = next(item for item in options if "flaktar" in item[0])
                confidence = 0.9
            elif "avfukt" in context or "qh" in context:
                selected = next(item for item in options if "QG_QH" in item[0])
                confidence = 0.9
        category, row = selected
        return ComponentMatch(
            raw_text=value,
            code=code,
            number=matched.group("num"),
            label=str(row["label"]),
            category=category,
            confidence=confidence,
            alternatives=alternatives,
            evidence={
                "rule": "component_id_pattern",
                "profile": "bip_default",
                "layer_semantic": layer_semantic,
                "system_context": system_context,
                "ambiguous": len(options) > 1,
            },
        )


class LayerProfileEngine:
    def __init__(self, project_layers: Mapping[str, str] | None = None) -> None:
        self._project_layers = {key.upper(): value for key, value in (project_layers or {}).items()}
        self._freehand = {
            "TFT": "tilluft_text",
            "TFA": "tilluftsaggregat",
            "FFT": "frånluft",
            "KANAL": "kanal_oisolerad",
            "KANAL_ISO": "kanal_isolerad",
            "DON": "luftdon",
            "TEXT": "text",
            "MÅTT": "måttsättning",
        }

    def resolve(self, layer: str) -> LayerMatch | None:
        normalized = layer.strip().upper()
        if normalized in self._project_layers:
            return LayerMatch(
                normalized, "project", self._project_layers[normalized], 1.0, normalized
            )
        if re.match(r"^V-?57", normalized):
            return LayerMatch(normalized, "sb11", "ventilation", 0.95, "^V-?57")
        if normalized in self._freehand:
            return LayerMatch(normalized, "freehand", self._freehand[normalized], 0.8, normalized)
        return None
