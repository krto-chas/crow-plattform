"""Checksumma för OVK-intyg: deterministisk SHA-256 över kanonisk payload.

Verifieringskoden är de första 12 hextecknen (versaler, grupperade 4-4-4)
och trycks på intyget tillsammans med QR-koden. Verifieringssidan räknar
om checksumman ur det lagrade intyget och jämför i konstant tid — ett
manipulerat intyg eller en manipulerad kod ger EJ GILTIGT.
"""

from __future__ import annotations

import json
import os
from hashlib import sha256
from hmac import compare_digest

from .models import OvkIntyg
from .service import intyg_to_payload

_CODE_HEX_LENGTH = 12
VERIFY_BASE_ENV = "CROW_OVK_VERIFY_BASE"
# Adressen på trycket är den publika redan från start: intyg som utfärdas medan
# verifieringssidan ännu är intern får då fungerande QR-koder den dag den öppnas.
DEFAULT_VERIFY_BASE = "https://crowab.se/ovk/verifiera"


def intyg_checksum(intyg: OvkIntyg) -> str:
    canonical = json.dumps(
        intyg_to_payload(intyg),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def intyg_verification_code(intyg: OvkIntyg) -> str:
    raw = intyg_checksum(intyg)[:_CODE_HEX_LENGTH].upper()
    return "-".join((raw[0:4], raw[4:8], raw[8:12]))


def _normalize_code(code: str) -> str:
    return code.replace("-", "").replace(" ", "").strip().upper()


def verify_intyg_code(intyg: OvkIntyg, code: str) -> bool:
    expected = _normalize_code(intyg_verification_code(intyg))
    provided = _normalize_code(code)
    return compare_digest(expected.encode("utf-8"), provided.encode("utf-8"))


def intyg_verify_url(intyg: OvkIntyg) -> str:
    base = os.environ.get(VERIFY_BASE_ENV, "").strip().rstrip("/") or DEFAULT_VERIFY_BASE
    code = _normalize_code(intyg_verification_code(intyg))
    return f"{base}/{intyg.project_id}/{intyg.intyg_id}?c={code}"
