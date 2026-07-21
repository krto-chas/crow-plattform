# Module Trust Policy

Crow separates compatibility from trust.

A module can be contract-compatible yet still be rejected because its manifest is:

- unsigned,
- signed by an unknown signer,
- signed with a disallowed algorithm,
- modified after signing.

Production policy should require:

```text
require_signature = true
allowed_algorithms = hmac-sha256 or approved successor
trusted_signers = explicit allow-list
```

The current HMAC-SHA256 implementation is a deterministic reference suitable for local
deployment and tests. A production distribution ecosystem should migrate to asymmetric
signatures so private signing keys never need to exist in the runtime trust store.
