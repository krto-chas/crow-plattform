from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .auth import SessionManager, load_user, verify_password
from .context import current_customer_from_request


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)


def configure_auth(app: FastAPI, *, config_root: Path) -> None:
    secret = os.getenv("CROW_SESSION_SECRET")
    manager = SessionManager(secret) if secret else None
    app.state.crow_session_manager = manager
    app.include_router(_router(config_root, manager))


def _router(config_root: Path, manager: SessionManager | None) -> APIRouter:
    router = APIRouter()

    @router.post("/api/auth/login", response_model=None)
    def login(payload: LoginRequest, response: Response) -> dict[str, object]:
        if manager is None:
            raise HTTPException(status_code=503, detail="Session authentication is not configured")
        user = load_user(config_root, payload.username)
        if user is None or not user.active or not verify_password(payload.password, user):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token = manager.issue(user)
        response.set_cookie(
            manager.cookie_name,
            token,
            httponly=True,
            samesite="lax",
            secure=_secure_cookie(),
            max_age=manager.ttl_seconds,
            path="/",
        )
        return {
            "user_id": user.username,
            "customer_id": user.customer_id,
            "roles": list(user.roles),
            "destination": "/admin" if "platform-admin" in user.roles else "/app",
        }

    @router.post("/api/auth/logout", status_code=204)
    def logout(response: Response) -> Response:
        cookie_name = manager.cookie_name if manager is not None else "crow_session"
        response.delete_cookie(cookie_name, path="/")
        return response

    @router.get("/api/auth/me", response_model=None)
    def me(request: Request) -> dict[str, object]:
        customer = current_customer_from_request(request)
        return {
            "user_id": customer.user_id,
            "customer_id": customer.customer_id,
            "roles": list(customer.roles),
            "destination": "/admin" if "platform-admin" in customer.roles else "/app",
        }

    return router


def _secure_cookie() -> bool:
    return os.getenv("CROW_COOKIE_SECURE", "true").strip().lower() not in {"0", "false", "no"}
