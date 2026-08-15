from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_entitlements.auth import UserRecord, hash_password, write_user
from crow_workbench.shell import create_app


def test_browser_logout_clears_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.setenv("CROW_SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("CROW_COOKIE_SECURE", "false")

    customer = tmp_path / "config" / "customers" / "acme" / "entitlements.json"
    customer.parent.mkdir(parents=True, exist_ok=True)
    customer.write_text(json.dumps({"customer_id": "acme", "modules": []}), encoding="utf-8")

    salt, digest = hash_password("correct-horse-battery-staple")
    write_user(
        tmp_path / "config",
        UserRecord(
            username="alice",
            customer_id="acme",
            roles=(),
            password_salt=salt,
            password_hash=digest,
            active=True,
        ),
    )

    client = TestClient(create_app(tmp_path))
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    assert client.get("/api/session").status_code == 200

    logout = client.get("/logout", follow_redirects=False)

    assert logout.status_code == 303
    assert logout.headers["location"] == "/login"
    assert client.get("/api/session").status_code == 401
