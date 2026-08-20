from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from .project_runtime import VentProjectRuntime


def vent_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    runtime = VentProjectRuntime(data_root)

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

    @router.get("/api/vent/registry")
    def vent_registry() -> dict[str, Any]:
        return runtime.registry()

    @router.get("/api/vent/projects/{project_id}/drawings/{checksum}/model")
    def vent_drawing_model(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        association_radius: float = 100.0,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        return runtime.model(
            project_id,
            checksum,
            tolerance=tolerance,
            association_radius=association_radius,
            layer=layer,
            visible_only=visible_only,
        )

    @router.post("/api/vent/projects/{project_id}/takeoff")
    def vent_takeoff(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return runtime.takeoff(project_id, body)

    @router.get("/api/vent/projects/{project_id}/drawings/{checksum}/quantity.csv")
    def vent_quantity_csv(project_id: str, checksum: str) -> Response:
        return _quantity_response(runtime, project_id, checksum)

    @router.get("/api/vent/projects/{project_id}/drawings/{checksum}/review")
    def vent_review(project_id: str, checksum: str) -> dict[str, Any]:
        return runtime.review(project_id, checksum)

    # Compatibility routes retained by the Vent module while clients migrate to /api/vent/*.
    @router.get(
        "/api/projects/{project_id}/vent/{checksum}",
        include_in_schema=False,
    )
    def legacy_vent_model(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        association_radius: float = 100.0,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        return runtime.model(
            project_id,
            checksum,
            tolerance=tolerance,
            association_radius=association_radius,
            layer=layer,
            visible_only=visible_only,
        )

    @router.post(
        "/api/projects/{project_id}/takeoff",
        include_in_schema=False,
    )
    def legacy_takeoff(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return runtime.takeoff(project_id, body)

    @router.get(
        "/api/projects/{project_id}/vent/{checksum}/quantity.csv",
        include_in_schema=False,
    )
    def legacy_quantity_csv(project_id: str, checksum: str) -> Response:
        return _quantity_response(runtime, project_id, checksum)

    @router.get(
        "/api/projects/{project_id}/vent/{checksum}/review",
        include_in_schema=False,
    )
    def legacy_review(project_id: str, checksum: str) -> dict[str, Any]:
        return runtime.review(project_id, checksum)

    return router


def _quantity_response(runtime: VentProjectRuntime, project_id: str, checksum: str) -> Response:
    return Response(
        content=runtime.quantity_csv(project_id, checksum),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="crow-vent-{checksum[:12]}-quantity.csv"'
        },
    )


def _asset_text(filename: str) -> str:
    return (
        resources.files("crow_vent_module").joinpath("assets", filename).read_text(encoding="utf-8")
    )
