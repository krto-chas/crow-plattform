from __future__ import annotations

from decimal import Decimal
from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from crow_vent_quote import VentQuoteRequest, build_vent_quote, quote_to_payload

from .project_runtime import VentProjectRuntime


def vent_quote_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    runtime = VentProjectRuntime(data_root)

    @router.get("/vent/offert", response_class=HTMLResponse)
    def vent_quote_page() -> str:
        return _asset_text("quote.html")

    @router.get("/vent/assets/quote.js", include_in_schema=False, response_model=None)
    def vent_quote_script() -> Response:
        return Response(
            content=_asset_text("quote.js"),
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": "no-cache"},
        )

    @router.post("/api/vent/projects/{project_id}/quote", response_model=None)
    def vent_quote(project_id: str, payload: dict[str, Any]) -> JSONResponse:
        takeoff_input = dict(payload.get("takeoff", {}))
        quote_input = dict(payload.get("quote", {}))

        priced = runtime.takeoff(project_id, takeoff_input).get("priced")
        if priced is None:
            return JSONResponse(
                status_code=422,
                content={"detail": {"code": "PRICED_TAKEOFF_REQUIRED"}},
            )

        try:
            quote_request = VentQuoteRequest(
                project_name=str(quote_input.get("project_name", project_id)),
                customer_name=str(quote_input.get("customer_name", "")),
                quote_date=str(quote_input.get("quote_date", "")),
                validity_days=int(quote_input.get("validity_days", 30)),
                overhead_percent=Decimal(str(quote_input.get("overhead_percent", "0"))),
                risk_percent=Decimal(str(quote_input.get("risk_percent", "0"))),
                profit_percent=Decimal(str(quote_input.get("profit_percent", "0"))),
                scope_note=str(quote_input.get("scope_note", "")),
                exclusions=tuple(str(item) for item in quote_input.get("exclusions", [])),
            )
            result = build_vent_quote(priced, quote_request)
        except (TypeError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={"detail": {"code": "INVALID_QUOTE_INPUT", "message": str(error)}},
            )
        return JSONResponse(content=quote_to_payload(result))

    return router


def _asset_text(filename: str) -> str:
    return (
        resources.files("crow_vent_module").joinpath("assets", filename).read_text(encoding="utf-8")
    )
