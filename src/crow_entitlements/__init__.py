"""Product module metadata and customer entitlement controls."""

from .catalog import load_product_module_catalog
from .context import current_customer_from_env
from .entitlements import load_customer_entitlements
from .models import (
    CustomerContext,
    CustomerEntitlements,
    EntitlementEntry,
    ProductModule,
    ProductModuleCatalog,
    ProductModuleStatus,
)

__all__ = [
    "CustomerContext",
    "CustomerEntitlements",
    "EntitlementEntry",
    "ProductModule",
    "ProductModuleCatalog",
    "ProductModuleStatus",
    "current_customer_from_env",
    "load_customer_entitlements",
    "load_product_module_catalog",
]
