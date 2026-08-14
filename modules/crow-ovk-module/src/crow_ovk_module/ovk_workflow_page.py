from __future__ import annotations

from importlib import resources

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response


def ovk_workflow_page_router() -> APIRouter:
    router = APIRouter()

    @router.get("/ovk/besiktning", response_class=HTMLResponse)
    def workflow_page() -> str:
        return _asset_text("workflow.html")

    @router.get("/ovk/besiktning/app.js", response_class=Response)
    def workflow_app() -> Response:
        return Response(_asset_text("workflow.js"), media_type="application/javascript")

    return router


def _asset_text(name: str) -> str:
    return resources.files("crow_ovk_module").joinpath("assets", name).read_text(encoding="utf-8")
