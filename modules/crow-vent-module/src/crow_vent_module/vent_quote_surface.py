from __future__ import annotations

from decimal import Decimal
from importlib import resources
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from crow_vent_quote import VentQuoteRequest, build_vent_quote, quote_to_payload


def vent_quote_router() -> APIRouter:
    router = APIRouter()

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
    async def vent_quote(project_id: str, request: Request) -> JSONResponse:
        payload: Any = await request.json()
        takeoff_input = dict(payload.get("takeoff", {}))
        quote_input = dict(payload.get("quote", {}))

        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://crow.internal",
        ) as client:
            response = await client.post(
                f"/api/projects/{quote(project_id, safe='')}/takeoff",
                json=takeoff_input,
            )
        if response.status_code != 200:
            return JSONResponse(status_code=response.status_code, content=response.json())

        priced = response.json().get("priced")
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
        resources.files("crow_vent_module")
        .joinpath("assets", filename)
        .read_text(encoding="utf-8")
    )
