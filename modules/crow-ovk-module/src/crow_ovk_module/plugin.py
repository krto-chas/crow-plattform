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
from crow_ovk_field import load_defect_types

from .ovk_field_surface import ovk_field_router
from .ovk_surface import ovk_router
from .ovk_workflow_surface import ovk_workflow_router


class CrowOvkModulePlugin:
    def manifest(self) -> ModuleManifest:
        return ModuleManifest(
            module_id="crow.ovk",
            name="Crow OVK",
            version="1.0.0",
            domain="ovk",
            backbone_api=">=1.0,<2.0",
            domain_model="1.0",
        )

    def capabilities(self) -> ModuleCapabilities:
        return ModuleCapabilities(
            claim_types=(),
            rule_providers=("ovk.regulations",),
            technical_delta=True,
            commercial_impact=True,
            pricing_adapter=True,
            exports=("ovk_protocol", "field_evidence"),
            human_review_supported=True,
        )

    def claim_schemas(self) -> tuple[ClaimSchema, ...]:
        return ()

    def validate_claim(self, claim: Claim) -> ValidationResult:
        return ValidationResult(False, ("OVK exposes no claim schema in 1.0",), ())

    def healthcheck(self) -> ModuleHealth:
        defects_ok = bool(load_defect_types())
        return ModuleHealth(
            HealthStatus.OK if defects_ok else HealthStatus.FAILED,
            {"defect_taxonomy": defects_ok, "web": True},
            "OVK module is ready" if defects_ok else "OVK defect taxonomy is unavailable",
        )

    def routers(self, data_root: Path) -> tuple[APIRouter, ...]:
        return (ovk_router(), ovk_workflow_router(data_root), ovk_field_router())
