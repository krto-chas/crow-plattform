from __future__ import annotations

from importlib import resources
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response


def vent_router() -> APIRouter:
    router = APIRouter()

    @router.get("/vent", response_class=HTMLResponse)
    def vent_page() -> str:
        return _asset_text("dashboard.html")

    @router.get("/vent/assets/dashboard.js", include_in_schema=False, response_model=None)
    def vent_dashboard_script() -> Response:
        return Response(
            content=_asset_text("dashboard.js"),
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": "no-cache"},
        )

    @router.get(
        "/api/vent/projects/{project_id}/drawings/{checksum}/model",
        response_model=None,
    )
    async def vent_drawing_model(
        project_id: str, checksum: str, request: Request
    ) -> JSONResponse:
        """Entitlement-protected alias for the existing Vent drawing analysis pipeline."""
        path = (
            f"/api/projects/{quote(project_id, safe='')}/vent/"
            f"{quote(checksum, safe='')}"
        )
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://crow.internal"
        ) as client:
            response = await client.get(path, params=list(request.query_params.multi_items()))
        return JSONResponse(status_code=response.status_code, content=response.json())

    @router.post("/api/vent/projects/{project_id}/takeoff", response_model=None)
    async def vent_takeoff(project_id: str, request: Request) -> JSONResponse:
        """Stable, entitlement-protected product alias for the existing takeoff pipeline."""
        payload: Any = await request.json()
        path = f"/api/projects/{quote(project_id, safe='')}/takeoff"
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://crow.internal"
        ) as client:
            response = await client.post(path, json=payload)
        return JSONResponse(status_code=response.status_code, content=response.json())

    return router


def _asset_text(filename: str) -> str:
    return (
        resources.files("crow_vent_module")
        .joinpath("assets", filename)
        .read_text(encoding="utf-8")
    )
