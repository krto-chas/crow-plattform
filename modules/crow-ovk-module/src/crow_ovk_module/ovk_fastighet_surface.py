"""Yta för fastighetsentiteten och besiktningsmannaregistret (pass 102).

Skapas med fördel från kontoret innan besiktning, men kan även fyllas i fält.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
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
