from crow_module_conformance import (
    TrustDecision,
    TrustPolicy,
    TrustStore,
    evaluate_trust,
    sign_manifest,
)
from crow_module_sdk import ModuleManifest


def _manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="crow.example",
        name="Example",
        version="1.0.0",
        domain="example",
        backbone_api=">=1.0.0,<2.0.0",
        domain_model="1.0.0",
    )


def test_trusted_signature_is_accepted() -> None:
    store = TrustStore({"crow-release": b"secret"})
    signed = sign_manifest(_manifest(), signer_id="crow-release", key=b"secret")

    result = evaluate_trust(
        signed,
        policy=TrustPolicy(trusted_signers=("crow-release",)),
        store=store,
    )

    assert result.decision == TrustDecision.TRUSTED


def test_tampered_manifest_is_rejected() -> None:
    store = TrustStore({"crow-release": b"secret"})
    signed = sign_manifest(_manifest(), signer_id="crow-release", key=b"secret")
    tampered = signed.__class__(
        manifest=signed.manifest.__class__(
            module_id=signed.manifest.module_id,
            name=signed.manifest.name,
            version="1.0.1",
            domain=signed.manifest.domain,
            backbone_api=signed.manifest.backbone_api,
            domain_model=signed.manifest.domain_model,
        ),
        signer_id=signed.signer_id,
        algorithm=signed.algorithm,
        signature=signed.signature,
    )

    result = evaluate_trust(
        tampered,
        policy=TrustPolicy(trusted_signers=("crow-release",)),
        store=store,
    )

    assert result.decision == TrustDecision.INVALID_SIGNATURE


def test_unsigned_manifest_is_rejected_when_required() -> None:
    result = evaluate_trust(
        None,
        policy=TrustPolicy(require_signature=True),
        store=TrustStore(),
    )

    assert result.decision == TrustDecision.UNSIGNED
