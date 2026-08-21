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

from .ovk_bevakning_surface import ovk_bevakning_router
from .ovk_dashboard_surface import ovk_dashboard_router
from .ovk_export_surface import ovk_export_router
from .ovk_fastighet_surface import ovk_fastighet_router
from .ovk_field_context_page import ovk_field_context_page_router
from .ovk_field_history import ovk_field_history_router
from .ovk_field_media import ovk_field_media_router
from .ovk_field_surface import ovk_field_router
from .ovk_field_workbench import ovk_field_workbench_router
from .ovk_intyg_surface import ovk_intyg_router
from .ovk_legacy_surface import ovk_legacy_router
from .ovk_protokoll_surface import ovk_protokoll_router
from .ovk_reinspection_surface import ovk_reinspection_router
from .ovk_reporting_surface import ovk_reporting_router
from .ovk_surface import ovk_router
from .ovk_time_surface import ovk_time_router
from .ovk_workflow_page import ovk_workflow_page_router
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
            exports=(
                "ovk_protocol",
                "ovk_intyg",
                "ovk_bevakning",
                "field_evidence",
                "ovk_annual_report",
            ),
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
        return (
            ovk_dashboard_router(data_root),
            ovk_router(),
            ovk_workflow_page_router(),
            ovk_workflow_router(data_root),
            ovk_intyg_router(data_root),
            ovk_reinspection_router(data_root),
            ovk_bevakning_router(data_root),
            ovk_export_router(data_root),
            ovk_fastighet_router(data_root),
            ovk_protokoll_router(data_root),
            ovk_field_context_page_router(),
            ovk_field_router(data_root),
            ovk_field_media_router(data_root),
            ovk_field_workbench_router(data_root),
            ovk_field_history_router(data_root),
            ovk_legacy_router(data_root),
            ovk_reporting_router(data_root),
            ovk_time_router(data_root),
        )
