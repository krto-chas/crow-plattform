from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from crow_accepted_claims import (
    build_project_accepted_claims,
    load_accepted_claims,
    summarize_accepted_claims,
)
from crow_authority import load_resolution, resolve_project, summarize_resolution
from crow_building_graph import (
    ALLOWED_RELATIONS,
    COMPONENT_RELATIONS,
    SYSTEM_DISCIPLINES,
    BuildingGraphService,
    BuildingStructureService,
    ComponentGraphService,
    GraphRepository,
    SystemGraphService,
)
from crow_canonical import (
    CanonicalEvidence,
    CanonicalGraphBridge,
    CanonicalRelation,
    IdentityReviewDecision,
    IdentityReviewService,
)
from crow_claim_extraction import (
    extract_project_claims,
    load_claim_candidates,
    summarize_claim_candidates,
)
from crow_commercial_adjustment import (
    apply_project_adjustments,
    load_adjusted,
    summarize_adjustments,
    write_profile_template,
)
from crow_commercial_impact import (
    build_project_commercial_impacts,
    load_commercial_impacts,
    summarize_commercial_impacts,
    write_price_book_template,
)
from crow_commercial_review import (
    CommercialReviewStatus,
    initialize_project_commercial_review,
    load_review,
    summarize_review,
    update_project_commercial_review,
)
from crow_document_intelligence.repository import load_index
from crow_document_intelligence.service import (
    create_project,
    import_into_project,
    slugify,
    summarize,
)
from crow_estimate_line import build_project_estimate, load_estimate, summarize_estimate
from crow_geometry_framework import (
    BoundingBox2D,
    as_payload,
    build_topology,
    connected_objects,
    consolidate_observations,
    discover_system_observations,
    dwg_adapter_status,
    find_object,
    geometry_from_import_manifest,
    geometry_index,
    identify_systems,
    nearest_objects,
    object_payload,
    object_system,
    objects_in_bbox,
    related_objects,
    search_geometry,
    segment_network,
    spatial_index_summary,
    system_observations,
    trace_network,
)
from crow_import_framework import ImportManager, create_default_registry
from crow_inference import InferenceService
from crow_knowledge_fusion import fuse_project, load_fusion_result, summarize_fusion
from crow_knowledge_runtime import KnowledgePackRuntime
from crow_reasoning import FindingRepository, FindingService, ReasoningService, RuleService
from crow_scope_impact import (
    build_project_scope_impacts,
    load_scope_impacts,
    summarize_scope_impacts,
    write_rule_set_template,
)
from crow_technical_delta import build_project_deltas, load_delta_set, summarize_deltas
from crow_vent import VentGraphAudit, build_vent_model, component_registry, quantity_takeoff_csv

_UPLOAD_FILES = File(...)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    project_id: str | None = Field(default=None, max_length=120)


class AuthorityDocumentInput(BaseModel):
    document_id: str
    authority_type: str
    title: str = ""
    issue_date: str | None = None
    revision: str | None = None


class AuthorityResolveRequest(BaseModel):
    documents: list[AuthorityDocumentInput]


class FindingStatusRequest(BaseModel):
    status: str
    actor: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    assignee: str | None = Field(default=None, max_length=120)


class CommercialReviewRequest(BaseModel):
    status: str
    reviewer: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)


class IdentityReviewRequest(BaseModel):
    decision: str = Field(pattern="^(confirm_same|reject_same)$")
    reviewer: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=2000)
    decided_at: str | None = None


class AuditFindingReviewRequest(BaseModel):
    decision: str = Field(pattern="^(acknowledge|mark_resolved|dismiss)$")
    reviewer: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=2000)
    decided_at: str | None = None


class LayerStateInput(BaseModel):
    visible: bool | None = None
    locked: bool | None = None


class SelectionInput(BaseModel):
    source_checksum: str
    object_ids: list[str] = Field(default_factory=list, max_length=500)
    mode: str = Field(default="replace", pattern="^(replace|add|remove|clear)$")


class GraphEvidenceInput(BaseModel):
    kind: str
    source_id: str
    locator: str | None = None
    checksum: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_id: str | None = None


class GraphObjectInput(BaseModel):
    object_type: str = Field(min_length=1, max_length=120)
    discipline: str = Field(default="generic", min_length=1, max_length=80)
    name: str | None = Field(default=None, max_length=240)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = None


class GraphObjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=240)
    status: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="system", max_length=120)


class GraphRelationInput(BaseModel):
    source_id: str
    relation_type: str
    target_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    relation_id: str | None = None


class GraphPropertyInput(BaseModel):
    owner_id: str
    name: str = Field(min_length=1, max_length=120)
    value: Any
    unit: str | None = Field(default=None, max_length=40)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    property_id: str | None = None


class BuildingInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    code: str | None = Field(default=None, max_length=80)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = None


class FloorInput(BaseModel):
    building_id: str
    name: str = Field(min_length=1, max_length=240)
    level: float | None = None
    code: str | None = Field(default=None, max_length=80)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = None


class SpaceInput(BaseModel):
    floor_id: str
    name: str = Field(min_length=1, max_length=240)
    number: str | None = Field(default=None, max_length=80)
    area: float | None = None
    area_unit: str = Field(default="m2", max_length=20)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = None


class ZoneInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    space_ids: list[str] = Field(min_length=1)
    zone_type: str = Field(default="generic", max_length=80)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = None


class TechnicalSystemInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    discipline: str
    system_type: str = Field(default="generic", max_length=120)
    code: str | None = Field(default=None, max_length=80)
    parent_system_id: str | None = None
    located_in_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = None


class SystemRelationInput(BaseModel):
    source_system_id: str
    target_system_id: str
    relation_type: str = "connects_to"
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SystemServiceInput(BaseModel):
    system_id: str
    target_id: str
    relation_type: str = "serves"
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TechnicalComponentInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    discipline: str
    component_type: str = Field(default="generic", max_length=120)
    code: str | None = Field(default=None, max_length=80)
    system_id: str | None = None
    located_in_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = None


class ComponentRelationInput(BaseModel):
    source_component_id: str
    target_component_id: str
    relation_type: str = "connects_to"
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComponentPropertyInput(BaseModel):
    component_id: str
    name: str = Field(min_length=1, max_length=160)
    value: Any
    unit: str | None = Field(default=None, max_length=40)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _safe_project_id(project_id: str) -> str:
    if not project_id or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in project_id.lower()
    ):
        raise HTTPException(status_code=400, detail="Ogiltigt projekt-id")
    return project_id.lower()


