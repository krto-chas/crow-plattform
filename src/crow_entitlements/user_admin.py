from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .audit import write_audit_event
from .auth import UserRecord, hash_password, load_user, write_user
from .context import current_customer_from_request
from .models import CustomerContext

_ADMIN_ROLE = "platform-admin"


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    customer_id: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=512)
    roles: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=120)
    roles: list[str] = Field(default_factory=list)
    active: bool = True
    password: str | None = Field(default=None, min_length=12, max_length=512)


def user_admin_router(config_root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/users", response_model=None)
    def list_users(request: Request) -> dict[str, Any]:
        _require_admin(request)
        users_root = config_root / "users"
        if not users_root.is_dir():
            return {"users": []}
        users = []
        for path in sorted(users_root.glob("*.json")):
            user = load_user(config_root, path.stem)
            if user is not None:
                users.append(_public_user(user))
        return {"users": users}

    @router.post("/api/admin/users", status_code=201, response_model=None)
    def create_user(payload: UserCreate, request: Request) -> dict[str, Any]:
        administrator = _require_admin(request)
        username = _normalize_username(payload.username)
        customer_id = _normalize_customer_id(payload.customer_id)
        roles = _normalize_roles(payload.roles)
        _validate_customer_target(config_root, customer_id, roles)
        if load_user(config_root, username) is not None:
            raise HTTPException(status_code=409, detail="User already exists")
        salt, digest = hash_password(payload.password)
        user = UserRecord(
            username=username,
            customer_id=customer_id,
            roles=roles,
            password_salt=salt,
            password_hash=digest,
        )
        write_user(config_root, user)
        public = _public_user(user)
        write_audit_event(
            config_root,
            actor=administrator,
            action="user.created",
            target_type="user",
            target_id=username,
            customer_id=customer_id,
            after=public,
        )
        return public

    @router.put("/api/admin/users/{username}", response_model=None)
    def update_user(username: str, payload: UserUpdate, request: Request) -> dict[str, Any]:
        administrator = _require_admin(request)
        normalized = _normalize_username(username)
        existing = load_user(config_root, normalized)
        if existing is None:
            raise HTTPException(status_code=404, detail="User not found")
        customer_id = _normalize_customer_id(payload.customer_id)
        roles = _normalize_roles(payload.roles)
        _validate_customer_target(config_root, customer_id, roles)
        if administrator.user_id == normalized and not payload.active:
            raise HTTPException(
                status_code=400, detail="Cannot deactivate the current administrator"
            )

        before = _public_user(existing)
        password_salt = existing.password_salt
        password_hash = existing.password_hash
        password_changed = payload.password is not None
        if payload.password is not None:
            password_salt, password_hash = hash_password(payload.password)
        user = UserRecord(
            username=normalized,
            customer_id=customer_id,
            roles=roles,
            password_salt=password_salt,
            password_hash=password_hash,
            active=payload.active,
        )
        write_user(config_root, user, overwrite=True)
        after = _public_user(user)
        write_audit_event(
            config_root,
            actor=administrator,
            action="user.updated",
            target_type="user",
            target_id=normalized,
            customer_id=customer_id,
            before=before,
            after={**after, "password_changed": password_changed},
        )
        return after

    return router


def _require_admin(request: Request) -> CustomerContext:
    try:
        customer = current_customer_from_request(request)
    except RuntimeError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    if _ADMIN_ROLE not in customer.roles:
        raise HTTPException(status_code=403, detail="Platform administrator role required")
    return customer


def _public_user(user: UserRecord) -> dict[str, Any]:
    return {
        "username": user.username,
        "customer_id": user.customer_id,
        "roles": list(user.roles),
        "active": user.active,
    }


def _normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in normalized
    ):
        raise HTTPException(status_code=400, detail="Invalid username")
    return normalized


def _normalize_customer_id(customer_id: str) -> str:
    normalized = customer_id.strip().lower()
    if not normalized or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in normalized
    ):
        raise HTTPException(status_code=400, detail="Invalid customer id")
    return normalized


def _normalize_roles(roles: list[str]) -> tuple[str, ...]:
    normalized = tuple(sorted({role.strip() for role in roles if role.strip()}))
    if any(len(role) > 120 for role in normalized):
        raise HTTPException(status_code=400, detail="Invalid role")
    return normalized


def _validate_customer_target(config_root: Path, customer_id: str, roles: tuple[str, ...]) -> None:
    if _ADMIN_ROLE in roles:
        return
    target = config_root / "customers" / customer_id / "entitlements.json"
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Customer does not exist")
