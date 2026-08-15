# ADR-006: Signed module manifests

## Status
Accepted

## Decision
Production trust policy requires signed manifests from explicitly trusted signers. The reference implementation uses HMAC-SHA256 for deterministic local verification.

## Consequences
Unsigned or tampered modules can be blocked before registration. A future asymmetric implementation can replace the reference signer without changing the policy model.

## Begränsning (tillagd i 0.5.0-rc.3)

HMAC-SHA256 är symmetrisk: den som innehar verifieringsnyckeln kan även förfalska signaturer.
Detta är acceptabelt som referensimplementation inom en enda förtroendedomän, men innan
tredjepartsmoduler distribueras krävs asymmetrisk signering (t.ex. Ed25519) där Backbone
endast innehar publika nycklar. TrustPolicy/TrustStore-kontrakten är utformade för att kunna
bära fler algoritmer utan brytande ändringar.
