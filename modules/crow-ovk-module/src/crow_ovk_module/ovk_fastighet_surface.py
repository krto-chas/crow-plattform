"""Yta för fastighetsentiteten och besiktningsmannaregistret (pass 102).

Skapas med fördel från kontoret innan besiktning, men kan även fyllas i fält.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from crow_ovk_fastighet import (
    BesiktningsmanRepository,
    FastighetRepository,
    KundRepository,
    besiktningsman_from_payload,
    besiktningsman_to_payload,
    fastighet_from_payload,
    fastighet_to_payload,
)
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from crow_ovk_workflow.repository import OvkWorkflowRepository

from .ovk_field_surface import _FieldSyncRepository, _validated_payload
from .ovk_inventory_promotion import inventory_revision, plan_inventory_promotion

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
    kund_repository = KundRepository(data_root)

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

    @router.get("/ovk/kunder.js", response_model=None)
    def kund_register_script() -> Response:
        return Response(
            _asset_text("desktop-kunder.js"),
            media_type="application/javascript",
            headers=_NO_CACHE,
        )

    @router.get("/ovk/fastigheter.js", response_model=None)
    def property_register_script() -> Response:
        return Response(
            _asset_text("desktop-properties.js"),
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
            if "kund_id" not in payload:
                # En klient som inte känner till kundkopplingen (flödet för ny
                # besiktning, äldre formulär) ska inte ta bort den genom att spara
                # fastigheten. En oläsbar tidigare post hindrar inte att den skrivs över.
                try:
                    previous = fastighet_repository.load(project_id, fastighet_id)
                except (FileNotFoundError, ValueError):
                    previous = None
                if previous is not None and previous.kund_id is not None:
                    payload["kund_id"] = previous.kund_id
            fastighet = fastighet_from_payload(payload)
            if fastighet.kund_id is not None and not kund_repository.exists(fastighet.kund_id):
                raise HTTPException(status_code=422, detail={"code": "KUND_NOT_FOUND"})
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
    def get_structure(
        project_id: str, fastighet_id: str, building_id: str, response: Response
    ) -> dict[str, Any]:
        path = structure_path(project_id, fastighet_id, building_id)
        result = _read_structure(path)
        response.headers["X-OVK-Inventory-Revision"] = inventory_revision(result)
        response.headers["Cache-Control"] = "no-store"
        return result

    @router.put(
        "/api/ovk/projects/{project_id}/fastighet/{fastighet_id}/byggnad/{building_id}/struktur",
        response_model=None,
    )
    async def save_structure(
        project_id: str, fastighet_id: str, building_id: str, request: Request, response: Response
    ) -> dict[str, Any]:
        path = structure_path(project_id, fastighet_id, building_id)
        payload = await _json_body(request)
        try:
            structure = _validate_structure(payload)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_OVK_STRUCTURE", "message": str(exc)}
            ) from exc
        expected = request.headers.get("X-OVK-Inventory-Revision")

        def save() -> None:
            with _structure_lock(path):
                if expected is not None and expected != inventory_revision(_read_structure(path)):
                    raise HTTPException(
                        status_code=409, detail={"code": "OVK_INVENTORY_REVISION_CONFLICT"}
                    )
                _write_structure(path, structure)

        await run_in_threadpool(save)
        response.headers["X-OVK-Inventory-Revision"] = inventory_revision(structure)
        return structure

    def promotion_plan(
        project_id: str,
        fastighet_id: str,
        building_id: str,
        inspection_id: str,
        path: Path,
        assignments: dict[str, str],
    ) -> dict[str, Any]:
        try:
            record = OvkWorkflowRepository(data_root).load(project_id, inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_INSPECTION_NOT_FOUND"}
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_IDENTIFIER"}) from exc
        obj = record.inspection.ovk_object
        if (obj.project_id, obj.object_id, obj.building_id) != (
            project_id,
            fastighet_id,
            building_id,
        ) or record.inspection.inspection_id != inspection_id:
            raise HTTPException(status_code=409, detail={"code": "OVK_INVENTORY_SOURCE_MISMATCH"})
        try:
            snapshot, snapshot_revision = _FieldSyncRepository(
                data_root, project_id=project_id
            ).load(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_FIELD_SNAPSHOT_NOT_FOUND"}
            ) from exc
        if snapshot.get("inspection_id") != inspection_id:
            raise HTTPException(status_code=409, detail={"code": "OVK_INVENTORY_SOURCE_MISMATCH"})
        _validated_payload(snapshot)
        inventory = _read_structure(path)
        try:
            if _validate_structure(inventory) != inventory:
                raise ValueError("Existing inventory must be normalized before promotion.")
            valid_systems = {item["system_id"] for item in inventory["systems"]}
            valid_points = {item["measurement_id"] for item in snapshot["measurements"]}
            if any(
                point_id not in valid_points or system_id not in valid_systems
                for point_id, system_id in assignments.items()
            ):
                raise ValueError("Unknown measurement point or inventory system.")
            plan = plan_inventory_promotion(inventory, snapshot, assignments)
            plan["structure"] = _validate_structure(plan["structure"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_INVENTORY_PROMOTION", "message": str(exc)},
            ) from exc
        base_revision = inventory_revision(inventory)
        token = inventory_revision(
            {
                "project_id": project_id,
                "fastighet_id": fastighet_id,
                "building_id": building_id,
                "inspection_id": inspection_id,
                "snapshot_revision": snapshot_revision,
                "inventory_revision": base_revision,
                "assignments": assignments,
                "plan": plan,
            }
        )
        return {
            **plan,
            "preview_token": token,
            "snapshot_revision": snapshot_revision,
            "inventory_revision": base_revision,
        }

    @router.post(
        "/api/ovk/projects/{project_id}/fastighet/{fastighet_id}/byggnad/"
        "{building_id}/struktur/aterforing/{inspection_id}/preview",
        response_model=None,
    )
    async def preview_promotion(
        project_id: str,
        fastighet_id: str,
        building_id: str,
        inspection_id: str,
        request: Request,
    ) -> dict[str, Any]:
        path = structure_path(project_id, fastighet_id, building_id)
        assignments = _promotion_assignments(await _json_body(request))
        return await run_in_threadpool(
            promotion_plan, project_id, fastighet_id, building_id, inspection_id, path, assignments
        )

    @router.post(
        "/api/ovk/projects/{project_id}/fastighet/{fastighet_id}/byggnad/"
        "{building_id}/struktur/aterforing/{inspection_id}/apply",
        response_model=None,
    )
    async def apply_promotion(
        project_id: str,
        fastighet_id: str,
        building_id: str,
        inspection_id: str,
        request: Request,
    ) -> dict[str, Any]:
        path = structure_path(project_id, fastighet_id, building_id)
        payload = await _json_body(request)
        assignments = _promotion_assignments(payload)
        expected = payload.get("preview_token")
        if payload.get("confirmed") is not True or not isinstance(expected, str):
            raise HTTPException(status_code=422, detail={"code": "OVK_PROMOTION_CONFIRM_REQUIRED"})

        def apply() -> dict[str, Any]:
            with _structure_lock(path):
                plan = promotion_plan(
                    project_id, fastighet_id, building_id, inspection_id, path, assignments
                )
                if plan["preview_token"] != expected:
                    raise HTTPException(
                        status_code=409, detail={"code": "OVK_PROMOTION_PREVIEW_STALE"}
                    )
                if not plan["additions"]:
                    raise HTTPException(
                        status_code=409, detail={"code": "OVK_PROMOTION_NO_ADDITIONS"}
                    )
                _write_structure(path, plan["structure"])
                return {
                    **plan,
                    "inventory_revision": inventory_revision(plan["structure"]),
                }

        return await run_in_threadpool(apply)

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


_TRAPPHUS_LIMIT = 200


def _promotion_assignments(payload: dict[str, Any]) -> dict[str, str]:
    assignments = payload.get("assignments", {})
    if not isinstance(assignments, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in assignments.items()
    ):
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_PROMOTION_ASSIGNMENTS"})
    return assignments


def _read_structure(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"units": [], "systems": [], "technical_spaces": []}
    result: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Stored building inventory must be an object.")
    return result


@contextmanager
def _structure_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / ".structure-write-lock.sqlite3"
    with closing(sqlite3.connect(lock_path, timeout=30)) as lock:
        lock.execute("BEGIN IMMEDIATE")
        try:
            yield
        finally:
            lock.rollback()


def _write_structure(path: Path, structure: dict[str, Any]) -> None:
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temp_path = Path(temporary.name)
        json.dump(structure, temporary, ensure_ascii=False, indent=2)
    try:
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


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

    # Trapphus är en egen lista i byggnaden. Enheterna pekar på sitt trapphus,
    # och enhetslistan förblir platt så att den frysta besiktningsstrukturen och
    # fältappen läser den som förut.
    trapphus_ids: set[str] = set()
    trapphus_names: set[str] = set()
    trapphus: list[dict[str, str]] = []
    trapphus_rows = rows(payload.get("trapphus", []), "trapphus")
    if len(trapphus_rows) > _TRAPPHUS_LIMIT:
        raise ValueError(f"at most {_TRAPPHUS_LIMIT} trapphus per building")
    for row in trapphus_rows:
        trapphus_id = identifier(row, "trapphus_id", trapphus_ids)
        namn = " ".join(required(row, "namn").split())
        adress = row.get("adress", "")
        if not isinstance(adress, str):
            raise ValueError("trapphus adress must be a string")
        adress = " ".join(adress.split())
        if len(trapphus_id) > 120 or len(namn) > 100 or len(adress) > 200:
            raise ValueError("trapphus value is too long")
        if not (namn.isprintable() and adress.isprintable()):
            raise ValueError("trapphus value contains control characters")
        if namn.casefold() in trapphus_names:
            raise ValueError(f"duplicate trapphus namn: {namn}")
        trapphus_names.add(namn.casefold())
        trapphus.append({"trapphus_id": trapphus_id, "namn": namn, "adress": adress})

    unit_ids: set[str] = set()
    room_ids: set[str] = set()
    point_ids: set[str] = set()
    units: list[dict[str, Any]] = []
    for row in rows(payload.get("units", []), "units"):
        unit_id = identifier(row, "unit_id", unit_ids)
        kind = required(row, "kind")
        if kind not in {"apartment", "premises"}:
            raise ValueError("invalid unit kind")
        rooms: list[dict[str, Any]] = []
        for room in rows(row.get("rooms", []), "rooms"):
            entry: dict[str, Any] = {
                "room_id": identifier(room, "room_id", room_ids),
                "name": required(room, "name"),
            }
            points: list[dict[str, Any]] = []
            for point in rows(room.get("measurement_points", []), "measurement_points"):
                point_id = identifier(point, "point_id", point_ids)
                point_type = required(point, "point_type")
                if point_type not in {"franluftsdon", "tilluftsdon", "overluftsdon"}:
                    raise ValueError("invalid measurement point type")
                system_id = required(point, "system_id")
                if system_id not in system_ids:
                    raise ValueError("measurement point references unknown system")
                design = point.get("designed_value")
                if design is not None:
                    if not isinstance(design, str) or not re.fullmatch(
                        r"[0-9]+(?:\.[0-9]+)?", design
                    ):
                        raise ValueError("invalid designed flow")
                if point.get("unit_of_measure", "l/s") != "l/s":
                    raise ValueError("invalid measurement unit")
                points.append(
                    {
                        "point_id": point_id,
                        "label": required(point, "label"),
                        "point_type": point_type,
                        "system_id": system_id,
                        "designed_value": design,
                        "unit_of_measure": "l/s",
                    }
                )
            if points:
                entry["measurement_points"] = points
            rooms.append(entry)
        number = required(row, "number")
        unit = {"unit_id": unit_id, "number": number, "kind": kind, "rooms": rooms}
        if kind == "premises":
            label = row.get("label", "")
            if not isinstance(label, str):
                raise ValueError("premises label must be a string")
            mode = row.get("display_mode", "name" if label.strip() else "number")
            if mode not in {"number", "name"}:
                raise ValueError("invalid premises display_mode")
            if mode == "name" and not label.strip():
                raise ValueError("premises name is required when display_mode is name")
            unit["label"] = label.strip()
            unit["display_mode"] = mode
        # Utelämnas utan trapphus, så att äldre strukturer normaliseras oförändrat.
        if row.get("trapphus_id") is not None:
            trapphus_ref = row["trapphus_id"]
            if not isinstance(trapphus_ref, str) or trapphus_ref not in trapphus_ids:
                raise ValueError("unit references unknown trapphus")
            unit["trapphus_id"] = trapphus_ref
        units.append(unit)

    space_ids: set[str] = set()
    spaces: list[dict[str, str]] = []
    for row in rows(payload.get("technical_spaces", []), "technical_spaces"):
        system_id = required(row, "system_id")
        if system_id not in system_ids:
            raise ValueError("technical space references unknown system")
        kind = row.get("kind", "unclassified")
        if not isinstance(kind, str) or kind not in {
            "unclassified",
            "flaktrum",
            "takflakt",
            "other",
        }:
            raise ValueError("invalid technical space kind")
        location = row.get("location", "")
        if not isinstance(location, str):
            raise ValueError("technical space location must be a string")
        spaces.append(
            {
                "space_id": identifier(row, "space_id", space_ids),
                "label": required(row, "label"),
                "system_id": system_id,
                "kind": kind,
                "location": location.strip(),
            }
        )
    result: dict[str, Any] = {"units": units, "systems": systems, "technical_spaces": spaces}
    if trapphus:
        result["trapphus"] = trapphus
    return result
