# Pass 106 — Platform user lifecycle

## Scope

Pass 106 extends the Platform IAM foundation with administrator-managed user lifecycle while keeping authentication local and file-backed for the current internal deployment.

## Included

- administrator API for listing users without exposing password hashes or salts
- administrator creation of customer users
- update of customer association, roles, active state and optional password replacement
- dedicated `/admin/users` surface
- customer existence validation for non-platform-admin users
- protection against an administrator disabling their own currently active account through the API
- session revalidation against the current user record on every authenticated request
- immediate rejection of an already-issued session after the user is disabled or their customer/roles change

## Security boundary

The signed session token is no longer sufficient on its own. In session mode, the current user record must still exist, be active and match the customer and roles encoded in the token. This provides immediate local revocation for account disablement and authorization changes.

This pass does not claim MFA, OIDC/SAML, password recovery, login throttling, account lockout, delegated customer administration or enterprise identity lifecycle.

## Architecture rule

User management remains part of the Platform identity/entitlement layer, not a domain module. Product modules continue to consume the resolved customer context without owning user accounts.

## Verification gate

The pass is not considered verified until repository CI has passed Ruff format/check, mypy, strict first-party module type checking, pytest, architecture review and distribution build.
