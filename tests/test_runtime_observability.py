from __future__ import annotations

import json
import logging
import re
from io import StringIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_deployment.observability import configure_runtime_observability


def _observable_client(data_root: Path, config_root: Path) -> TestClient:
    data_root.mkdir(parents=True, exist_ok=True)
    config_root.mkdir(parents=True, exist_ok=True)
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    configure_runtime_observability(app, data_root=data_root, config_root=config_root)
    return TestClient(app)


def test_runtime_preserves_safe_request_id(tmp_path: Path) -> None:
    client = _observable_client(tmp_path / "data", tmp_path / "config")

    response = client.get("/health", headers={"X-Request-ID": "job-42:probe"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "job-42:probe"


def test_runtime_replaces_unsafe_request_id(tmp_path: Path) -> None:
    client = _observable_client(tmp_path / "data", tmp_path / "config")

    response = client.get("/health", headers={"X-Request-ID": "bad request id"})

    assert response.status_code == 200
    generated = response.headers["X-Request-ID"]
    assert generated != "bad request id"
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


def test_readiness_checks_persistent_roots(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    config_root = tmp_path / "config"
    client = _observable_client(data_root, config_root)

    ready = client.get("/ready")
    config_root.rmdir()
    not_ready = client.get("/ready")

    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert not_ready.status_code == 503
    assert not_ready.json()["status"] == "not_ready"
    assert not_ready.json()["checks"]["config_root"]["ready"] is False


def test_request_log_is_structured_json(tmp_path: Path) -> None:
    stream = StringIO()
    logger = logging.getLogger("crow.runtime")
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    try:
        client = _observable_client(tmp_path / "data", tmp_path / "config")
        response = client.get("/health", headers={"X-Request-ID": "trace-111"})
    finally:
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)

    assert response.status_code == 200
    event = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert event["event"] == "http.request"
    assert event["request_id"] == "trace-111"
    assert event["method"] == "GET"
    assert event["path"] == "/health"
    assert event["status_code"] == 200
    assert isinstance(event["duration_ms"], float)
