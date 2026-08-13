from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .models import CustomerContext

_COOKIE_NAME = "crow_session"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


@dataclass(frozen=True, slots=True)
class UserRecord:
    username: str
    customer_id: str
    roles: tuple[str, ...]
    password_salt: str
    password_hash: str
    active: bool = True


class SessionManager:
    def __init__(self, secret: str, *, ttl_seconds: int = 8 * 60 * 60) -> None:
        if len(secret) < 32:
            raise ValueError("CROW_SESSION_SECRET must contain at least 32 characters")
        self._secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    @property
    def cookie_name(self) -> str:
        return _COOKIE_NAME

    def issue(self, user: UserRecord, *, now: int | None = None) -> str:
        issued = int(time.time()) if now is None else now
        payload = {
            "sub": user.username,
            "customer_id": user.customer_id,
            "roles": list(user.roles),
            "iat": issued,
            "exp": issued + self.ttl_seconds,
        }
        encoded = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = _b64(hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def resolve(self, token: str, *, now: int | None = None) -> CustomerContext | None:
        try:
            encoded, signature = token.split(".", 1)
            expected = _b64(
                hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(signature, expected):
                return None
            payload = cast(dict[str, Any], json.loads(_unb64(encoded)))
            current = int(time.time()) if now is None else now
            if int(payload["exp"]) < current:
                return None
            return CustomerContext(
                customer_id=str(payload["customer_id"]),
                user_id=str(payload["sub"]),
                roles=tuple(sorted(str(role) for role in cast(list[Any], payload.get("roles", [])))),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None


def hash_password(password: str, *, salt: bytes | None = None) -> tuple[str, str]:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    resolved_salt = secrets.token_bytes(16) if salt is None else salt
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=resolved_salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return resolved_salt.hex(), digest.hex()


def verify_password(password: str, user: UserRecord) -> bool:
    try:
        _, digest = hash_password(password, salt=bytes.fromhex(user.password_salt))
    except ValueError:
        return False
    return hmac.compare_digest(digest, user.password_hash)


def load_user(config_root: Path, username: str) -> UserRecord | None:
    path = config_root / "users" / f"{_safe_username(username)}.json"
    if not path.is_file():
        return None
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return UserRecord(
        username=str(payload["username"]),
        customer_id=str(payload["customer_id"]),
        roles=tuple(sorted(str(role) for role in cast(list[Any], payload.get("roles", [])))),
        password_salt=str(payload["password_salt"]),
        password_hash=str(payload["password_hash"]),
        active=bool(payload.get("active", True)),
    )


def write_user(config_root: Path, user: UserRecord, *, overwrite: bool = False) -> Path:
    path = config_root / "users" / f"{_safe_username(user.username)}.json"
    if path.exists() and not overwrite:
        raise FileExistsError(f"User already exists: {user.username}")
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "username": user.username,
        "customer_id": user.customer_id,
        "roles": list(user.roles),
        "password_salt": user.password_salt,
        "password_hash": user.password_hash,
        "active": user.active,
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def _safe_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in normalized):
        raise ValueError("Username contains invalid characters")
    return normalized


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
