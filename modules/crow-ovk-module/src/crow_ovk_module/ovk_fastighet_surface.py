"""Yta för fastighetsentiteten och besiktningsmannaregistret (pass 102).

Skapas med fördel från kontoret innan besiktning, men kan även fyllas i fält.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from crow_ovk_fastighet import (
    BesiktningsmanRepository,
    FastighetRepository,
    besiktningsman_from_payload,
    besiktningsman_to_payload,
    fastighet_from_payload,
    fastighet_to_payload,
)
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

_NO_CACHE = {"Cache-Control": "no-cache"}


def _asset_text(name: str) -> str:
    return (files("crow_ovk_module") / "assets" / name).read_text(encoding="utf-8")


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_JSON", "message": str(exc)}
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_JSON", "message": "payload must be an object"},
        )
    return payload


def ovk_fastighet_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    fastighet_repository = FastighetRepository(data_root)
    besiktningsman_repository = BesiktningsmanRepository(data_root)

    @router.get("/ovk/fastighet", response_class=HTMLResponse)
    def fastighet_page() -> HTMLResponse:
        return HTMLResponse(_asset_text("fastighet.html"), headers=_NO_CACHE)

    @router.get("/ovk/fastighet/app.js", response_model=None)
    def fastighet_app() -> Response:
        return Response(
            _asset_text("fastighet.js"),
            media_type="application/javascript",
            headers=_NO_CACHE,
        )

    @router.put("/api/ovk/projects/{project_id}/fastighet/{fastighet_id}", response_model=None)
    async def save_fastighet(
        project_id: str, fastighet_id: str, request: Request
    ) -> dict[str, Any]:
        payload = await _json_body(request)
        payload["project_id"] = project_id
        payload["fastighet_id"] = fastighet_id
        payload["updated_at"] = datetime.now(UTC).isoformat()
        try:
            fastighet = fastighet_from_payload(payload)
            fastighet_repository.save(fastighet)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_FASTIGHET", "message": str(exc)}
            ) from exc
        return {"saved": True, "fastighet": fastighet_to_payload(fastighet)}

    @router.get("/api/ovk/projects/{project_id}/fastighet/{fastighet_id}", response_model=None)
    def get_fastighet(project_id: str, fastighet_id: str) -> dict[str, Any]:
        try:
            fastighet = fastighet_repository.load(project_id, fastighet_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "FASTIGHET_NOT_FOUND"}) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_IDENTIFIER", "message": str(exc)}
            ) from exc
        return fastighet_to_payload(fastighet)

    @router.get("/api/ovk/projects/{project_id}/fastighet", response_model=None)
    def list_fastighet(project_id: str) -> dict[str, Any]:
        try:
            items = fastighet_repository.list(project_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_IDENTIFIER", "message": str(exc)}
            ) from exc
        return {"fastigheter": [fastighet_to_payload(item) for item in items]}

    def structure_path(project_id: str, fastighet_id: str, building_id: str) -> Path:
        try:
            property_record = fastighet_repository.load(project_id, fastighet_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "FASTIGHET_NOT_FOUND"}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_IDENTIFIER"}) from exc
        if not re.fullmatch(r"[A-Za-z0-9_-]+", building_id):
            raise HTTPException(status_code=422, detail={"code": "INVALID_IDENTIFIER"})
        if not any(b.byggnad_id == building_id for b in property_record.byggnader):
            raise HTTPException(status_code=404, detail={"code": "BYGGNAD_NOT_FOUND"})
        return (
            data_root
            / "projects"
            / project_id
            / "ovk-structure"
            / fastighet_id
            / f"{building_id}.json"
        )

    @router.get(
        "/api/ovk/projects/{project_id}/fastighet/{fastighet_id}/byggnad/{building_id}/struktur",
        response_model=None,
    )
    def get_structure(project_id: str, fastighet_id: str, building_id: str) -> dict[str, Any]:
        path = structure_path(project_id, fastighet_id, building_id)
        if not path.exists():
            return {"units": [], "systems": [], "technical_spaces": []}
        result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return result

    @router.put(
        "/api/ovk/projects/{project_id}/fastighet/{fastighet_id}/byggnad/{building_id}/struktur",
        response_model=None,
    )
    async def save_structure(
        project_id: str, fastighet_id: str, building_id: str, request: Request
    ) -> dict[str, Any]:
        path = structure_path(project_id, fastighet_id, building_id)
        payload = await _json_body(request)
        try:
            structure = _validate_structure(payload)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_OVK_STRUCTURE", "message": str(exc)}
            ) from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            json.dump(structure, temporary, ensure_ascii=False, indent=2)
        try:
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)
        return structure

    @router.put("/api/ovk/registry/besiktningsman/{besiktningsman_id}", response_model=None)
    async def save_besiktningsman(besiktningsman_id: str, request: Request) -> dict[str, Any]:
        payload = await _json_body(request)
        payload["besiktningsman_id"] = besiktningsman_id
        try:
            person = besiktningsman_from_payload(payload)
            besiktningsman_repository.save(person)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_BESIKTNINGSMAN", "message": str(exc)},
            ) from exc
        return {"saved": True, "besiktningsman": besiktningsman_to_payload(person)}

    @router.get("/api/ovk/registry/besiktningsman/{besiktningsman_id}", response_model=None)
    def get_besiktningsman(besiktningsman_id: str) -> dict[str, Any]:
        try:
            person = besiktningsman_repository.load(besiktningsman_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "BESIKTNINGSMAN_NOT_FOUND"}
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_IDENTIFIER", "message": str(exc)}
            ) from exc
        return besiktningsman_to_payload(person)

    @router.get("/api/ovk/registry/besiktningsman", response_model=None)
    def list_besiktningsman() -> dict[str, Any]:
        return {
            "besiktningsman": [
                besiktningsman_to_payload(item) for item in besiktningsman_repository.list()
            ]
        }

    return router


def _validate_structure(payload: dict[str, Any]) -> dict[str, Any]:
    """Store inventory only; never carry inspection outcomes into the register."""

    def rows(value: Any, key: str) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError(f"{key} must be a list of objects")
        return value

    def required(row: dict[str, Any], key: str) -> str:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a nonempty string")
        return value.strip()

    def identifier(row: dict[str, Any], key: str, seen: set[str]) -> str:
        value = required(row, key)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value) or value in seen:
            raise ValueError(f"invalid or duplicate {key}: {value}")
        seen.add(value)
        return value

    system_ids: set[str] = set()
    systems: list[dict[str, str]] = []
    for row in rows(payload.get("systems", []), "systems"):
        system_id = identifier(row, "system_id", system_ids)
        kind = required(row, "system_type")
        if kind not in {"S", "F", "FT", "FTX", "FX"}:
            raise ValueError("invalid system_type")
        systems.append(
            {"system_id": system_id, "system_type": kind, "label": required(row, "label")}
        )

    unit_ids: set[str] = set()
    room_ids: set[str] = set()
    units: list[dict[str, Any]] = []
    for row in rows(payload.get("units", []), "units"):
        unit_id = identifier(row, "unit_id", unit_ids)
        kind = required(row, "kind")
        if kind not in {"apartment", "premises"}:
            raise ValueError("invalid unit kind")
        rooms = [
            {"room_id": identifier(room, "room_id", room_ids), "name": required(room, "name")}
            for room in rows(row.get("rooms", []), "rooms")
        ]
        units.append(
            {"unit_id": unit_id, "number": required(row, "number"), "kind": kind, "rooms": rooms}
        )

    space_ids: set[str] = set()
    spaces: list[dict[str, str]] = []
    for row in rows(payload.get("technical_spaces", []), "technical_spaces"):
        system_id = required(row, "system_id")
        if system_id not in system_ids:
            raise ValueError("technical space references unknown system")
        spaces.append(
            {
                "space_id": identifier(row, "space_id", space_ids),
                "label": required(row, "label"),
                "system_id": system_id,
            }
        )
    return {"units": units, "systems": systems, "technical_spaces": spaces}
