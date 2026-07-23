"""Crow Vent — the first production domain module on the Crow Backbone.

Implements the 0.5 plugin contract (ModuleManifest, ModuleCapabilities,
claim schemas, claim validation, healthcheck) and is discovered via the
``crow.modules`` entry point. Domain knowledge is delegated to the vent
lexicon; the Backbone never imports this package.
"""

from __future__ import annotations

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
from crow_vent.lexicon import VentLexicon

NAMESPACE = "vent"


class CrowVentModulePlugin:
    def __init__(self) -> None:
        self._lexicon = VentLexicon.default()

    def manifest(self) -> ModuleManifest:
        return ModuleManifest(
            module_id="crow.vent",
            name="Crow Vent",
            version="1.0.0",
            domain=NAMESPACE,
            backbone_api=">=1.0,<2.0",
            domain_model="1.0",
        )

    def capabilities(self) -> ModuleCapabilities:
        return ModuleCapabilities(
            claim_types=(
                "vent.duct.length",
                "vent.component.count",
                "vent.point.setpoint",
            ),
            rule_providers=("vent.authority",),
            technical_delta=True,
            commercial_impact=True,
            pricing_adapter=True,
            exports=("estimate_line", "quantity_takeoff", "client_question", "reservation"),
            human_review_supported=True,
        )

    def claim_schemas(self) -> tuple[ClaimSchema, ...]:
        return (
            ClaimSchema(NAMESPACE, "length", "decimal", unit_required=True),
            ClaimSchema(NAMESPACE, "count", "decimal", unit_required=True),
            ClaimSchema(NAMESPACE, "setpoint", "decimal", unit_required=True),
        )

    def validate_claim(self, claim: Claim) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if claim.namespace != NAMESPACE:
            errors.append(f"Unsupported namespace: {claim.namespace}")
        if claim.property not in {"length", "count", "setpoint"}:
            errors.append(f"Unsupported property: {claim.property}")
        if not claim.provenance.is_complete():
            errors.append("Provenance document_id is required")
        if not isinstance(claim.value, Decimal):
            errors.append("Value must be Decimal")
        if claim.property == "length" and claim.unit != "m":
            errors.append("Length unit must be m")
        if claim.property == "count":
            if claim.unit != "st":
                errors.append("Count unit must be st")
            elif (
                isinstance(claim.value, Decimal)
                and claim.value != claim.value.to_integral_value()
            ):
                errors.append("Count must be integral")
        subject = claim.subject.strip()
        if (
            self._lexicon.parse_duct_string(subject) is None
            and self._lexicon.lookup_component(subject) is None
        ):
            warnings.append(
                f"Subject {subject!r} is not a known vent designation "
                "(kanalsträng eller komponentbeteckning)"
            )
        return ValidationResult(not errors, tuple(errors), tuple(warnings))

    def healthcheck(self) -> ModuleHealth:
        lexicon_ok = self._lexicon.parse_duct_string("T-125") is not None
        status = HealthStatus.OK if lexicon_ok else HealthStatus.FAILED
        return ModuleHealth(
            status,
            {"manifest": True, "schemas": True, "lexicon": lexicon_ok},
            "Vent module is ready" if lexicon_ok else "Lexicon failed self-test",
        )
