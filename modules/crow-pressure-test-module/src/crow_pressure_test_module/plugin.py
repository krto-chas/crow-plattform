from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from crow_module_sdk.models import (
    Claim,
    ClaimSchema,
    HealthStatus,
    ModuleCapabilities,
    ModuleHealth,
    ModuleManifest,
    ValidationResult,
)
from crow_pressure_test import load_knowledge
from crow_workbench.pressure_test_integration_surface import pressure_test_integration_router
from crow_workbench.pressure_test_surface import pressure_test_router


class CrowPressureTestModulePlugin:
    def manifest(self) -> ModuleManifest:
        return ModuleManifest(
            module_id="crow.provtryckning",
            name="Crow Provtryckning",
            version="1.0.0",
            domain="provtryckning",
            backbone_api=">=1.0,<2.0",
            domain_model="1.0",
        )

    def capabilities(self) -> ModuleCapabilities:
        return ModuleCapabilities(
            claim_types=(),
            rule_providers=("pressure_test.knowledge",),
            technical_delta=True,
            commercial_impact=True,
            pricing_adapter=True,
            exports=("pressure_test_protocol",),
            human_review_supported=True,
        )

    def claim_schemas(self) -> tuple[ClaimSchema, ...]:
        return ()

    def validate_claim(self, claim: Claim) -> ValidationResult:
        return ValidationResult(False, ("Provtryckning exposes no claim schema in 1.0",), ())

    def healthcheck(self) -> ModuleHealth:
        knowledge = load_knowledge()
        ok = bool(knowledge.standards)
        return ModuleHealth(
            HealthStatus.OK if ok else HealthStatus.FAILED,
            {"knowledge": ok, "web": True},
            "Provtryckning module is ready" if ok else "Pressure-test knowledge is unavailable",
        )

    def routers(self, data_root: Path) -> tuple[APIRouter, ...]:
        del data_root
        return (pressure_test_router(), pressure_test_integration_router())
