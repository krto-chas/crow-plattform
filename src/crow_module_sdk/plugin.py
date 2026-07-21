from typing import Protocol

from .models import (
    Claim,
    ClaimSchema,
    ModuleCapabilities,
    ModuleHealth,
    ModuleManifest,
    ValidationResult,
)


class CrowModulePlugin(Protocol):
    def manifest(self) -> ModuleManifest: ...
    def capabilities(self) -> ModuleCapabilities: ...
    def claim_schemas(self) -> tuple[ClaimSchema, ...]: ...
    def validate_claim(self, claim: Claim) -> ValidationResult: ...
    def healthcheck(self) -> ModuleHealth: ...
