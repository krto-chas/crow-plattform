from __future__ import annotations

import os
import re
from typing import cast

from fastapi import Request

from .auth import SessionManager
from .models import CustomerContext

_CUSTOMER_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,119}$")


def current_customer_from_request(request: Request) -> CustomerContext:
    auth_mode = os.getenv("CROW_AUTH_MODE", "environment").strip().lower()
    manager = cast(
        SessionManager | None,
        getattr(request.app.state, "crow_session_manager", None),
    )
    if manager is not None:
        token = request.cookies.get(manager.cookie_name)
        if token:
            customer = manager.resolve(token)
            if customer is not None:
                return customer
    if auth_mode == "session":
        raise RuntimeError("Authentication required")
    return current_customer_from_env()


def current_customer_from_env() -> CustomerContext:
    mode = os.getenv("CROW_MODE", "local").strip().lower()
    configured_id = os.getenv("CROW_CUSTOMER_ID")
    if configured_id is None:
        if mode != "local":
            raise RuntimeError("CROW_CUSTOMER_ID is required outside local mode")
        configured_id = "local-dev"
    customer_id = configured_id.strip().lower()
    if not _CUSTOMER_ID.fullmatch(customer_id):
        raise RuntimeError("CROW_CUSTOMER_ID contains invalid characters")
    user_id = os.getenv("CROW_USER_ID") or None
    raw_roles = os.getenv("CROW_ROLES", "").split(",")
    roles = tuple(sorted({item.strip() for item in raw_roles if item.strip()}))
    return CustomerContext(customer_id=customer_id, user_id=user_id, roles=roles)
