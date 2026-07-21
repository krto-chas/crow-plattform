from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum

from crow_module_sdk import ModuleManifest


class TrustDecision(StrEnum):
    TRUSTED = "trusted"
    UNTRUSTED_SIGNER = "untrusted_signer"
    INVALID_SIGNATURE = "invalid_signature"
    UNSIGNED = "unsigned"


@dataclass(frozen=True, slots=True)
class SignedModuleManifest:
    manifest: ModuleManifest
    signer_id: str
    algorithm: str
    signature: str


@dataclass(frozen=True, slots=True)
class TrustEvaluation:
    decision: TrustDecision
    signer_id: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class TrustPolicy:
    require_signature: bool = True
    allowed_algorithms: tuple[str, ...] = ("hmac-sha256",)
    trusted_signers: tuple[str, ...] = ()


class TrustStore:
    def __init__(self, keys: Mapping[str, bytes] | None = None) -> None:
        self._keys = dict(keys or {})

    def add(self, signer_id: str, key: bytes) -> None:
        if not signer_id.strip():
            raise ValueError("signer_id must not be empty")
        if not key:
            raise ValueError("signing key must not be empty")
        self._keys[signer_id] = key

    def get(self, signer_id: str) -> bytes | None:
        return self._keys.get(signer_id)


def canonical_manifest_payload(manifest: ModuleManifest) -> bytes:
    return json.dumps(
        asdict(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sign_manifest(
    manifest: ModuleManifest,
    *,
    signer_id: str,
    key: bytes,
) -> SignedModuleManifest:
    if not key:
        raise ValueError("signing key must not be empty")
    signature = hmac.new(
        key,
        canonical_manifest_payload(manifest),
        hashlib.sha256,
    ).hexdigest()
    return SignedModuleManifest(
        manifest=manifest,
        signer_id=signer_id,
        algorithm="hmac-sha256",
        signature=signature,
    )


def evaluate_trust(
    signed: SignedModuleManifest | None,
    *,
    policy: TrustPolicy,
    store: TrustStore,
) -> TrustEvaluation:
    if signed is None:
        decision = TrustDecision.UNSIGNED if policy.require_signature else TrustDecision.TRUSTED
        return TrustEvaluation(
            decision=decision,
            signer_id=None,
            reason=(
                "Signature required but manifest is unsigned"
                if policy.require_signature
                else "Unsigned manifests are allowed by policy"
            ),
        )

    if signed.algorithm not in policy.allowed_algorithms:
        return TrustEvaluation(
            TrustDecision.INVALID_SIGNATURE,
            signed.signer_id,
            f"Algorithm is not allowed: {signed.algorithm}",
        )

    if policy.trusted_signers and signed.signer_id not in policy.trusted_signers:
        return TrustEvaluation(
            TrustDecision.UNTRUSTED_SIGNER,
            signed.signer_id,
            "Signer is not trusted by policy",
        )

    key = store.get(signed.signer_id)
    if key is None:
        return TrustEvaluation(
            TrustDecision.UNTRUSTED_SIGNER,
            signed.signer_id,
            "No trust key is registered for signer",
        )

    expected = hmac.new(
        key,
        canonical_manifest_payload(signed.manifest),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signed.signature):
        return TrustEvaluation(
            TrustDecision.INVALID_SIGNATURE,
            signed.signer_id,
            "Manifest signature verification failed",
        )

    return TrustEvaluation(
        TrustDecision.TRUSTED,
        signed.signer_id,
        "Manifest signature verified",
    )