def create_app(data_root: Path | None = None) -> FastAPI:
    root = data_root or Path.cwd() / ".crow-workbench"
    projects_root = root / "projects"
    uploads_root = root / "uploads"
    static_root = Path(__file__).parent / "static"
    projects_root.mkdir(parents=True, exist_ok=True)
    uploads_root.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Crow Workbench", version="0.7.0-alpha.1")
    import_registry = create_default_registry()
    app.mount("/static", StaticFiles(directory=static_root), name="static")

    def project_file(project_id: str) -> Path:
        return projects_root / _safe_project_id(project_id) / "crow-project.json"

    def require_project(project_id: str) -> Path:
        path = project_file(project_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Projektet finns inte")
        return path

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_root / "index.html")

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(projects_root.glob("*/crow-project.json")):
            index_data = load_index(path)
            items.append(_jsonable(summarize(index_data)))
        return items

    @app.post("/api/projects", status_code=201)
    def new_project(payload: ProjectCreate) -> dict[str, Any]:
        resolved_id = (
            _safe_project_id(payload.project_id) if payload.project_id else slugify(payload.name)
        )
        directory = projects_root / resolved_id
        if directory.exists():
            raise HTTPException(status_code=409, detail="Projekt-id används redan")
        path = create_project(directory, payload.name, resolved_id)
        return _jsonable(summarize(load_index(path)))

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        index_data = load_index(require_project(project_id))
        return {
            "summary": _jsonable(summarize(index_data)),
            "documents": [_jsonable(asdict(document)) for document in index_data.documents],
            "sessions": [_jsonable(asdict(session)) for session in index_data.import_sessions],
        }

    @app.get("/api/importers")
    def list_importers() -> list[dict[str, Any]]:
        return [
            {
                "id": plugin.id,
                "format_id": plugin.format_id,
                "extensions": list(plugin.extensions),
                "media_types": list(plugin.media_types),
            }
            for plugin in import_registry.plugins()
        ]

    @app.post("/api/projects/{project_id}/documents", status_code=201)
    async def upload_documents(
        project_id: str, files: list[UploadFile] = _UPLOAD_FILES
    ) -> dict[str, Any]:
        path = require_project(project_id)
        safe_id = _safe_project_id(project_id)
        target_dir = uploads_root / safe_id
        target_dir.mkdir(parents=True, exist_ok=True)
        manager = ImportManager(import_registry, projects_root / safe_id / "imports")
        saved_pdfs: list[Path] = []
        assets: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for upload in files:
            filename = Path(upload.filename or "upload.bin").name
            target = target_dir / filename
            with target.open("wb") as handle:
                shutil.copyfileobj(upload.file, handle)
            try:
                asset = manager.import_file(target, upload.content_type)
                assets.append(_jsonable(asdict(asset)))
                if asset.format_id == "pdf":
                    saved_pdfs.append(target)
            except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
                errors.append({"filename": filename, "error": str(exc)})
        session_payload = None
        if saved_pdfs:
            index_data, session = import_into_project(path, saved_pdfs)
            session_payload = _jsonable(asdict(session))
            summary_payload = _jsonable(summarize(index_data))
        else:
            summary_payload = _jsonable(summarize(load_index(path)))
        if not assets and errors:
            raise HTTPException(
                status_code=400, detail={"message": "Inga filer kunde importeras", "files": errors}
            )
        return {
            "summary": summary_payload,
            "session": session_payload,
            "assets": assets,
            "errors": errors,
        }

    @app.get("/api/projects/{project_id}/imports")
    def list_imported_assets(project_id: str) -> list[dict[str, Any]]:
        require_project(project_id)
        manifest_dir = projects_root / _safe_project_id(project_id) / "imports"
        if not manifest_dir.exists():
            return []
        return [
            json.loads(item.read_text(encoding="utf-8"))
            for item in sorted(manifest_dir.glob("*.json"))
        ]

    @app.get("/api/projects/{project_id}/imports/{checksum}")
    def get_imported_asset(project_id: str, checksum: str) -> dict[str, Any]:
        require_project(project_id)
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum.lower()):
            raise HTTPException(status_code=400, detail="Ogiltig checksumma")
        manifest = (
            projects_root / _safe_project_id(project_id) / "imports" / f"{checksum.lower()}.json"
        )
        if not manifest.exists():
            raise HTTPException(status_code=404, detail="Importerad tillgång finns inte")
        return json.loads(manifest.read_text(encoding="utf-8"))

    @app.get("/api/projects/{project_id}/imports/{checksum}/file")
    def get_imported_asset_file(project_id: str, checksum: str) -> FileResponse:
        asset = get_imported_asset(project_id, checksum)
        candidate = uploads_root / _safe_project_id(project_id) / Path(asset["filename"]).name
        if not candidate.exists():
            raise HTTPException(status_code=404, detail="Källfilen finns inte")
        return FileResponse(
            candidate, media_type=asset.get("media_type"), filename=asset["filename"]
        )

    def geometry_state_path(project_id: str, checksum: str) -> Path:
        return projects_root / _safe_project_id(project_id) / "geometry-state" / f"{checksum}.json"

    def load_geometry_state(project_id: str, checksum: str) -> dict[str, Any]:
        path = geometry_state_path(project_id, checksum)
        if not path.exists():
            return {"layers": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_geometry_state(project_id: str, checksum: str, state: dict[str, Any]) -> None:
        path = geometry_state_path(project_id, checksum)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    @app.get("/api/projects/{project_id}/geometry/{checksum}")
    def get_geometry(project_id: str, checksum: str) -> dict[str, Any]:
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(as_payload(document))

    @app.get("/api/projects/{project_id}/geometry/{checksum}/objects/{object_id}")
    def get_geometry_object(project_id: str, checksum: str, object_id: str) -> dict[str, Any]:
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        item = find_object(document, object_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Geometriobjektet finns inte")
        return _jsonable(object_payload(item))

    @app.get("/api/projects/{project_id}/geometry/{checksum}/index")
    def get_geometry_index(project_id: str, checksum: str) -> dict[str, Any]:
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(geometry_index(document))

    @app.get("/api/projects/{project_id}/geometry/{checksum}/search")
    def search_geometry_objects(
        project_id: str,
        checksum: str,
        q: str | None = None,
        kind: str | None = None,
        layer: str | None = None,
        visible_only: bool = False,
        limit: int = 500,
    ) -> dict[str, Any]:
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        items = search_geometry(
            document,
            text=q,
            kinds=[kind] if kind else None,
            layers=[layer] if layer else None,
            visible_only=visible_only,
            limit=limit,
        )
        return {"count": len(items), "items": [_jsonable(object_payload(item)) for item in items]}

    @app.get("/api/projects/{project_id}/geometry/{checksum}/spatial-index")
    def get_spatial_index(project_id: str, checksum: str) -> dict[str, Any]:
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(spatial_index_summary(document))

    @app.get("/api/projects/{project_id}/geometry/{checksum}/nearest")
    def get_nearest_geometry(
        project_id: str,
        checksum: str,
        x: float,
        y: float,
        radius: float | None = None,
        kind: str | None = None,
        layer: str | None = None,
        visible_only: bool = False,
        limit: int = 25,
    ) -> dict[str, Any]:
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        hits = nearest_objects(
            document,
            x=x,
            y=y,
            max_distance=radius,
            kinds=[kind] if kind else None,
            layers=[layer] if layer else None,
            visible_only=visible_only,
            limit=limit,
        )
        return {
            "origin": {"x": x, "y": y},
            "count": len(hits),
            "items": [
                dict(_jsonable(object_payload(item)), distance=distance) for item, distance in hits
            ],
        }

    @app.get("/api/projects/{project_id}/geometry/{checksum}/bbox")
    def get_geometry_in_bbox(
        project_id: str,
        checksum: str,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        kind: str | None = None,
        layer: str | None = None,
        visible_only: bool = False,
        limit: int = 2000,
    ) -> dict[str, Any]:
        if min_x > max_x or min_y > max_y:
            raise HTTPException(status_code=400, detail="Ogiltig bounding box")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        items = objects_in_bbox(
            document,
            BoundingBox2D(min_x, min_y, max_x, max_y),
            kinds=[kind] if kind else None,
            layers=[layer] if layer else None,
            visible_only=visible_only,
            limit=limit,
        )
        return {"count": len(items), "items": [_jsonable(object_payload(item)) for item in items]}

    @app.get("/api/projects/{project_id}/geometry/{checksum}/objects/{object_id}/relations")
    def get_geometry_relations(
        project_id: str,
        checksum: str,
        object_id: str,
        radius: float = 100.0,
        limit: int = 50,
    ) -> dict[str, Any]:
        if radius < 0:
            raise HTTPException(status_code=400, detail="Radien måste vara positiv")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        try:
            return _jsonable(related_objects(document, object_id, radius=radius, limit=limit))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Geometriobjektet finns inte") from exc

    @app.get("/api/projects/{project_id}/geometry/{checksum}/topology")
    def get_geometry_topology(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(
            build_topology(
                document,
                tolerance=tolerance,
                layers=[layer] if layer else None,
                visible_only=visible_only,
            )
        )

    @app.get("/api/projects/{project_id}/geometry/{checksum}/objects/{object_id}/connections")
    def get_geometry_connections(
        project_id: str,
        checksum: str,
        object_id: str,
        tolerance: float = 0.001,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        try:
            return _jsonable(connected_objects(document, object_id, tolerance=tolerance))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Geometriobjektet finns inte") from exc

    @app.get("/api/projects/{project_id}/geometry/{checksum}/objects/{object_id}/trace")
    def trace_geometry_network(
        project_id: str,
        checksum: str,
        object_id: str,
        tolerance: float = 0.001,
        max_depth: int | None = None,
        stop_at_junctions: bool = False,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        if max_depth is not None and max_depth < 0:
            raise HTTPException(status_code=400, detail="Maxdjup får inte vara negativt")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        try:
            return _jsonable(
                trace_network(
                    document,
                    object_id,
                    tolerance=tolerance,
                    max_depth=max_depth,
                    stop_at_junctions=stop_at_junctions,
                    layers=[layer] if layer else None,
                    visible_only=visible_only,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Geometriobjektet finns inte") from exc

    @app.get("/api/projects/{project_id}/geometry/{checksum}/segments")
    def get_geometry_segments(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(
            segment_network(
                document,
                tolerance=tolerance,
                layers=[layer] if layer else None,
                visible_only=visible_only,
            )
        )

    @app.get("/api/projects/{project_id}/geometry/{checksum}/systems")
    def get_geometry_systems(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(
            identify_systems(
                document,
                tolerance=tolerance,
                layers=[layer] if layer else None,
                visible_only=visible_only,
            )
        )

    @app.get("/api/projects/{project_id}/geometry/{checksum}/objects/{object_id}/system")
    def get_geometry_object_system(
        project_id: str,
        checksum: str,
        object_id: str,
        tolerance: float = 0.001,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        try:
            return _jsonable(object_system(document, object_id, tolerance=tolerance))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Geometriobjektet finns inte") from exc

    @app.get("/api/projects/{project_id}/geometry/{checksum}/observations")
    def get_geometry_observations(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        association_radius: float = 100.0,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        if association_radius < 0:
            raise HTTPException(status_code=400, detail="Kopplingsradien får inte vara negativ")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(
            discover_system_observations(
                document,
                tolerance=tolerance,
                association_radius=association_radius,
                layers=[layer] if layer else None,
                visible_only=visible_only,
            )
        )

    @app.get("/api/projects/{project_id}/geometry/{checksum}/observation-candidates")
    def get_consolidated_geometry_observations(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        association_radius: float = 100.0,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        if association_radius < 0:
            raise HTTPException(status_code=400, detail="Kopplingsradien får inte vara negativ")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        return _jsonable(
            consolidate_observations(
                document,
                tolerance=tolerance,
                association_radius=association_radius,
                layers=[layer] if layer else None,
                visible_only=visible_only,
            )
        )

    @app.get("/api/projects/{project_id}/geometry/{checksum}/systems/{system_id}/observations")
    def get_system_observations(
        project_id: str,
        checksum: str,
        system_id: str,
        tolerance: float = 0.001,
        association_radius: float = 100.0,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        if association_radius < 0:
            raise HTTPException(status_code=400, detail="Kopplingsradien får inte vara negativ")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        try:
            return _jsonable(
                system_observations(
                    document,
                    system_id,
                    tolerance=tolerance,
                    association_radius=association_radius,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Geometrisystemet finns inte") from exc

    @app.patch("/api/projects/{project_id}/geometry/{checksum}/layers/{layer_name}")
    def update_layer_state(
        project_id: str, checksum: str, layer_name: str, payload: LayerStateInput
    ) -> dict[str, Any]:
        get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        layers = state.setdefault("layers", {})
        current = layers.setdefault(layer_name, {"visible": True, "locked": False})
        if payload.visible is not None:
            current["visible"] = payload.visible
        if payload.locked is not None:
            current["locked"] = payload.locked
        save_geometry_state(project_id, checksum, state)
        return get_geometry(project_id, checksum)

    @app.get("/api/projects/{project_id}/selection")
    def get_selection(project_id: str) -> dict[str, Any]:
        require_project(project_id)
        path = projects_root / _safe_project_id(project_id) / "selection.json"
        if not path.exists():
            return {"source_checksum": None, "object_ids": [], "updated_at": None}
        return json.loads(path.read_text(encoding="utf-8"))

    @app.put("/api/projects/{project_id}/selection")
    def update_selection(project_id: str, payload: SelectionInput) -> dict[str, Any]:
        require_project(project_id)
        asset = get_imported_asset(project_id, payload.source_checksum)
        state = load_geometry_state(project_id, payload.source_checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        valid_ids = {item.object_id for item in document.objects}
        requested = [item for item in payload.object_ids if item in valid_ids]
        current = get_selection(project_id)
        existing = (
            list(current.get("object_ids") or [])
            if current.get("source_checksum") == payload.source_checksum
            else []
        )
        if payload.mode == "add":
            selected = list(dict.fromkeys(existing + requested))
        elif payload.mode == "remove":
            selected = [item for item in existing if item not in set(requested)]
        elif payload.mode == "clear":
            selected = []
        else:
            selected = requested
        result = {
            "source_checksum": payload.source_checksum,
            "object_ids": selected,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        path = projects_root / _safe_project_id(project_id) / "selection.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    @app.get("/api/projects/{project_id}/dwg/{checksum}/adapter-status")
    def get_dwg_adapter_status(project_id: str, checksum: str) -> dict[str, Any]:
        asset = get_imported_asset(project_id, checksum)
        if asset.get("format_id") != "dwg":
            raise HTTPException(status_code=400, detail="Tillgången är inte en DWG")
        candidate = uploads_root / _safe_project_id(project_id) / Path(asset["filename"]).name
        return dwg_adapter_status(candidate)

    @app.post("/api/projects/{project_id}/analysis/claims")
    def analyze_claims(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        claims, _ = extract_project_claims(path)
        fusion, _ = fuse_project(path)
        return {
            "claims": _jsonable(summarize_claim_candidates(claims)),
            "fusion": _jsonable(summarize_fusion(fusion)),
        }

    @app.get("/api/projects/{project_id}/claims")
    def get_claims(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        claim_file = path.with_name("crow-claim-candidates.json")
        fusion_file = path.with_name("crow-knowledge-fusion.json")
        if not claim_file.exists() or not fusion_file.exists():
            return {
                "analyzed": False,
                "summary": {"candidates": 0, "clusters": 0, "conflicting": 0, "review_required": 0},
                "clusters": [],
            }

        index_data = load_index(path)
        claims = load_claim_candidates(claim_file)
        fusion = load_fusion_result(fusion_file)
        by_id = {candidate.id: candidate for candidate in claims.candidates}
        documents = {document.id: document for document in index_data.documents}
        clusters: list[dict[str, Any]] = []
        for cluster in fusion.clusters:
            cluster_candidates = []
            for candidate_id in cluster.candidate_ids:
                candidate = by_id.get(candidate_id)
                if candidate is None:
                    continue
                document = documents.get(candidate.provenance.document_id)
                cluster_candidates.append(
                    {
                        **_jsonable(asdict(candidate)),
                        "document_filename": document.filename
                        if document
                        else candidate.provenance.document_id,
                    }
                )
            clusters.append(
                {
                    **_jsonable(asdict(cluster)),
                    "candidates": cluster_candidates,
                    "requires_review": cluster.status.value == "conflicting"
                    or any(
                        float(candidate["confidence"]) < 0.8 for candidate in cluster_candidates
                    ),
                }
            )
        review_required = sum(bool(cluster["requires_review"]) for cluster in clusters)
        return {
            "analyzed": True,
            "summary": {
                "candidates": len(claims.candidates),
                "clusters": len(fusion.clusters),
                "conflicting": fusion.conflicting_count,
                "review_required": review_required,
            },
            "clusters": clusters,
        }

    @app.get("/api/projects/{project_id}/authority")
    def get_authority(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        index_data = load_index(path)
        resolution_file = path.with_name("crow-authority-resolution.json")
        accepted_file = path.with_name("crow-accepted-claims.json")
        defaults = {
            "drawing": "drawing",
            "technical_specification": "technical_description",
            "af": "administrative_specifications",
            "estimate": "priced_bill",
            "quotation": "tender",
        }
        documents = [
            {
                "document_id": item.id,
                "filename": item.filename,
                "title": item.metadata.title or item.filename,
                "authority_type": defaults.get(item.document_type.value, "unknown"),
                "issue_date": None,
                "revision": item.metadata.revision or item.fingerprint.revision,
            }
            for item in index_data.active_documents
        ]
        payload: dict[str, Any] = {
            "resolved": resolution_file.exists(),
            "documents": documents,
            "summary": {"decisions": 0, "resolved": 0, "unresolved": 0},
            "decisions": [],
            "accepted": {"accepted": 0, "pending": 0},
        }
        if resolution_file.exists():
            resolution = load_resolution(resolution_file)
            payload["summary"] = _jsonable(summarize_resolution(resolution))
            payload["decisions"] = [_jsonable(asdict(item)) for item in resolution.decisions]
        if accepted_file.exists():
            accepted = load_accepted_claims(accepted_file)
            payload["accepted"] = _jsonable(summarize_accepted_claims(accepted))
        return payload

    @app.post("/api/projects/{project_id}/authority/resolve")
    def resolve_authority(project_id: str, payload: AuthorityResolveRequest) -> dict[str, Any]:
        path = require_project(project_id)
        fusion_file = path.with_name("crow-knowledge-fusion.json")
        if not fusion_file.exists():
            raise HTTPException(
                status_code=409, detail="Kör Claim-analys innan auktoritetsprövning"
            )
        index_data = load_index(path)
        valid_ids = {item.id for item in index_data.active_documents}
        if any(item.document_id not in valid_ids for item in payload.documents):
            raise HTTPException(status_code=400, detail="Manifestet innehåller ett okänt dokument")
        manifest = {
            "framework_id": "ab04.default",
            "framework_name": "AB 04 default hierarchy",
            "source": "Crow Workbench authority review",
            "documents": [item.model_dump() for item in payload.documents],
        }
        manifest_file = path.with_name("crow-authority-manifest.json")
        import json

        manifest_file.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        resolution, _ = resolve_project(path, manifest_file)
        accepted, _ = build_project_accepted_claims(path)
        return {
            "summary": _jsonable(summarize_resolution(resolution)),
            "accepted": _jsonable(summarize_accepted_claims(accepted)),
            "decisions": [_jsonable(asdict(item)) for item in resolution.decisions],
        }

    @app.get("/api/projects/{project_id}/technical-deltas")
    def get_technical_deltas(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        files = {
            "baseline": path.with_name("crow-technical-baseline.json"),
            "decisions": path.with_name("crow-technical-decisions.json"),
            "reviews": path.with_name("crow-technical-reviews.json"),
            "deltas": path.with_name("crow-technical-deltas.json"),
        }
        prerequisites = {name: file.exists() for name, file in files.items() if name != "deltas"}
        payload: dict[str, Any] = {
            "ready": all(prerequisites.values()),
            "generated": files["deltas"].exists(),
            "prerequisites": prerequisites,
            "summary": {"total": 0, "changed": 0, "by_type": {}},
            "deltas": [],
        }
        if files["deltas"].exists():
            delta_set = load_delta_set(files["deltas"])
            payload["summary"] = _jsonable(summarize_deltas(delta_set))
            payload["deltas"] = [_jsonable(asdict(item)) for item in delta_set.deltas]
        return payload

    @app.post("/api/projects/{project_id}/technical-deltas/build")
    def build_technical_deltas(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        baseline = path.with_name("crow-technical-baseline.json")
        missing = [
            name
            for name, file in {
                "teknisk baseline": baseline,
                "tekniska beslut": path.with_name("crow-technical-decisions.json"),
                "teknisk review": path.with_name("crow-technical-reviews.json"),
            }.items()
            if not file.exists()
        ]
        if missing:
            raise HTTPException(
                status_code=409,
                detail="Technical Delta kan inte byggas. Saknas: " + ", ".join(missing),
            )
        delta_set, _ = build_project_deltas(path, baseline)
        return {
            "summary": _jsonable(summarize_deltas(delta_set)),
            "deltas": [_jsonable(asdict(item)) for item in delta_set.deltas],
        }

    @app.get("/api/projects/{project_id}/commercial")
    def get_commercial(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        files = {
            "technical_deltas": path.with_name("crow-technical-deltas.json"),
            "scope_rules": path.with_name("crow-scope-rules.json"),
            "price_book": path.with_name("crow-price-book.json"),
            "adjustment_profile": path.with_name("crow-adjustment-profile.json"),
            "scope_impacts": path.with_name("crow-scope-impacts.json"),
            "commercial_impacts": path.with_name("crow-commercial-impacts.json"),
            "adjustments": path.with_name("crow-commercial-adjustments.json"),
            "review": path.with_name("crow-commercial-review.json"),
            "estimate": path.with_name("crow-estimate.json"),
        }
        payload: dict[str, Any] = {
            "prerequisites": {
                key: file.exists()
                for key, file in files.items()
                if key in {"technical_deltas", "scope_rules", "price_book", "adjustment_profile"}
            },
            "generated": {
                key: file.exists()
                for key, file in files.items()
                if key
                not in {"technical_deltas", "scope_rules", "price_book", "adjustment_profile"}
            },
            "scope": None,
            "commercial": None,
            "adjustments": None,
            "review": None,
            "estimate": None,
            "impacts": [],
            "lines": [],
        }
        if files["scope_impacts"].exists():
            value = load_scope_impacts(files["scope_impacts"])
            payload["scope"] = _jsonable(summarize_scope_impacts(value))
        if files["commercial_impacts"].exists():
            value = load_commercial_impacts(files["commercial_impacts"])
            payload["commercial"] = _jsonable(summarize_commercial_impacts(value))
            payload["impacts"] = [_jsonable(asdict(item)) for item in value.impacts]
        if files["adjustments"].exists():
            value = load_adjusted(files["adjustments"])
            payload["adjustments"] = _jsonable(summarize_adjustments(value))
        if files["review"].exists():
            value = load_review(files["review"])
            payload["review"] = _jsonable(summarize_review(value))
            payload["review_history"] = [_jsonable(asdict(item)) for item in value.history]
        if files["estimate"].exists():
            value = load_estimate(files["estimate"])
            payload["estimate"] = _jsonable(summarize_estimate(value))
            payload["lines"] = [_jsonable(asdict(item)) for item in value.lines]
        return payload

    @app.post("/api/projects/{project_id}/commercial/profile/example")
    def initialize_commercial_profile(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        write_rule_set_template(path.with_name("crow-scope-rules.json"))
        write_price_book_template(path.with_name("crow-price-book.json"))
        write_profile_template(path.with_name("crow-adjustment-profile.json"))
        return {"initialized": True, "profile": "example"}

    @app.post("/api/projects/{project_id}/commercial/build")
    def build_commercial(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        required = {
            "Technical Delta": path.with_name("crow-technical-deltas.json"),
            "scope-regler": path.with_name("crow-scope-rules.json"),
            "prislista": path.with_name("crow-price-book.json"),
            "påslagsprofil": path.with_name("crow-adjustment-profile.json"),
        }
        missing = [name for name, file in required.items() if not file.exists()]
        if missing:
            raise HTTPException(
                status_code=409,
                detail="Kommersiell beräkning kan inte köras. Saknas: " + ", ".join(missing),
            )
        scope, _ = build_project_scope_impacts(path, required["scope-regler"])
        commercial, _ = build_project_commercial_impacts(path, required["prislista"])
        adjusted, _ = apply_project_adjustments(path, required["påslagsprofil"])
        review, _ = initialize_project_commercial_review(path)
        return {
            "scope": _jsonable(summarize_scope_impacts(scope)),
            "commercial": _jsonable(summarize_commercial_impacts(commercial)),
            "adjustments": _jsonable(summarize_adjustments(adjusted)),
            "review": _jsonable(summarize_review(review)),
        }

    @app.post("/api/projects/{project_id}/commercial/review")
    def review_commercial(project_id: str, payload: CommercialReviewRequest) -> dict[str, Any]:
        path = require_project(project_id)
        review_file = path.with_name("crow-commercial-review.json")
        if not review_file.exists():
            raise HTTPException(status_code=409, detail="Kör kommersiell beräkning först")
        try:
            status = CommercialReviewStatus(payload.status)
            review, _ = update_project_commercial_review(
                path, status, payload.reviewer, payload.reason, datetime.now(UTC)
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if review.is_approved:
            build_project_estimate(path, estimate_id=f"estimate:{project_id}")
        return _jsonable(summarize_review(review))

    @app.get("/api/projects/{project_id}/documents/{document_id}")
    def get_document(project_id: str, document_id: str) -> dict[str, Any]:
        index_data = load_index(require_project(project_id))
        document = next((item for item in index_data.documents if item.id == document_id), None)
        if document is None:
            raise HTTPException(status_code=404, detail="Dokumentet finns inte")
        pages = [page for page in index_data.pages if page.document_id == document_id]
        regions = [region for region in index_data.regions if region.document_id == document_id]
        return {
            "document": _jsonable(asdict(document)),
            "pages": [_jsonable(asdict(page)) for page in pages],
            "regions": [_jsonable(asdict(region)) for region in regions],
        }

    @app.get("/api/projects/{project_id}/documents/{document_id}/file")
    def get_document_file(project_id: str, document_id: str) -> FileResponse:
        index_data = load_index(require_project(project_id))
        document = next((item for item in index_data.documents if item.id == document_id), None)
        if document is None or not document.path.exists():
            raise HTTPException(status_code=404, detail="Dokumentfilen finns inte")
        return FileResponse(document.path, media_type="application/pdf", filename=document.filename)

    def _load_json_if_exists(path: Path) -> dict[str, Any] | list[Any] | None:
        if not path.exists():
            return None
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/projects/{project_id}/workbench")
    def get_workbench(project_id: str) -> dict[str, Any]:
        path = require_project(project_id)
        index_data = load_index(path)
        summary = _jsonable(summarize(index_data))
        files = {item.name: item for item in path.parent.glob("crow-*.json")}
        claims = _load_json_if_exists(path.with_name("crow-claim-candidates.json")) or {}
        fusion = _load_json_if_exists(path.with_name("crow-knowledge-fusion.json")) or {}
        authority = _load_json_if_exists(path.with_name("crow-authority-resolution.json")) or {}
        accepted = _load_json_if_exists(path.with_name("crow-accepted-claims.json")) or {}
        deltas = _load_json_if_exists(path.with_name("crow-technical-deltas.json")) or {}
        commercial = _load_json_if_exists(path.with_name("crow-commercial-impacts.json")) or {}
        review = _load_json_if_exists(path.with_name("crow-commercial-review.json")) or {}
        estimate = _load_json_if_exists(path.with_name("crow-estimate.json")) or {}

        candidates = claims.get("candidates", []) if isinstance(claims, dict) else []
        clusters = fusion.get("clusters", []) if isinstance(fusion, dict) else []
        decisions = authority.get("decisions", []) if isinstance(authority, dict) else []
        accepted_items = (
            accepted.get("accepted_claims", accepted.get("claims", []))
            if isinstance(accepted, dict)
            else []
        )
        pending_items = (
            accepted.get("pending_claims", accepted.get("pending", []))
            if isinstance(accepted, dict)
            else []
        )
        delta_items = deltas.get("deltas", []) if isinstance(deltas, dict) else []
        commercial_items = (
            commercial.get("impacts", commercial.get("items", []))
            if isinstance(commercial, dict)
            else []
        )
        estimate_lines = estimate.get("lines", []) if isinstance(estimate, dict) else []

        conflict_count = sum(1 for item in clusters if str(item.get("status", "")) == "conflicting")
        low_confidence = sum(
            1 for item in candidates if float(item.get("confidence", 1) or 0) < 0.8
        )
        unresolved_commercial = sum(
            1 for item in commercial_items if item.get("pricing_status") != "priced"
        )
        review_items = []
        for item in clusters:
            if str(item.get("status", "")) == "conflicting":
                review_items.append(
                    {
                        "kind": "conflict",
                        "severity": "high",
                        "title": f"{item.get('subject', 'Claim')} · {item.get('predicate', '')}",
                        "entity_id": item.get("id"),
                        "reason": "Motstridiga värden",
                    }
                )
        for item in candidates:
            if float(item.get("confidence", 1) or 0) < 0.8:
                review_items.append(
                    {
                        "kind": "claim",
                        "severity": "medium",
                        "title": item.get("normalized_value")
                        or item.get("value")
                        or "Claim candidate",
                        "entity_id": item.get("id"),
                        "reason": "Låg confidence",
                    }
                )
        for item in commercial_items:
            if item.get("pricing_status") != "priced":
                review_items.append(
                    {
                        "kind": "commercial",
                        "severity": "high",
                        "title": item.get("description", "Kommersiell post"),
                        "entity_id": item.get("id"),
                        "reason": "Olöst prissättning",
                    }
                )

        nodes = [
            {
                "id": f"project:{project_id}",
                "type": "project",
                "label": summary.get("project_name", project_id),
                "status": "active",
            }
        ]
        edges = []
        for document in index_data.active_documents:
            nodes.append(
                {
                    "id": document.id,
                    "type": "document",
                    "label": document.filename,
                    "status": "active",
                    "meta": {"pages": document.fingerprint.page_count},
                }
            )
            edges.append(
                {"source": f"project:{project_id}", "target": document.id, "relation": "contains"}
            )
        for item in candidates[:250]:
            node_id = item.get("id")
            if not node_id:
                continue
            nodes.append(
                {
                    "id": node_id,
                    "type": "claim",
                    "label": str(item.get("normalized_value") or item.get("value") or "Claim"),
                    "status": "pending",
                    "meta": {"confidence": item.get("confidence")},
                }
            )
            prov = item.get("provenance", {}) or {}
            doc_id = prov.get("document_id")
            if doc_id:
                edges.append({"source": doc_id, "target": node_id, "relation": "supports"})
        for item in decisions[:250]:
            node_id = item.get("id")
            if not node_id:
                continue
            nodes.append(
                {
                    "id": node_id,
                    "type": "decision",
                    "label": str(item.get("status") or "Authority decision"),
                    "status": str(item.get("status") or "pending"),
                }
            )
            for claim_id in item.get("candidate_ids", item.get("claim_candidate_ids", [])) or []:
                edges.append({"source": claim_id, "target": node_id, "relation": "resolved_by"})
        for item in delta_items[:250]:
            node_id = item.get("id")
            if not node_id:
                continue
            nodes.append(
                {
                    "id": node_id,
                    "type": "delta",
                    "label": item.get("title", "Technical Delta"),
                    "status": item.get("delta_type", "changed"),
                }
            )
            prov = item.get("provenance", {}) or {}
            for claim_id in prov.get("accepted_claim_ids", []) or []:
                edges.append({"source": claim_id, "target": node_id, "relation": "changes"})
        for item in commercial_items[:250]:
            node_id = item.get("id")
            if not node_id:
                continue
            nodes.append(
                {
                    "id": node_id,
                    "type": "commercial",
                    "label": item.get("description", "Commercial Impact"),
                    "status": item.get("pricing_status", "pending"),
                    "meta": {"amount": item.get("amount")},
                }
            )
            prov = item.get("provenance", {}) or {}
            delta_id = prov.get("technical_delta_id") or item.get("technical_delta_id")
            if delta_id:
                edges.append({"source": delta_id, "target": node_id, "relation": "priced_as"})
        for item in estimate_lines[:250]:
            node_id = item.get("id") or f"estimate-line:{item.get('line_number', 'x')}"
            nodes.append(
                {
                    "id": node_id,
                    "type": "estimate",
                    "label": item.get("description", "Estimate line"),
                    "status": "approved",
                    "meta": {"total": item.get("total_amount")},
                }
            )
            source = item.get("commercial_impact_id")
            if source:
                edges.append({"source": source, "target": node_id, "relation": "estimated_as"})

        stages = [
            ("documents", len(index_data.active_documents), True),
            ("claims", len(candidates), bool(claims)),
            ("authority", len(decisions), bool(authority)),
            ("technical", len(delta_items), bool(deltas)),
            ("commercial", len(commercial_items), bool(commercial)),
            ("estimate", len(estimate_lines), bool(estimate)),
        ]
        completed = sum(1 for _, _, ready in stages if ready)
        return {
            "summary": summary,
            "health": {
                "score": round(completed / len(stages) * 100),
                "stages": [{"id": a, "count": b, "ready": c} for a, b, c in stages],
            },
            "counts": {
                "documents": len(index_data.active_documents),
                "claims": len(candidates),
                "conflicts": conflict_count,
                "low_confidence": low_confidence,
                "accepted": len(accepted_items),
                "pending": len(pending_items),
                "deltas": len(delta_items),
                "commercial": len(commercial_items),
                "unresolved_commercial": unresolved_commercial,
                "estimate_lines": len(estimate_lines),
                "reviews": len(review_items),
            },
            "review_items": review_items[:200],
            "graph": {"nodes": nodes, "edges": edges},
            "timeline": [
                {
                    "stage": stage,
                    "status": "complete" if ready else "waiting",
                    "count": count,
                    "order": idx + 1,
                }
                for idx, (stage, count, ready) in enumerate(stages)
            ],
            "artifacts": sorted(files),
            "commercial_review": review,
        }

    def building_graph_service(project_id: str) -> BuildingGraphService:
        require_project(project_id)
        path = projects_root / _safe_project_id(project_id) / "building-graph" / "graph.json"
        return BuildingGraphService(GraphRepository(path))

    def building_graph_repository(project_id: str) -> GraphRepository:
        require_project(project_id)
        path = projects_root / _safe_project_id(project_id) / "building-graph" / "graph.json"
        return GraphRepository(path)

    def identity_review_file(project_id: str) -> Path:
        require_project(project_id)
        return (
            projects_root
            / _safe_project_id(project_id)
            / "building-graph"
            / "identity-reviews.json"
        )

    def graph_audit_directory(project_id: str) -> Path:
        require_project(project_id)
        return projects_root / _safe_project_id(project_id) / "building-graph" / "audits"

    def serialize_graph_audit(project_id: str) -> dict[str, Any]:
        graph = building_graph_repository(project_id).load()
        result = VentGraphAudit().audit(graph)
        graph_payload = json.dumps(graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        graph_checksum = sha256(graph_payload.encode("utf-8")).hexdigest()
        return {
            "project_id": _safe_project_id(project_id),
            "graph_checksum": graph_checksum,
            "summary": result.summary,
            "metadata": result.metadata,
            "findings": [_jsonable(asdict(item)) for item in result.findings],
        }

    def persist_graph_audit(project_id: str) -> tuple[dict[str, Any], bool]:
        payload = serialize_graph_audit(project_id)
        audit_key = "|".join(
            (payload["graph_checksum"], str(payload["metadata"]["rule_version"]))
        )
        audit_id = f"vent:audit:{sha256(audit_key.encode('utf-8')).hexdigest()[:20]}"
        payload["audit_id"] = audit_id
        payload["created_at"] = datetime.now(UTC).isoformat()
        directory = graph_audit_directory(project_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{audit_id.replace(':', '-')}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            return existing, False
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
        return payload, True

    def graph_audit_path(project_id: str, audit_id: str) -> Path:
        safe_audit_id = audit_id.replace(":", "-")
        path = graph_audit_directory(project_id) / f"{safe_audit_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Granskningskörningen finns inte")
        return path

    def audit_finding_review_file(project_id: str) -> Path:
        require_project(project_id)
        return (
            projects_root
            / _safe_project_id(project_id)
            / "building-graph"
            / "audit-finding-reviews.json"
        )

    def load_audit_finding_reviews(project_id: str) -> list[dict[str, Any]]:
        path = audit_finding_review_file(project_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise HTTPException(status_code=500, detail="Ogiltigt finding-granskningsregister")
        return raw

    def save_audit_finding_reviews(project_id: str, reviews: list[dict[str, Any]]) -> None:
        path = audit_finding_review_file(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(reviews, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)

    def load_identity_reviews(project_id: str) -> list[dict[str, Any]]:
        path = identity_review_file(project_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise HTTPException(status_code=500, detail="Ogiltigt granskningsregister")
        return raw

    def save_identity_reviews(project_id: str, reviews: list[dict[str, Any]]) -> None:
        path = identity_review_file(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(reviews, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)

    @app.get("/api/graph/relation-types")
    def graph_relation_types() -> dict[str, Any]:
        return {"count": len(ALLOWED_RELATIONS), "items": sorted(ALLOWED_RELATIONS)}

    @app.get("/api/projects/{project_id}/graph")
    def get_building_graph(project_id: str) -> dict[str, Any]:
        return building_graph_service(project_id).graph()

    @app.post("/api/projects/{project_id}/graph/evidence", status_code=201)
    def create_graph_evidence(project_id: str, payload: GraphEvidenceInput) -> dict[str, Any]:
        try:
            return building_graph_service(project_id).create_evidence(**payload.model_dump())
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/graph/objects", status_code=201)
    def create_graph_object(project_id: str, payload: GraphObjectInput) -> dict[str, Any]:
        try:
            return building_graph_service(project_id).create_object(**payload.model_dump())
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/projects/{project_id}/graph/objects/{object_id}")
    def update_graph_object(
        project_id: str, object_id: str, payload: GraphObjectUpdate
    ) -> dict[str, Any]:
        try:
            return building_graph_service(project_id).update_object(
                object_id, **payload.model_dump()
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Grafobjektet finns inte") from exc

    @app.post("/api/projects/{project_id}/graph/relations", status_code=201)
    def create_graph_relation(project_id: str, payload: GraphRelationInput) -> dict[str, Any]:
        try:
            return building_graph_service(project_id).create_relation(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Refererat grafobjekt eller evidens saknas: {exc}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


    @app.get("/api/projects/{project_id}/graph/audit")
    def get_graph_audit(project_id: str) -> dict[str, Any]:
        return serialize_graph_audit(project_id)

    @app.post("/api/projects/{project_id}/graph/audit-runs", status_code=201)
    def create_graph_audit_run(project_id: str, response: Response) -> dict[str, Any]:
        payload, created = persist_graph_audit(project_id)
        if not created:
            response.status_code = 200
        return {"created": created, "audit": payload}

    @app.get("/api/projects/{project_id}/graph/audit-runs")
    def list_graph_audit_runs(project_id: str) -> dict[str, Any]:
        directory = graph_audit_directory(project_id)
        if not directory.exists():
            return {"count": 0, "items": []}
        items = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("vent-audit-*.json"))
        ]
        items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return {"count": len(items), "items": items}

    @app.get("/api/projects/{project_id}/graph/audit-finding-reviews")
    def list_audit_finding_reviews(project_id: str, audit_id: str | None = None) -> dict[str, Any]:
        reviews = load_audit_finding_reviews(project_id)
        if audit_id is not None:
            reviews = [item for item in reviews if item.get("audit_id") == audit_id]
        return {"count": len(reviews), "items": reviews}

    @app.post(
        "/api/projects/{project_id}/graph/audit-runs/{audit_id}/findings/{finding_id}/review",
        status_code=201,
    )
    def review_audit_finding(
        project_id: str,
        audit_id: str,
        finding_id: str,
        payload: AuditFindingReviewRequest,
    ) -> dict[str, Any]:
        audit = json.loads(graph_audit_path(project_id, audit_id).read_text(encoding="utf-8"))
        finding = next(
            (item for item in audit.get("findings", []) if item.get("finding_id") == finding_id),
            None,
        )
        if finding is None:
            raise HTTPException(status_code=404, detail="Finding finns inte i granskningskörningen")
        reviews = load_audit_finding_reviews(project_id)
        if any(
            item.get("audit_id") == audit_id and item.get("finding_id") == finding_id
            for item in reviews
        ):
            raise HTTPException(status_code=409, detail="Finding är redan granskad")
        decided_at = payload.decided_at or datetime.now(UTC).isoformat()
        review_key = "|".join(
            (audit_id, finding_id, payload.decision, payload.reviewer, decided_at)
        )
        review_digest = sha256(review_key.encode("utf-8")).hexdigest()[:20]
        review = {
            "review_id": f"vent:finding-review:{review_digest}",
            "project_id": _safe_project_id(project_id),
            "audit_id": audit_id,
            "graph_checksum": audit.get("graph_checksum"),
            "finding_id": finding_id,
            "rule_id": finding.get("rule_id"),
            "decision": payload.decision,
            "reviewer": payload.reviewer,
            "rationale": payload.rationale,
            "decided_at": decided_at,
            "finding_snapshot": finding,
            "metadata": {
                "audit_mutated": False,
                "graph_mutated": False,
                "automatic_correction_performed": False,
            },
        }
        reviews.append(review)
        save_audit_finding_reviews(project_id, reviews)
        return review

    @app.get("/api/projects/{project_id}/graph/identity-candidates")
    def list_identity_candidates(project_id: str) -> dict[str, Any]:
        graph = building_graph_repository(project_id).load()
        reviews = load_identity_reviews(project_id)
        reviewed_candidate_ids = {item["candidate_relation_id"] for item in reviews}
        candidates = [
            item
            for item in graph["relations"]
            if item.get("relation_type") == "same_as_candidate"
            and item.get("metadata", {}).get("status") == "review_required"
        ]
        pending = [item for item in candidates if item.get("id") not in reviewed_candidate_ids]
        return {
            "count": len(candidates),
            "pending_count": len(pending),
            "reviewed_count": len(candidates) - len(pending),
            "items": pending,
        }

    @app.get("/api/projects/{project_id}/graph/identity-reviews")
    def list_identity_reviews(project_id: str) -> dict[str, Any]:
        reviews = load_identity_reviews(project_id)
        return {"count": len(reviews), "items": reviews}

    @app.post(
        "/api/projects/{project_id}/graph/identity-candidates/{relation_id}/review",
        status_code=201,
    )
    def review_identity_candidate(
        project_id: str, relation_id: str, payload: IdentityReviewRequest
    ) -> dict[str, Any]:
        repository = building_graph_repository(project_id)
        graph = repository.load()
        relation = next(
            (item for item in graph["relations"] if item.get("id") == relation_id),
            None,
        )
        if relation is None:
            raise HTTPException(status_code=404, detail="Kandidatrelationen finns inte")
        reviews = load_identity_reviews(project_id)
        if any(item["candidate_relation_id"] == relation_id for item in reviews):
            raise HTTPException(status_code=409, detail="Kandidatrelationen är redan granskad")
        evidence_ids = relation.get("evidence_ids", [])
        evidence_record = next(
            (item for item in graph["evidence"] if item.get("id") in evidence_ids),
            None,
        )
        if evidence_record is None:
            raise HTTPException(status_code=409, detail="Kandidatrelationen saknar evidens")
        evidence_metadata = evidence_record.get("metadata", {})
        candidate = CanonicalRelation(
            canonical_id=relation["id"],
            source_id=relation["source_id"],
            relation_type=relation["relation_type"],
            target_id=relation["target_id"],
            confidence=float(relation.get("confidence", 1.0)),
            evidence=CanonicalEvidence(
                source_id=evidence_record["source_id"],
                source_kind=str(evidence_metadata.get("source_kind", "drawing_text")),
                locator=evidence_record.get("locator"),
                confidence=float(evidence_record.get("confidence", 1.0)),
                metadata=dict(evidence_metadata),
            ),
            metadata=dict(relation.get("metadata", {})),
        )
        try:
            result = IdentityReviewService().decide(
                candidate,
                decision=IdentityReviewDecision(payload.decision),
                reviewer=payload.reviewer,
                rationale=payload.rationale,
                decided_at=payload.decided_at,
            )
            persisted = CanonicalGraphBridge(building_graph_service(project_id)).persist_relation(
                result.resolved_relation
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        review_payload = asdict(result.review)
        review_payload["decision"] = result.review.decision.value
        review_payload["resolved_relation_id"] = persisted["relation"]["id"]
        reviews.append(review_payload)
        save_identity_reviews(project_id, reviews)
        return {"review": review_payload, "resolved_relation": persisted["relation"]}

    @app.post("/api/projects/{project_id}/graph/properties", status_code=201)
    def create_graph_property(project_id: str, payload: GraphPropertyInput) -> dict[str, Any]:
        try:
            return building_graph_service(project_id).create_property(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Refererat grafobjekt eller evidens saknas: {exc}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/graph/objects/{object_id}/neighbors")
    def graph_neighbors(
        project_id: str, object_id: str, relation_type: str | None = None
    ) -> dict[str, Any]:
        try:
            return building_graph_service(project_id).neighbors(object_id, relation_type)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Grafobjektet finns inte") from exc

    def reasoning_service(project_id: str) -> ReasoningService:
        require_project(project_id)
        path = projects_root / _safe_project_id(project_id) / "building-graph" / "graph.json"
        return ReasoningService(path)

    @app.get("/api/projects/{project_id}/reasoning/traverse/{object_id}")
    def reasoning_traverse(
        project_id: str,
        object_id: str,
        direction: str = "both",
        relation_types: str | None = None,
        max_depth: int | None = None,
    ) -> dict[str, Any]:
        try:
            types = (
                [item.strip() for item in relation_types.split(",") if item.strip()]
                if relation_types
                else None
            )
            return reasoning_service(project_id).traverse(
                object_id, direction=direction, relation_types=types, max_depth=max_depth
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Grafobjektet finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/reasoning/path")
    def reasoning_path(
        project_id: str,
        source_id: str,
        target_id: str,
        direction: str = "both",
        relation_types: str | None = None,
    ) -> dict[str, Any]:
        try:
            types = (
                [item.strip() for item in relation_types.split(",") if item.strip()]
                if relation_types
                else None
            )
            return reasoning_service(project_id).shortest_path(
                source_id, target_id, direction=direction, relation_types=types
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="Ett eller flera grafobjekt saknas"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/reasoning/impact/{object_id}")
    def reasoning_impact(
        project_id: str,
        object_id: str,
        relation_types: str | None = None,
        max_depth: int | None = None,
    ) -> dict[str, Any]:
        try:
            types = (
                [item.strip() for item in relation_types.split(",") if item.strip()]
                if relation_types
                else None
            )
            return reasoning_service(project_id).impact(
                object_id, relation_types=types, max_depth=max_depth
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Grafobjektet finns inte") from exc

    @app.get("/api/projects/{project_id}/reasoning/diagnostics")
    def reasoning_diagnostics(project_id: str) -> dict[str, Any]:
        return reasoning_service(project_id).diagnostics()

    def rule_service(project_id: str) -> RuleService:
        require_project(project_id)
        graph_path = projects_root / _safe_project_id(project_id) / "building-graph" / "graph.json"
        default_rules = (
            Path(__file__).resolve().parents[1] / "crow_reasoning" / "default_rules.json"
        )
        return RuleService(graph_path, default_rules)

    @app.get("/api/projects/{project_id}/reasoning/rules")
    def reasoning_rules(project_id: str) -> dict[str, Any]:
        service = rule_service(project_id)
        rules = service.load_rules()
        validation = service.validate_rules(rules)
        return {"schema": "crow-rule-pack-v0.1", "rules": rules, "validation": validation}

    @app.post("/api/projects/{project_id}/reasoning/rules/validate")
    def reasoning_validate_rules(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            rules = payload.get("rules", [])
            return rule_service(project_id).validate_rules(rules)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def finding_service(project_id: str) -> FindingService:
        require_project(project_id)
        path = projects_root / _safe_project_id(project_id) / "building-graph" / "findings.json"
        return FindingService(FindingRepository(path))

    @app.get("/api/projects/{project_id}/reasoning/findings")
    def reasoning_findings(
        project_id: str,
        status: str | None = None,
        severity: str | None = None,
        rule_id: str | None = None,
        object_id: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        if refresh:
            return rule_service(project_id).synchronize_findings()
        return finding_service(project_id).list(
            status=status, severity=severity, rule_id=rule_id, object_id=object_id
        )

    @app.post("/api/projects/{project_id}/reasoning/findings/synchronize")
    def reasoning_synchronize_findings(
        project_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            body = payload or {}
            rules = body.get("rules")
            return rule_service(project_id).synchronize_findings(
                rules, actor=str(body.get("actor", "rule-engine"))
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/projects/{project_id}/reasoning/findings/{finding_id}")
    def reasoning_update_finding(
        project_id: str, finding_id: str, payload: FindingStatusRequest
    ) -> dict[str, Any]:
        try:
            return finding_service(project_id).update_status(finding_id, **payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Finding finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/reasoning/findings/history")
    def reasoning_finding_history(project_id: str, finding_id: str | None = None) -> dict[str, Any]:
        return finding_service(project_id).history(finding_id)

    @app.get("/api/projects/{project_id}/reasoning/findings.csv")
    def reasoning_findings_csv(
        project_id: str,
        status: str | None = None,
        severity: str | None = None,
        rule_id: str | None = None,
        object_id: str | None = None,
    ) -> Response:
        content = finding_service(project_id).csv_export(
            status=status, severity=severity, rule_id=rule_id, object_id=object_id
        )
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{project_id}-findings.csv"'},
        )

    @app.post("/api/projects/{project_id}/reasoning/evaluate")
    def reasoning_evaluate(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return rule_service(project_id).evaluate(payload.get("rules", []))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def knowledge_runtime() -> KnowledgePackRuntime:
        return KnowledgePackRuntime(Path(__file__).resolve().parents[2] / "knowledge")

    @app.get("/api/knowledge-packs")
    def knowledge_packs() -> dict[str, Any]:
        return knowledge_runtime().registry()

    @app.get("/api/knowledge-packs/{pack_id}")
    def knowledge_pack(pack_id: str) -> dict[str, Any]:
        runtime = knowledge_runtime()
        try:
            pack = runtime._get(pack_id)
            validation = runtime.validate(pack)
            return {
                "manifest": pack["manifest"],
                "validation": {
                    "valid": validation.valid,
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                },
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Kunskapspaketet finns inte") from exc

    @app.post("/api/projects/{project_id}/reasoning/knowledge-packs/{pack_id}/evaluate")
    def evaluate_knowledge_pack(project_id: str, pack_id: str) -> dict[str, Any]:
        try:
            return rule_service(project_id).evaluate(knowledge_runtime().rules(pack_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Kunskapspaketet finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def inference_service(project_id: str) -> InferenceService:
        require_project(project_id)
        root = projects_root / _safe_project_id(project_id) / "building-graph"
        return InferenceService(root / "graph.json", root / "inferences.json")

    @app.get("/api/projects/{project_id}/inference/relations")
    def inference_relations(project_id: str, refresh: bool = False) -> dict[str, Any]:
        return inference_service(project_id).list(refresh=refresh)

    @app.post("/api/projects/{project_id}/inference/run")
    def inference_run(project_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            body = payload or {}
            return inference_service(project_id).run(
                body.get("rules"),
                persist=bool(body.get("persist", True)),
                max_iterations=int(body.get("max_iterations", 8)),
                force=bool(body.get("force", False)),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/inference/status")
    def inference_status(project_id: str) -> dict[str, Any]:
        return inference_service(project_id).status()

    @app.post("/api/projects/{project_id}/inference/invalidate")
    def inference_invalidate(
        project_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return inference_service(project_id).invalidate(
            reason=str((payload or {}).get("reason", "manual"))
        )

    @app.get("/api/projects/{project_id}/inference/runs")
    def inference_runs(project_id: str) -> dict[str, Any]:
        return inference_service(project_id).history()

    @app.get("/api/projects/{project_id}/inference/diff")
    def inference_diff(
        project_id: str, from_run: int | None = None, to_run: int | None = None
    ) -> dict[str, Any]:
        try:
            return inference_service(project_id).diff(from_run=from_run, to_run=to_run)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Inferenskörningen finns inte") from exc

    @app.get("/api/projects/{project_id}/inference/query")
    def inference_query(
        project_id: str,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
        minimum_confidence: float = 0.0,
        refresh: bool = False,
    ) -> dict[str, Any]:
        return inference_service(project_id).query(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            minimum_confidence=minimum_confidence,
            refresh=refresh,
        )

    @app.get("/api/projects/{project_id}/inference/conflicts")
    def inference_conflicts(project_id: str, refresh: bool = False) -> dict[str, Any]:
        return inference_service(project_id).conflicts(refresh=refresh)

    @app.get("/api/projects/{project_id}/inference/relations/{relation_id}/explanation")
    def inference_explanation(
        project_id: str, relation_id: str, refresh: bool = False
    ) -> dict[str, Any]:
        try:
            return inference_service(project_id).explain(relation_id, refresh=refresh)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Härledd relation finns inte") from exc

    @app.get("/api/projects/{project_id}/inference/reviews")
    def inference_reviews(project_id: str, status: str | None = None) -> dict[str, Any]:
        return inference_service(project_id).reviews(status=status)

    @app.post("/api/projects/{project_id}/inference/relations/{relation_id}/review")
    def inference_review(
        project_id: str, relation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            return inference_service(project_id).review_relation(
                relation_id,
                decision=str(payload.get("decision", "")),
                actor=str(payload.get("actor", "system")),
                note=payload.get("note"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Härledd relation finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/inference/relations/{relation_id}/promote")
    def inference_promote(
        project_id: str, relation_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            body = payload or {}
            return inference_service(project_id).promote_relation(
                relation_id,
                actor=str(body.get("actor", "system")),
                note=body.get("note"),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Härledd relation finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def building_structure_service(project_id: str) -> BuildingStructureService:
        return BuildingStructureService(building_graph_service(project_id))

    @app.get("/api/projects/{project_id}/building-graph/structure")
    def get_building_structure(project_id: str) -> dict[str, Any]:
        return building_structure_service(project_id).structure()

    @app.post("/api/projects/{project_id}/building-graph/buildings", status_code=201)
    def create_building(project_id: str, payload: BuildingInput) -> dict[str, Any]:
        try:
            return building_structure_service(project_id).create_building(**payload.model_dump())
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/building-graph/floors", status_code=201)
    def create_floor(project_id: str, payload: FloorInput) -> dict[str, Any]:
        try:
            return building_structure_service(project_id).create_floor(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Byggnaden finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/building-graph/spaces", status_code=201)
    def create_space(project_id: str, payload: SpaceInput) -> dict[str, Any]:
        try:
            return building_structure_service(project_id).create_space(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Planet finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/building-graph/zones", status_code=201)
    def create_zone(project_id: str, payload: ZoneInput) -> dict[str, Any]:
        try:
            return building_structure_service(project_id).create_zone(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Ett eller flera rum saknas") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def system_graph_service(project_id: str) -> SystemGraphService:
        return SystemGraphService(building_graph_service(project_id))

    @app.get("/api/system-graph/disciplines")
    def system_disciplines() -> dict[str, Any]:
        return {"count": len(SYSTEM_DISCIPLINES), "items": sorted(SYSTEM_DISCIPLINES)}

    @app.get("/api/projects/{project_id}/system-graph/systems")
    def get_systems(project_id: str, discipline: str | None = None) -> dict[str, Any]:
        try:
            return system_graph_service(project_id).systems(discipline=discipline)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/system-graph/systems", status_code=201)
    def create_technical_system(project_id: str, payload: TechnicalSystemInput) -> dict[str, Any]:
        try:
            return system_graph_service(project_id).create_system(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Refererat system eller byggnadsobjekt saknas: {exc}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/system-graph/relations", status_code=201)
    def create_system_relation(project_id: str, payload: SystemRelationInput) -> dict[str, Any]:
        try:
            return system_graph_service(project_id).connect_systems(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"System saknas: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/system-graph/service-relations", status_code=201)
    def create_system_service(project_id: str, payload: SystemServiceInput) -> dict[str, Any]:
        try:
            return system_graph_service(project_id).assign_service(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"System eller målobjekt saknas: {exc}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/system-graph/systems/{system_id}/impact")
    def get_system_impact(project_id: str, system_id: str, max_depth: int = 10) -> dict[str, Any]:
        try:
            return system_graph_service(project_id).impact(system_id, max_depth=max_depth)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Systemet finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def component_graph_service(project_id: str) -> ComponentGraphService:
        return ComponentGraphService(building_graph_service(project_id))

    @app.get("/api/component-graph/relation-types")
    def component_relation_types() -> dict[str, Any]:
        return {"count": len(COMPONENT_RELATIONS), "items": sorted(COMPONENT_RELATIONS)}

    @app.get("/api/projects/{project_id}/component-graph/components")
    def get_components(
        project_id: str,
        discipline: str | None = None,
        system_id: str | None = None,
        located_in_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            return component_graph_service(project_id).components(
                discipline=discipline, system_id=system_id, located_in_id=located_in_id
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Refererat system eller byggnadsobjekt saknas: {exc}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/component-graph/components", status_code=201)
    def create_component(project_id: str, payload: TechnicalComponentInput) -> dict[str, Any]:
        try:
            return component_graph_service(project_id).create_component(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Refererat system eller byggnadsobjekt saknas: {exc}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/component-graph/relations", status_code=201)
    def create_component_relation(
        project_id: str, payload: ComponentRelationInput
    ) -> dict[str, Any]:
        try:
            return component_graph_service(project_id).connect_components(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Komponent saknas: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/component-graph/properties", status_code=201)
    def create_component_property(
        project_id: str, payload: ComponentPropertyInput
    ) -> dict[str, Any]:
        try:
            return component_graph_service(project_id).add_property(**payload.model_dump())
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Komponent eller evidens saknas: {exc}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/component-graph/components/{component_id}/trace")
    def trace_component(project_id: str, component_id: str, max_depth: int = 20) -> dict[str, Any]:
        try:
            return component_graph_service(project_id).trace(component_id, max_depth=max_depth)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Komponenten finns inte") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/vent/registry")
    def get_vent_registry() -> dict[str, Any]:
        items = [asdict(item) for item in component_registry()]
        return {"version": "crow-vent-registry-v0.2", "count": len(items), "components": items}

    @app.get("/api/projects/{project_id}/vent/{checksum}")
    def get_vent_model(
        project_id: str,
        checksum: str,
        tolerance: float = 0.001,
        association_radius: float = 100.0,
        layer: str | None = None,
        visible_only: bool = False,
    ) -> dict[str, Any]:
        if tolerance <= 0:
            raise HTTPException(status_code=400, detail="Toleransen måste vara större än noll")
        if association_radius < 0:
            raise HTTPException(status_code=400, detail="Kopplingsradien får inte vara negativ")
        asset = get_imported_asset(project_id, checksum)
        state = load_geometry_state(project_id, checksum)
        document = geometry_from_import_manifest(asset, state.get("layers") or {})
        candidates = consolidate_observations(
            document,
            tolerance=tolerance,
            association_radius=association_radius,
            layers=[layer] if layer else None,
            visible_only=visible_only,
        )
        return _jsonable(build_vent_model(candidates))

    @app.get("/api/projects/{project_id}/vent/{checksum}/quantity.csv")
    def get_vent_quantity_csv(project_id: str, checksum: str) -> Response:
        model = get_vent_model(project_id, checksum)
        content = "\ufeff" + quantity_takeoff_csv(model["quantity_takeoff"])
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="crow-vent-{checksum[:12]}-quantity.csv"'
                )
            },
        )

    @app.get("/api/projects/{project_id}/vent/{checksum}/review")
    def get_vent_review(project_id: str, checksum: str) -> dict[str, Any]:
        model = get_vent_model(project_id, checksum)
        items = [item for item in model["classifications"] if item["status"] == "needs_review"]
        return {"count": len(items), "items": items}

    return app


app = create_app()
