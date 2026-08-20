from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, cast

from fastapi import HTTPException

from crow_geometry_framework import consolidate_observations, geometry_from_import_manifest
from crow_takeoff_consolidation import (
    PriceBook,
    PriceBookEntry,
    SourceTakeoff,
    consolidate_takeoffs,
    price_consolidated_takeoff,
    takeoff_from_geometry,
    takeoff_from_table,
    takeoff_from_text,
)
from crow_vent import build_vent_model, component_registry, quantity_takeoff_csv
from crow_vent.lexicon import VentLexicon


class VentProjectRuntime:
    """Vent-owned access to project geometry, takeoff and review data."""

    def __init__(self, data_root: Path) -> None:
        self._projects_root = data_root / "projects"
        self._lexicon = VentLexicon.default()

    def registry(self) -> dict[str, Any]:
        items = [asdict(item) for item in component_registry()]
        return {
            "version": "crow-vent-registry-v0.2",
            "count": len(items),
            "components": items,
        }

    def model(
        self,
        project_id: str,
        checksum: str,
        *,
        tolerance: float = 0.001,
        association_radius: float = 100.0,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        if association_radius < 0:
            raise HTTPException(status_code=400, detail="Kopplingsradien får inte vara negativ")

        asset = self.imported_asset(project_id, checksum)
        state = self._geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        candidates = consolidate_observations(
            document,
            tolerance=tolerance,
            association_radius=association_radius,
            layers=[layer] if layer else None,
            visible_only=visible_only,
        )
        return cast(dict[str, Any], _jsonable(build_vent_model(candidates)))

    def takeoff(self, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
        takeoffs: list[SourceTakeoff] = []
        geometry_checksums = cast(list[object], body.get("geometry_checksums") or [])
        for checksum in geometry_checksums:
            model = self.model(project_id, str(checksum))
            takeoffs.append(
                takeoff_from_geometry(
                    model["quantity_takeoff"], source_id=f"dxf:{str(checksum)[:12]}"
                )
            )

        table_rows = cast(list[list[str]], body.get("table_rows") or [])
        if table_rows:
            takeoffs.append(
                takeoff_from_table(
                    table_rows,
                    source_id="tabell:mangdforteckning",
                    lexicon=self._lexicon,
                )
            )

        text_segments = cast(list[str], body.get("text_segments") or [])
        if text_segments:
            takeoffs.append(
                takeoff_from_text(
                    text_segments,
                    source_id="text:beskrivning",
                    lexicon=self._lexicon,
                )
            )

        if not takeoffs:
            raise HTTPException(
                status_code=422,
                detail="Minst en källa krävs: geometri, tabellrader eller text.",
            )

        tolerance = float(body.get("length_tolerance") or 0.02)
        consolidated = consolidate_takeoffs(takeoffs, length_tolerance=tolerance)

        priced: dict[str, Any] | None = None
        raw_book = body.get("price_book")
        if isinstance(raw_book, dict):
            entries = cast(list[dict[str, Any]], raw_book.get("entries", []))
            book = PriceBook(
                price_book_id=str(raw_book.get("price_book_id", "prisbok")),
                currency=str(raw_book.get("currency", "SEK")),
                labour_rate_per_hour=float(raw_book.get("labour_rate_per_hour", 0.0)),
                entries=tuple(
                    PriceBookEntry(
                        kind=str(entry["kind"]),
                        code=str(entry["code"]),
                        dimension=str(entry.get("dimension", "*")),
                        unit=str(entry["unit"]),
                        material_unit_price=float(entry.get("material_unit_price", 0.0)),
                        labour_hours_per_unit=float(entry.get("labour_hours_per_unit", 0.0)),
                        article=entry.get("article"),
                    )
                    for entry in entries
                ),
            )
            priced = price_consolidated_takeoff(consolidated, book)

        return {"consolidated": consolidated, "priced": priced}

    def quantity_csv(self, project_id: str, checksum: str) -> str:
        model = self.model(project_id, checksum)
        return "\ufeff" + quantity_takeoff_csv(model["quantity_takeoff"])

    def review(self, project_id: str, checksum: str) -> dict[str, Any]:
        model = self.model(project_id, checksum)
        classifications = cast(list[dict[str, Any]], model.get("classifications", []))
        items = [item for item in classifications if item["status"] == "needs_review"]
        return {"count": len(items), "items": items}

    def imported_asset(self, project_id: str, checksum: str) -> dict[str, Any]:
        safe_project_id = _safe_project_id(project_id)
        safe_checksum = _safe_checksum(checksum)
        self._require_project(safe_project_id)
        manifest = self._projects_root / safe_project_id / "imports" / f"{safe_checksum}.json"
        if not manifest.exists():
            raise HTTPException(status_code=404, detail="Importerad tillgång finns inte")
        return _load_json_object(manifest, detail="Ogiltigt importmanifest")

    def _require_project(self, project_id: str) -> Path:
        path = self._projects_root / project_id / "crow-project.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Projektet finns inte")
        return path

    def _geometry_state(self, project_id: str, checksum: str) -> dict[str, Any]:
        path = (
            self._projects_root
            / _safe_project_id(project_id)
            / "geometry-state"
            / f"{_safe_checksum(checksum)}.json"
        )
        if not path.exists():
            return {"layers": {}}
        return _load_json_object(path, detail="Ogiltigt geometriläge")


def _safe_project_id(project_id: str) -> str:
    if not project_id or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in project_id.lower()
    ):
        raise HTTPException(status_code=400, detail="Ogiltigt projekt-id")
    return project_id.lower()


def _safe_checksum(checksum: str) -> str:
    if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum.lower()):
        raise HTTPException(status_code=400, detail="Ogiltig checksumma")
    return checksum.lower()


def _load_json_object(path: Path, *, detail: str) -> dict[str, Any]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=500, detail=detail) from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail=detail)
    return cast(dict[str, Any], payload)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
