from __future__ import annotations

from importlib import resources
from typing import Any

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

    @router.post("/api/vent/projects/{project_id}/takeoff", response_model=None)
    async def vent_takeoff(project_id: str, request: Request) -> JSONResponse:
        """Stable, entitlement-protected product alias for the existing takeoff pipeline."""
        payload: Any = await request.json()
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://crow.internal"
        ) as client:
            response = await client.post(f"/api/projects/{project_id}/takeoff", json=payload)
        return JSONResponse(status_code=response.status_code, content=response.json())

    return router


def _asset_text(filename: str) -> str:
    return (
        resources.files("crow_vent_module")
        .joinpath("assets", filename)
        .read_text(encoding="utf-8")
    )
