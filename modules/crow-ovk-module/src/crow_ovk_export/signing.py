"""HMAC-SHA256-signerade exportvägar: ingen PDF lämnar plattformen osignerad.

Signaturen täcker den kanoniska sökvägen och utgångstiden. Verifiering sker med
konstanttidsjämförelse och nekar både manipulerade och utgångna länkar.
"""

from __future__ import annotations

import hashlib
import hmac

ALGORITHM = "hmac-sha256"


class ExportSignatureError(ValueError):
    """Ogiltig, manipulerad eller utgången exportsignatur."""


def sign_export_path(secret: str, path: str, expires_epoch: int) -> str:
    if not secret:
        raise ValueError("signing secret is required")
    if not path.startswith("/"):
        raise ValueError("export path must be absolute")
    message = f"{path}|{expires_epoch}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_export_signature(
    secret: str,
    path: str,
    expires_epoch: int,
    signature: str,
    *,
    now_epoch: int,
) -> None:
    if now_epoch > expires_epoch:
        raise ExportSignatureError("export link has expired")
    expected = sign_export_path(secret, path, expires_epoch)
    if not hmac.compare_digest(expected, signature):
        raise ExportSignatureError("export signature is invalid")
