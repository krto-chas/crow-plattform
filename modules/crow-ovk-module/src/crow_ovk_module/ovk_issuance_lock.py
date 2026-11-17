from __future__ import annotations

import re
import sqlite3
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from crow_ovk_intyg import OvkIntygRepository

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_ISSUANCE_ROUTE_SUFFIXES = (
    "/inspections/{inspection_id}/intyg",
    "/inspections/{inspection_id}/intyg/recover",
)


def require_unissued(data_root: Path, project_id: str, inspection_id: str) -> None:
    if any(
        item.inspection_id == inspection_id
        for item in OvkIntygRepository(data_root).list(project_id)
    ):
        raise HTTPException(status_code=409, detail={"code": "OVK_INSPECTION_ISSUED"})
    manifest = (
        data_root / "projects" / project_id / "ovk-issuance-manifest" / f"{inspection_id}.json"
    )
    if manifest.exists():
        raise HTTPException(status_code=409, detail={"code": "OVK_ISSUANCE_RECOVERY_REQUIRED"})


def inspection_mutation_guard(data_root: Path) -> Callable[[Request], AsyncIterator[None]]:
    async def guard(request: Request) -> AsyncIterator[None]:
        project_id = request.path_params.get("project_id")
        inspection_id = request.path_params.get("inspection_id")
        if request.method not in {"PUT", "POST", "PATCH", "DELETE"} or not (
            project_id and inspection_id
        ):
            yield
            return
        for value in (project_id, inspection_id):
            if not _SAFE_ID.fullmatch(value) or value in {".", ".."}:
                raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"})
        # Låset tas alltid, även innan projektkatalogen finns: annars kan en
        # långsam första begäran passera vakten och skriva efter ett utfärdande.
        # Låsfilerna ligger utanför ``projects/`` så att ett id som bara
        # förekommer i en URL aldrig ger upphov till en projektkatalog.
        root = data_root / "ovk-issuance-lock" / project_id
        root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            root / f"{inspection_id}.sqlite3", timeout=30, check_same_thread=False
        )
        try:
            await run_in_threadpool(connection.execute, "BEGIN IMMEDIATE")
            # Issuance checks duplicate certificate IDs first, then inspection identity.
            # Jämför mot ruttmallen, inte den faktiska sökvägen: ett besiktnings-id
            # som råkar heta ``intyg`` får inte slippa kontrollen.
            route_path = getattr(request.scope.get("route"), "path", "")
            if not route_path.endswith(_ISSUANCE_ROUTE_SUFFIXES):
                require_unissued(data_root, project_id, inspection_id)
            yield
        finally:
            connection.close()

    return guard
