from decimal import Decimal

from crow_module_sdk.models import (
    Claim,
    ClaimSchema,
    HealthStatus,
    ModuleCapabilities,
    ModuleHealth,
    ModuleManifest,
    ValidationResult,
)


class ExamplePlugin:
    def manifest(self) -> ModuleManifest:
        return ModuleManifest(
            module_id="crow.example",
            name="Crow Example Module",
            version="0.1.0",
            domain="synthetic",
            backbone_api=">=1.0,<2.0",
            domain_model="1.0",
        )

    def capabilities(self) -> ModuleCapabilities:
        return ModuleCapabilities(
            claim_types=("example.component.size",),
            rule_providers=("example.authority",),
            technical_delta=True,
            commercial_impact=True,
            pricing_adapter=True,
            exports=("estimate_line", "client_question", "reservation"),
            human_review_supported=True,
        )

    def claim_schemas(self) -> tuple[ClaimSchema, ...]:
        return (ClaimSchema("example", "size", "decimal", unit_required=True),)

    def validate_claim(self, claim: Claim) -> ValidationResult:
        errors: list[str] = []
        if claim.namespace != "example":
            errors.append("Unsupported namespace")
        if claim.property != "size":
            errors.append("Unsupported property")
        if not claim.provenance.is_complete():
            errors.append("Provenance document_id is required")
        if not isinstance(claim.value, Decimal):
            errors.append("Value must be Decimal")
        if claim.unit != "mm":
            errors.append("Unit must be mm")
        return ValidationResult(not errors, tuple(errors))

    def healthcheck(self) -> ModuleHealth:
        return ModuleHealth(
            HealthStatus.OK,
            {"manifest": True, "schemas": True, "determinism": True},
            "Example module is ready",
        )
