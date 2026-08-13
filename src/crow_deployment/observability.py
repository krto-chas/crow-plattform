from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_LOGGER_NAME = "crow.runtime"


def configure_runtime_observability(
    app: FastAPI,
    *,
    data_root: Path,
    config_root: Path,
) -> None:
    """Install the shared runtime request logger and readiness endpoint."""
    _configure_runtime_logger()
    app.add_middleware(RequestObservabilityMiddleware)

    @app.get("/ready", include_in_schema=False)
    def readiness() -> JSONResponse:
        payload = runtime_readiness(data_root=data_root, config_root=config_root)
        status_code = 200 if payload["status"] == "ready" else 503
        return JSONResponse(payload, status_code=status_code)


def runtime_readiness(*, data_root: Path, config_root: Path) -> dict[str, Any]:
    checks = {
        "data_root": _path_readiness(data_root),
        "config_root": _path_readiness(config_root),
    }
    ready = all(check["ready"] for check in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
    }


class RequestObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger(_LOGGER_NAME)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = _request_id(headers.get("x-request-id"))
        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        started = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            self._write_event(
                request_id=request_id,
                method=method,
                path=path,
                status_code=500,
                duration_ms=(perf_counter() - started) * 1000,
                error_type=type(exc).__name__,
            )
            raise

        self._write_event(
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=(perf_counter() - started) * 1000,
        )

    def _write_event(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        error_type: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "http.request",
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 3),
        }
        if error_type is not None:
            payload["error_type"] = error_type
        level = logging.ERROR if status_code >= 500 else logging.INFO
        self.logger.log(level, json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _request_id(candidate: str | None) -> str:
    if candidate is not None and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


def _path_readiness(path: Path) -> dict[str, Any]:
    exists = path.exists()
    is_directory = path.is_dir() if exists else False
    accessible = bool(
        exists
        and is_directory
        and os.access(path, os.R_OK | os.W_OK | os.X_OK)
    )
    return {
        "path": str(path),
        "ready": accessible,
        "exists": exists,
        "directory": is_directory,
        "readable_writable": accessible,
    }


def _configure_runtime_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    configured_level = os.getenv("CROW_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, configured_level, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger
