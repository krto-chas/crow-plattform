# ruff: noqa: E501
from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from crow_ovk_export import intyg_pdf
from crow_ovk_fastighet import (
    BesiktningsmanRepository,
    FastighetRepository,
    funktionskontrollant_from,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response

from crow_entitlements.context import current_customer_from_request
from crow_ovk_intyg import (
    Behorighet,
    Byggnadsagare,
    Funktionskontrollant,
    OvkIntyg,
    OvkIntygRepository,
    build_intyg,
    intyg_from_payload,
    intyg_html,
    intyg_to_payload,
    intyg_verification_code,
    intyg_verify_url,
    verify_intyg_code,
)
from crow_ovk_pricing import BuildingCategory, InspectionType
from crow_ovk_workflow import OvkWorkflowRecord, OvkWorkflowRepository, record_to_payload

from .ovk_issuance_lock import inspection_mutation_guard, require_unissued
from .ovk_issuance_manifest import manifest_path, publish_manifest
from .ovk_protocol_source import require_current_protocol_source


def ovk_intyg_router(data_root: Path) -> APIRouter:
    router = APIRouter(dependencies=[Depends(inspection_mutation_guard(data_root))])
    workflow_repository = OvkWorkflowRepository(data_root)
    intyg_repository = OvkIntygRepository(data_root)
    fastighet_repository = FastighetRepository(data_root)
    besiktningsman_repository = BesiktningsmanRepository(data_root)

    def _resolve_fastighetsbeteckning(project_id: str, payload: dict[str, Any]) -> str:
        fastighet_id = payload.get("fastighet_id")
        if isinstance(fastighet_id, str) and fastighet_id.strip():
            try:
                fastighet = fastighet_repository.load(project_id, fastighet_id.strip())
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404, detail={"code": "FASTIGHET_NOT_FOUND"}
                ) from exc
            return fastighet.fastighetsbeteckning
        return _required(payload, "fastighetsbeteckning")

    def _resolve_byggnadsagare(project_id: str, payload: dict[str, Any]) -> Byggnadsagare:
        fastighet_id = payload.get("fastighet_id")
        if isinstance(fastighet_id, str) and fastighet_id.strip():
            fastighet = fastighet_repository.load(project_id, fastighet_id.strip())
            if fastighet.byggnadsagare_namn.strip():
                contact_parts = [
                    part
                    for part in (
                        fastighet.byggnadsagare_adress.gata,
                        fastighet.byggnadsagare_adress.postnr,
                        fastighet.byggnadsagare_adress.ort,
                    )
                    if part.strip()
                ]
                return Byggnadsagare(
                    name=fastighet.byggnadsagare_namn,
                    contact=" ".join(contact_parts) or None,
                )
        return Byggnadsagare(
            name=_required(payload, "byggnadsagare_name"),
            contact=_optional(payload.get("byggnadsagare_contact")),
        )

    def _resolve_kontrollant(payload: dict[str, Any]) -> Funktionskontrollant:
        besiktningsman_id = payload.get("besiktningsman_id")
        if isinstance(besiktningsman_id, str) and besiktningsman_id.strip():
            try:
                person = besiktningsman_repository.load(besiktningsman_id.strip())
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404, detail={"code": "BESIKTNINGSMAN_NOT_FOUND"}
                ) from exc
            return funktionskontrollant_from(person)
        return Funktionskontrollant(
            name=_required(payload, "kontrollant_name"),
            behorighet=Behorighet(_required(payload, "kontrollant_behorighet")),
            certification_body=_required(payload, "kontrollant_certification_body"),
            certificate_number=_required(payload, "kontrollant_certificate_number"),
            certificate_valid_to=_optional_date(payload.get("kontrollant_certificate_valid_to")),
        )

    def _registered_identity(
        record: OvkWorkflowRecord, project_id: str, payload: dict[str, Any]
    ) -> OvkWorkflowRecord:
        planning = record.planning
        if planning is None:
            # Legacy local fixtures and trusted development only; never production sessions.
            if (
                os.getenv("CROW_MODE", "local").strip().lower() == "local"
                and os.getenv("CROW_AUTH_MODE", "environment").strip().lower() == "environment"
            ):
                return record
            raise ValueError("registered inspection planning is required")
        obj = record.inspection.ovk_object
        if obj.project_id != project_id:
            raise ValueError("inspection project does not match")
        for key, expected in (
            ("fastighet_id", obj.object_id),
            ("besiktningsman_id", planning.inspector_id),
            ("inspection_type", planning.inspection_type),
        ):
            supplied = payload.get(key)
            if supplied is not None and supplied != expected:
                raise ValueError(f"{key} does not match planned inspection")
            payload[key] = expected
        try:
            property_record = fastighet_repository.load(project_id, obj.object_id)
            person = besiktningsman_repository.load(planning.inspector_id)
        except FileNotFoundError as exc:
            raise ValueError("registered property or inspector is missing") from exc
        if (
            property_record.project_id != project_id
            or property_record.fastighet_id != obj.object_id
        ):
            raise ValueError("registered property identity does not match")
        building = next(
            (item for item in property_record.byggnader if item.byggnad_id == obj.building_id),
            None,
        )
        if building is None:
            raise ValueError("registered building is missing")
        if not property_record.byggnadsagare_namn.strip():
            raise ValueError("registered building owner is required")
        address = property_record.byggnadens_adress
        if address.is_empty:
            raise ValueError("registered building address is required")
        inspection_date = _required_date(payload, "inspection_date")
        issued_date = _optional_date(payload.get("issued_date")) or date.today()
        if not inspection_date <= issued_date <= date.today():
            raise ValueError("inspection and issuance dates are inconsistent")
        if person.giltig_till is None or person.giltig_till < issued_date:
            raise ValueError("registered inspector certificate is missing validity or has expired")
        payload["issued_date"] = issued_date.isoformat()
        if record.building_structure_json is None:
            raise ValueError("registered building system snapshot is required")
        structure = json.loads(record.building_structure_json)
        registered = {item["system_id"]: item for item in structure["systems"]}
        systems = record.inspection.systems
        if not systems or any(
            system.system_id not in registered
            or registered[system.system_id]["system_type"] != system.system_type
            or registered[system.system_id]["label"] != system.label
            for system in systems
        ):
            raise ValueError("inspection systems do not match registered building snapshot")
        category = {
            "villa": "smahus",
            "flerbostadshus": "flerbostadshus",
            "kontorsbyggnad": "lokal",
            "industrifastighet": "lokal",
        }[property_record.fastighetstyp.value]
        if payload.get("building_category") != category:
            raise ValueError("building category does not match registered property")
        if not isinstance(payload.get("school_or_care", False), bool):
            raise ValueError("school_or_care must be a boolean")
        if (
            person.behorighet.value == "N"
            and category != "smahus"
            and any(system.system_type in {"FT", "FTX"} for system in systems)
        ):
            raise ValueError("registered inspector requires K for this system")
        canonical = replace(
            obj,
            name=f"{property_record.fastighetsbeteckning} · {building.internt_namn}",
            address=" ".join(part for part in (address.gata, address.postnr, address.ort) if part),
        )
        return replace(record, inspection=replace(record.inspection, ovk_object=canonical))

    @router.get("/ovk/intyg", response_class=HTMLResponse)
    def intyg_page() -> str:
        return _INTYG_HTML

    @router.get("/api/ovk/projects/{project_id}/intyg", response_model=None)
    def list_intyg(project_id: str) -> dict[str, Any]:
        try:
            items = intyg_repository.list(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_PROJECT"}) from exc
        return {
            "project_id": project_id,
            "intyg": [
                {
                    "intyg_id": item.intyg_id,
                    "inspection_id": item.inspection_id,
                    "object_name": item.object_name,
                    "result": item.result.value,
                    "issued_date": item.issued_date.isoformat(),
                    "next_inspection_due": (
                        item.next_inspection.due_date.isoformat()
                        if item.next_inspection.due_date is not None
                        else None
                    ),
                }
                for item in items
            ],
        }

    @router.get("/api/ovk/projects/{project_id}/intyg/{intyg_id}", response_model=None)
    def get_intyg(project_id: str, intyg_id: str) -> dict[str, Any]:
        return intyg_to_payload(_load(intyg_repository, project_id, intyg_id))

    @router.get(
        "/api/ovk/projects/{project_id}/intyg/{intyg_id}/anslag",
        response_class=HTMLResponse,
    )
    def export_anslag(project_id: str, intyg_id: str) -> str:
        return intyg_html(_load(intyg_repository, project_id, intyg_id))

    async def _build_from_request(
        project_id: str, inspection_id: str, request: Request
    ) -> tuple[OvkIntyg, str]:
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_INTYG"})
        try:
            record = workflow_repository.load(project_id, inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_INSPECTION_NOT_FOUND"}
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc
        try:
            require_current_protocol_source(data_root, project_id, inspection_id, record)
            original_record = record
            record = _registered_identity(record, project_id, payload)
            intyg = build_intyg(
                intyg_id=_required(payload, "intyg_id"),
                record=record,
                fastighetsbeteckning=_resolve_fastighetsbeteckning(project_id, payload),
                byggnadsagare=_resolve_byggnadsagare(project_id, payload),
                funktionskontrollant=_resolve_kontrollant(payload),
                inspection_type=InspectionType(_required(payload, "inspection_type")),
                inspection_date=_required_date(payload, "inspection_date"),
                building_category=BuildingCategory(_required(payload, "building_category")),
                school_or_care=bool(payload.get("school_or_care", False)),
                issued_date=_optional_date(payload.get("issued_date")),
            )
            field_root = data_root / "projects" / project_id / "ovk-field" / inspection_id
            field_digests = {
                name: sha256((field_root / name).read_bytes()).hexdigest()
                for name in ("snapshot.json", "context.json", "protocol-source.json")
                if (field_root / name).is_file()
            }
            revision = sha256(
                json.dumps(
                    [record_to_payload(original_record), intyg_to_payload(intyg), field_digests],
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            return intyg, revision
        except ValueError as exc:
            message = str(exc)
            if "protocol ready" in message or "pending" in message:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "OVK_INTYG_NOT_READY",
                        "conclusion": record.inspection.conclusion.value,
                        "unresolved_review_count": record.unresolved_review_count,
                    },
                ) from exc
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_INTYG", "message": message},
            ) from exc

    @router.post(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/intyg/preview",
        response_model=None,
    )
    async def preview_intyg(project_id: str, inspection_id: str, request: Request) -> Response:
        """Vattenstämplat utkast: bygger intyget utan att spara det."""
        intyg, revision = await _build_from_request(project_id, inspection_id, request)
        return Response(
            content=intyg_pdf(intyg, draft=True),
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'inline; filename="ovk-intyg-utkast.pdf"',
                "X-OVK-Review-Revision": revision,
                "Cache-Control": "no-store",
            },
        )

    def _review_path(project_id: str, inspection_id: str, revision: str) -> Path:
        # Project and inspection identifiers have already been validated by workflow.load.
        directory = data_root / "projects" / project_id / "ovk-issuance-review"
        return directory / inspection_id / f"{revision}.json"

    @router.post(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/intyg/review",
        response_model=None,
    )
    async def approve_intyg_review(
        project_id: str, inspection_id: str, request: Request
    ) -> dict[str, Any]:
        intyg, revision = await _build_from_request(project_id, inspection_id, request)
        if request.headers.get("X-OVK-Review-Revision") != revision:
            raise HTTPException(status_code=409, detail={"code": "OVK_REVIEW_REVISION_MISMATCH"})
        customer = current_customer_from_request(request)
        approval = {
            "revision": revision,
            "intyg_id": intyg.intyg_id,
            "reviewer": customer.user_id,
            "customer_id": customer.customer_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        path = _review_path(project_id, inspection_id, revision)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
            ) as stream:
                temp = Path(stream.name)
                json.dump(approval, stream, ensure_ascii=False)
            temp.replace(path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        return approval

    def _certificate_status(intyg: OvkIntyg) -> dict[str, Any]:
        def digest(item: OvkIntyg) -> str:
            canonical = json.dumps(
                intyg_to_payload(item), sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            return sha256(canonical.encode("utf-8")).hexdigest()

        error = {"status": "integrity_error"}
        project_id = intyg.project_id
        if not intyg.inspection_id or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for char in intyg.inspection_id
        ):
            return error
        try:
            source_path = manifest_path(data_root, project_id, intyg.inspection_id)
            source_bytes = source_path.read_bytes()
            source = json.loads(source_bytes)
            original_id = source["intyg_id"]
            original = intyg_repository.load(project_id, original_id)
            if (
                source["project_id"] != project_id
                or source["inspection_id"] != intyg.inspection_id
                or original.project_id != project_id
                or original.inspection_id != intyg.inspection_id
                or original.intyg_id != original_id
                or source["intyg_sha256"] != digest(original)
            ):
                return error
            directory = data_root / "projects" / project_id / "ovk-correction-manifests"
            path = directory / f"{original_id}.json"
            if not path.exists():
                return {"status": "current"} if intyg.intyg_id == original_id else error
            correction = json.loads(path.read_bytes())
            replacement_id = correction["replacement_intyg_id"]
            replacement = intyg_repository.load(project_id, replacement_id)
            if (
                correction["project_id"] != project_id
                or correction["inspection_id"] != intyg.inspection_id
                or correction["original_intyg_id"] != original_id
                or correction["original_sha256"] != digest(original)
                or correction["original_manifest_sha256"] != sha256(source_bytes).hexdigest()
                or replacement_id == original_id
                or replacement.project_id != project_id
                or replacement.inspection_id != intyg.inspection_id
                or replacement.intyg_id != replacement_id
                or correction["replacement_sha256"] != digest(replacement)
            ):
                return error
            if intyg.intyg_id == original_id:
                return {"status": "superseded", "replacement_intyg_id": replacement_id}
            if intyg.intyg_id == replacement_id:
                return {"status": "current", "original_intyg_id": original_id}
        except (OSError, ValueError, KeyError, TypeError):
            return error
        return error

    @router.get("/api/ovk/projects/{project_id}/intyg/{intyg_id}/status")
    def certificate_status(project_id: str, intyg_id: str) -> dict[str, Any]:
        intyg = _load(intyg_repository, project_id, intyg_id)
        if intyg.project_id != project_id or intyg.intyg_id != intyg_id:
            return {"status": "integrity_error"}
        return _certificate_status(intyg)

    @router.get("/ovk/verifiera/{project_id}/{intyg_id}", response_class=HTMLResponse)
    def verify_page(project_id: str, intyg_id: str, c: str = Query(default="")) -> str:
        try:
            intyg = intyg_repository.load(project_id, intyg_id)
        except (FileNotFoundError, ValueError):
            return _verify_html(None, valid=False, code=c)
        valid = bool(c.strip()) and verify_intyg_code(intyg, c)
        if not valid or intyg.project_id != project_id or intyg.intyg_id != intyg_id:
            return _verify_html(None, valid=False, code=c)
        status = _certificate_status(intyg)
        return _verify_html(intyg, valid=True, code=c, status=status)

    @router.post(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/intyg",
        response_model=None,
    )
    async def create_intyg(
        project_id: str,
        inspection_id: str,
        request: Request,
    ) -> dict[str, Any]:
        intyg, revision = await _build_from_request(project_id, inspection_id, request)
        try:
            if intyg_repository.exists(project_id, intyg.intyg_id):
                raise FileExistsError(intyg.intyg_id)
            require_unissued(data_root, project_id, inspection_id)
            if not _review_path(project_id, inspection_id, revision).is_file():
                raise HTTPException(status_code=409, detail={"code": "OVK_INTYG_REVIEW_REQUIRED"})
            publish_manifest(
                data_root,
                project_id,
                inspection_id,
                intyg,
                revision,
                _review_path(project_id, inspection_id, revision),
            )
            intyg_repository.save(intyg)
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVK_INTYG_ALREADY_EXISTS",
                    "message": "Intyget är redan utfärdat och kan inte skrivas över; "
                    "använd rättelseflödet.",
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_INTYG", "message": str(exc)},
            ) from exc
        return {
            **intyg_to_payload(intyg),
            "verification_code": intyg_verification_code(intyg),
            "verify_url": intyg_verify_url(intyg),
        }

    @router.post("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction")
    async def request_correction(
        project_id: str, intyg_id: str, request: Request
    ) -> dict[str, Any]:
        original = _load(intyg_repository, project_id, intyg_id)
        try:
            payload: Any = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid JSON") from exc
        reason = payload.get("reason") if isinstance(payload, dict) else None
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
            raise HTTPException(status_code=422, detail={"code": "OVK_CORRECTION_REASON_REQUIRED"})
        customer = current_customer_from_request(request)
        correction = {
            "schema_version": 1,
            "project_id": project_id,
            "inspection_id": original.inspection_id,
            "original_intyg_id": intyg_id,
            "original_verification_code": intyg_verification_code(original),
            "reason": reason.strip(),
            "requested_by": customer.user_id,
            "customer_id": customer.customer_id,
            "requested_at": datetime.now(UTC).isoformat(),
            "status": "requested",
        }
        target = data_root / "projects" / project_id / "ovk-corrections" / f"{intyg_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(correction, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "OVK_CORRECTION_ALREADY_REQUESTED"}
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return correction

    @router.get("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction")
    def get_correction(project_id: str, intyg_id: str) -> dict[str, Any]:
        _load(intyg_repository, project_id, intyg_id)
        target = data_root / "projects" / project_id / "ovk-corrections" / f"{intyg_id}.json"
        try:
            payload: dict[str, Any] = json.loads(target.read_bytes())
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_CORRECTION_NOT_FOUND"}
            ) from exc
        return payload

    @router.post("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction/draft")
    async def create_correction_draft(
        project_id: str, intyg_id: str, request: Request
    ) -> dict[str, Any]:
        original = _load(intyg_repository, project_id, intyg_id)
        correction = get_correction(project_id, intyg_id)
        if correction.get("original_verification_code") != intyg_verification_code(original):
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_SOURCE_CHANGED"})
        try:
            payload: Any = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid JSON") from exc
        allowed = {"address", "object_name"}
        if not isinstance(payload, dict) or not payload or set(payload) - allowed:
            raise HTTPException(status_code=422, detail={"code": "OVK_CORRECTION_INVALID_FIELDS"})
        changes: dict[str, str] = {}
        for key, value in payload.items():
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
                raise HTTPException(
                    status_code=422, detail={"code": "OVK_CORRECTION_INVALID_FIELDS"}
                )
            if value.strip() != getattr(original, key):
                changes[key] = value.strip()
        if not changes:
            raise HTTPException(status_code=422, detail={"code": "OVK_CORRECTION_NO_CHANGES"})
        candidate = replace(
            original,
            intyg_id=f"correction-{uuid4().hex}",
            address=changes.get("address", original.address),
            object_name=changes.get("object_name", original.object_name),
        )
        original_payload = intyg_to_payload(original)
        canonical = json.dumps(
            original_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        customer = current_customer_from_request(request)
        draft = {
            "schema_version": 1,
            "status": "draft",
            "project_id": project_id,
            "original_intyg_id": intyg_id,
            "original_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "draft_id": candidate.intyg_id,
            "reason": correction["reason"],
            "changes": {
                key: {"before": getattr(original, key), "after": value}
                for key, value in changes.items()
            },
            "created_by": customer.user_id,
            "customer_id": customer.customer_id,
            "created_at": datetime.now(UTC).isoformat(),
            "candidate": intyg_to_payload(candidate),
        }
        target = data_root / "projects" / project_id / "ovk-correction-drafts" / f"{intyg_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(draft, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "OVK_CORRECTION_DRAFT_EXISTS"}
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return draft

    @router.get("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction/draft")
    def get_correction_draft(project_id: str, intyg_id: str) -> dict[str, Any]:
        _load(intyg_repository, project_id, intyg_id)
        target = data_root / "projects" / project_id / "ovk-correction-drafts" / f"{intyg_id}.json"
        try:
            payload: dict[str, Any] = json.loads(target.read_bytes())
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_CORRECTION_DRAFT_NOT_FOUND"}
            ) from exc
        return payload

    def _correction_revision(project_id: str, intyg_id: str) -> str:
        original = intyg_to_payload(_load(intyg_repository, project_id, intyg_id))
        correction = get_correction(project_id, intyg_id)
        draft = get_correction_draft(project_id, intyg_id)
        canonical = json.dumps(original, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        changes = draft.get("changes")
        if (
            draft.get("original_sha256") != sha256(canonical.encode("utf-8")).hexdigest()
            or draft.get("project_id") != project_id
            or draft.get("original_intyg_id") != intyg_id
            or draft.get("reason") != correction.get("reason")
            or not isinstance(changes, dict)
            or not changes
            or set(changes) - {"address", "object_name"}
        ):
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_SOURCE_CHANGED"})
        expected = dict(original)
        draft_id = draft.get("draft_id")
        if not isinstance(draft_id, str) or not draft_id.startswith("correction-"):
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_SOURCE_CHANGED"})
        expected["intyg_id"] = draft_id
        for key, change in changes.items():
            if (
                not isinstance(change, dict)
                or change.get("before") != original[key]
                or not isinstance(change.get("after"), str)
                or not 1 <= len(change["after"].strip()) <= 500
                or change["after"] == original[key]
            ):
                raise HTTPException(
                    status_code=409, detail={"code": "OVK_CORRECTION_SOURCE_CHANGED"}
                )
            expected[key] = change["after"]
        if draft.get("candidate") != expected:
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_SOURCE_CHANGED"})
        source = json.dumps(
            [original, correction, draft], sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        return sha256(source.encode("utf-8")).hexdigest()

    @router.get("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction/review")
    def correction_review(project_id: str, intyg_id: str) -> dict[str, Any]:
        revision = _correction_revision(project_id, intyg_id)
        return {"revision": revision, "draft": get_correction_draft(project_id, intyg_id)}

    @router.post("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction/review")
    async def approve_correction(
        project_id: str, intyg_id: str, request: Request
    ) -> dict[str, Any]:
        customer = current_customer_from_request(request)
        if not customer.user_id or "ovk_correction_reviewer" not in customer.roles:
            raise HTTPException(status_code=403, detail={"code": "OVK_CORRECTION_REVIEW_FORBIDDEN"})
        revision = _correction_revision(project_id, intyg_id)
        draft = get_correction_draft(project_id, intyg_id)
        if draft.get("customer_id") != customer.customer_id:
            raise HTTPException(status_code=403, detail={"code": "OVK_CORRECTION_REVIEW_FORBIDDEN"})
        try:
            payload: Any = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid JSON") from exc
        if not isinstance(payload, dict) or payload.get("revision") != revision:
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_REVIEW_STALE"})
        approval = {
            "schema_version": 1,
            "project_id": project_id,
            "original_intyg_id": intyg_id,
            "draft_id": draft["draft_id"],
            "revision": revision,
            "reviewer": customer.user_id,
            "customer_id": customer.customer_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        target = data_root / "projects" / project_id / "ovk-correction-reviews" / f"{intyg_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(approval, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "OVK_CORRECTION_ALREADY_REVIEWED"}
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return approval

    @router.post("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction/issue")
    async def issue_correction(project_id: str, intyg_id: str, request: Request) -> dict[str, Any]:
        return await _publish_correction(project_id, intyg_id, request, recover=False)

    @router.post("/api/ovk/projects/{project_id}/intyg/{intyg_id}/correction/recover")
    async def recover_correction(
        project_id: str, intyg_id: str, request: Request
    ) -> dict[str, Any]:
        return await _publish_correction(project_id, intyg_id, request, recover=True)

    async def _publish_correction(
        project_id: str, intyg_id: str, request: Request, *, recover: bool
    ) -> dict[str, Any]:
        customer = current_customer_from_request(request)
        if not customer.user_id or "ovk_correction_issuer" not in customer.roles:
            raise HTTPException(status_code=403, detail={"code": "OVK_CORRECTION_ISSUE_FORBIDDEN"})
        original = _load(intyg_repository, project_id, intyg_id)
        revision = _correction_revision(project_id, intyg_id)
        draft = get_correction_draft(project_id, intyg_id)
        correction = get_correction(project_id, intyg_id)
        if (
            draft.get("customer_id") != customer.customer_id
            or correction.get("customer_id") != customer.customer_id
        ):
            raise HTTPException(status_code=403, detail={"code": "OVK_CORRECTION_ISSUE_FORBIDDEN"})
        try:
            payload: Any = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid JSON") from exc
        if not isinstance(payload, dict) or payload.get("revision") != revision:
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_REVIEW_STALE"})
        root = data_root / "projects" / project_id
        review_path = root / "ovk-correction-reviews" / f"{intyg_id}.json"
        try:
            approval = json.loads(review_path.read_bytes())
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "OVK_CORRECTION_REVIEW_REQUIRED"}
            ) from exc
        if (
            not isinstance(approval, dict)
            or approval.get("revision") != revision
            or approval.get("project_id") != project_id
            or approval.get("original_intyg_id") != intyg_id
            or approval.get("draft_id") != draft["draft_id"]
            or approval.get("customer_id") != customer.customer_id
            or not approval.get("reviewer")
            or not approval.get("reviewed_at")
        ):
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_REVIEW_STALE"})
        source_path = manifest_path(data_root, project_id, original.inspection_id)
        try:
            source_bytes = source_path.read_bytes()
            source = json.loads(source_bytes)
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=409, detail={"code": "OVK_CORRECTION_SOURCE_CHANGED"}
            ) from exc
        if (
            not isinstance(source, dict)
            or source.get("project_id") != project_id
            or source.get("inspection_id") != original.inspection_id
            or source.get("intyg_id") != intyg_id
            or source.get("intyg_sha256") != draft["original_sha256"]
        ):
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_SOURCE_CHANGED"})
        candidate = intyg_from_payload(draft["candidate"])
        if not recover and intyg_repository.exists(project_id, candidate.intyg_id):
            raise HTTPException(status_code=409, detail={"code": "OVK_CORRECTION_ALREADY_ISSUED"})
        # Preserve the reviewed certificate dates. The correction event has its own timestamp.
        certificate = intyg_to_payload(candidate)
        canonical = json.dumps(
            certificate, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        manifest = {
            "schema_version": 1,
            "project_id": project_id,
            "inspection_id": original.inspection_id,
            "original_intyg_id": intyg_id,
            "replacement_intyg_id": candidate.intyg_id,
            "original_sha256": draft["original_sha256"],
            "original_manifest_sha256": sha256(source_bytes).hexdigest(),
            "replacement_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "review_revision": revision,
            "review": approval,
            "changes": draft["changes"],
            "reason": draft["reason"],
            "issued_by": customer.user_id,
            "customer_id": customer.customer_id,
            "corrected_at": datetime.now(UTC).isoformat(),
        }
        target = root / "ovk-correction-manifests" / f"{intyg_id}.json"
        if recover:
            try:
                saved = json.loads(target.read_bytes())
            except (OSError, ValueError) as exc:
                raise HTTPException(
                    status_code=409, detail={"code": "OVK_CORRECTION_RECOVERY_INVALID"}
                ) from exc
            if (
                not isinstance(saved, dict)
                or set(saved) != set(manifest)
                or any(
                    saved[key] != value
                    for key, value in manifest.items()
                    if key not in {"issued_by", "corrected_at"}
                )
                or not isinstance(saved.get("issued_by"), str)
                or not saved["issued_by"]
                or not isinstance(saved.get("corrected_at"), str)
            ):
                raise HTTPException(
                    status_code=409, detail={"code": "OVK_CORRECTION_RECOVERY_INVALID"}
                )
            try:
                timestamp = datetime.fromisoformat(saved["corrected_at"])
                if timestamp.tzinfo is None:
                    raise ValueError("Missing timezone")
            except ValueError as exc:
                raise HTTPException(
                    status_code=409, detail={"code": "OVK_CORRECTION_RECOVERY_INVALID"}
                ) from exc
            try:
                intyg_repository.save(candidate)
            except FileExistsError:
                pass
            if _certificate_status(candidate).get("status") != "current":
                raise HTTPException(
                    status_code=409, detail={"code": "OVK_CORRECTION_RECOVERY_INVALID"}
                )
            return {
                "certificate": certificate,
                "correction": saved,
                "verification_code": intyg_verification_code(candidate),
                "verify_url": intyg_verify_url(candidate),
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(manifest, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
            intyg_repository.save(candidate)
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "OVK_CORRECTION_RECOVERY_REQUIRED"}
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {
            "certificate": certificate,
            "correction": manifest,
            "verification_code": intyg_verification_code(candidate),
            "verify_url": intyg_verify_url(candidate),
        }

    return router


def _verify_html(
    intyg: OvkIntyg | None, *, valid: bool, code: str, status: dict[str, Any] | None = None
) -> str:
    head = (
        '<!doctype html><html lang="sv"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex">'
        "<title>OVK-verifiering</title>" + _VERIFY_CSS + "</head><body><main>"
        "<h1>OVK-verifiering</h1>"
    )
    if intyg is None or not valid:
        # Samma svar oavsett om intyget saknas eller koden är fel: sidan ska
        # inte avslöja vilka intygs-ID:n som finns.
        return (
            head + '<div class="verdict fail">EJ GILTIGT</div>'
            "<p>Intyget kunde inte verifieras. Kontrollera adressen och koden på "
            "intyget, eller kontakta utfärdaren.</p></main></body></html>"
        )
    if status is not None and status["status"] == "integrity_error":
        return (
            head + '<div class="verdict fail">INTEGRITETSFEL</div>'
            "<p>Intygets utfärdandehistorik kunde inte verifieras.</p></main></body></html>"
        )
    superseded = status is not None and status["status"] == "superseded"
    verdict = "ERSATT INTYG" if superseded else "GILTIGT INTYG"
    history = ""
    if superseded and status is not None:
        replacement_id = escape(status["replacement_intyg_id"])
        history = f"<p>Historiskt intyg. Ersättningsintyg: {replacement_id}.</p>"
    elif status is not None and "original_intyg_id" in status:
        history = "<p>Rättelse av intyg: " + escape(status["original_intyg_id"]) + ".</p>"
    rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"
        for label, value in (
            ("Intygs-ID", intyg.intyg_id),
            ("Fastighetsbeteckning", intyg.fastighetsbeteckning),
            ("Byggnad", f"{intyg.object_name} ({intyg.building_id})"),
            ("Resultat", "GODKÄND" if intyg.result.value == "godkand" else "EJ GODKÄND"),
            ("Besiktningsdatum", intyg.inspection_date.isoformat()),
            ("Utfärdat", intyg.issued_date.isoformat()),
            ("Funktionskontrollant", intyg.funktionskontrollant.name),
            (
                "Nästa besiktning senast",
                intyg.next_inspection.due_date.isoformat()
                if intyg.next_inspection.due_date is not None
                else "—",
            ),
        )
    )
    return (
        f'{head}<div class="verdict pass">{verdict}</div>{history}'
        f"<p>Verifieringskod <code>{escape(code)}</code> "
        "stämmer mot det lagrade intyget.</p>"
        f"<table>{rows}</table>"
        '<p class="note">Jämför uppgifterna ovan med det tryckta intyget. '
        "Avviker de är dokumentet inte giltigt.</p></main></body></html>"
    )


_VERIFY_CSS = (
    "<style>body{font-family:Georgia,serif;color:#18212b;background:#f4f6f8;margin:0}"
    "main{max-width:640px;margin:40px auto;padding:24px;background:#fff;"
    "border:1px solid #dfe5ea;border-radius:10px}"
    ".verdict{font-size:26px;font-weight:700;text-align:center;padding:14px;border:3px solid}"
    ".verdict.pass{color:#1c6b34;border-color:#1c6b34;background:#e5f6ea}"
    ".verdict.fail{color:#8f2020;border-color:#8f2020;background:#fbe9e9}"
    "table{width:100%;border-collapse:collapse;margin:14px 0}"
    "td,th{border:1px solid #8a97a3;padding:7px 9px;text-align:left;font-size:14px}"
    "th{background:#eef2f5;width:220px}code{font-size:15px}"
    ".note{font-size:12px;color:#52616f}</style>"
)


def _load(repository: OvkIntygRepository, project_id: str, intyg_id: str) -> Any:
    try:
        return repository.load(project_id, intyg_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "OVK_INTYG_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc


def _required(item: dict[str, Any], key: str) -> str:
    value = _optional(item.get(key))
    if value is None:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_OVK_INTYG", "message": f"{key} is required"}
        )
    return value


def _optional(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _required_date(item: dict[str, Any], key: str) -> date:
    parsed = _optional_date(item.get(key))
    if parsed is None:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_OVK_INTYG", "message": f"{key} is required"}
        )
    return parsed


def _optional_date(value: object) -> date | None:
    text = _optional(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_OVK_INTYG", "message": f"invalid date {text!r}"},
        ) from exc


_INTYG_HTML = r"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow OVK Intyg</title>
<style>:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1200px}.grid{display:grid;grid-template-columns:420px 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px}input,select{width:100%;padding:8px;border:1px solid #cbd4dc;border-radius:6px}.primary,.secondary{margin-top:10px;padding:10px 14px;border-radius:6px;cursor:pointer}.primary{border:0;background:#17202a;color:#fff}.secondary{border:1px solid #aeb9c3;background:#fff}.status{margin-top:12px;padding:10px;background:#eef2f5;border-radius:6px}.warning{background:#fff4cf}.pass{background:#e5f6ea}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}pre{white-space:pre-wrap;background:#f7f8fa;padding:12px;border-radius:6px;max-height:420px;overflow:auto}table{width:100%;border-collapse:collapse;margin-top:10px}td,th{border:1px solid #dfe5ea;padding:6px 8px;font-size:13px;text-align:left}@media(max-width:900px){.shell{grid-template-columns:1fr}aside{display:none}.grid{grid-template-columns:1fr}.two{grid-template-columns:1fr}}</style></head>
<body><div class="shell"><aside><h2>Crow</h2><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a href="/provtryckning">Provtryckning</a><a href="/ovk">OVK import</a><a href="/ovk/besiktning">OVK besiktning</a><a href="/ovk/falt">OVK fält</a><a class="active" href="/ovk/intyg">OVK intyg</a></nav></aside><main><p>OVK · INTYG</p><h1>Utfärda OVK-intyg</h1><p>För planerade besiktningar hämtas fastighet, byggnadsägare och kontrollant från registren. Intyget byggs ur ett sparat, protokollklart workflowrecord. Nästa besiktningsfrist härleds ur BFS 2011:16-intervall och märks som härledd uppgift med skriven basis.</p><div class="grid"><section class="panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><label>Besiktnings-ID</label><input id="inspection" value="ovk-001"><label>Intygs-ID</label><input id="intyg" value="intyg-001"><label>Fastighetsbeteckning</label><input id="fastighet" placeholder="Berghällen 1:2"><label>Byggnadens ägare</label><input id="agare"><div class="two"><div><label>Besiktningstyp</label><select id="type"><option value="aterkommande">Återkommande</option><option value="forstagang">Förstagång</option></select></div><div><label>Byggnadskategori</label><select id="category"><option value="flerbostadshus">Flerbostadshus</option><option value="lokal">Lokal</option><option value="hotell">Hotell</option><option value="smahus">Småhus</option></select></div></div><div class="two"><div><label>Besiktningsdatum</label><input id="date" type="date"></div><div><label>Skola/vård</label><select id="school"><option value="false">Nej</option><option value="true">Ja</option></select></div></div><h3>Funktionskontrollant</h3><label>Namn</label><input id="kname"><div class="two"><div><label>Behörighet</label><select id="kbeh"><option value="K">K</option><option value="N">N</option></select></div><div><label>Certifikatnummer</label><input id="kcert"></div></div><label>Certifieringsorgan</label><input id="korgan" placeholder="RISE / Kiwa"><button class="secondary" id="preview">Förhandsgranska (UTKAST)</button><button class="secondary" id="approve" disabled>Godkänn underlag för utfärdande</button><button class="primary" id="create">Utfärda intyg</button><button class="secondary" id="list">Lista intyg</button><button class="secondary" id="anslag">Öppna anslag</button><div id="message" class="status">Klar.</div></section><section class="panel"><h3>Intyg</h3><pre id="result">Inget intyg laddat.</pre><div id="items"></div></section></div></main></div>
<script>
const $=id=>document.getElementById(id);let reviewedPreview=null;function esc(value){return String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}function ensureProject(id){if(!id)return;if(![...$('project').options].some(o=>o.value===id)){const option=document.createElement('option');option.value=id;option.textContent=id;$('project').appendChild(option)}}
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok)return;const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='ovk')){$('message').textContent='OVK ingår inte i licensen.';$('create').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){ensureProject(p.project_id);const o=[...$('project').options].find(x=>x.value===p.project_id);if(o)o.textContent=p.project_name||p.name||p.project_id}}$('date').value=new Date().toISOString().slice(0,10)}
function build(){return{intyg_id:$('intyg').value,fastighetsbeteckning:$('fastighet').value,byggnadsagare_name:$('agare').value,inspection_type:$('type').value,building_category:$('category').value,inspection_date:$('date').value,school_or_care:$('school').value==='true',kontrollant_name:$('kname').value,kontrollant_behorighet:$('kbeh').value,kontrollant_certification_body:$('korgan').value,kontrollant_certificate_number:$('kcert').value}}
$('create').onclick=async()=>{const p=$('project').value,i=$('inspection').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/inspections/'+encodeURIComponent(i)+'/intyg',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(build())});const d=await r.json();if(!r.ok){$('message').className='status warning';$('message').textContent='Fel: '+JSON.stringify(d);return}$('result').textContent=JSON.stringify(d,null,2);$('message').className='status pass';$('message').textContent='Intyg '+d.intyg_id+' utfärdat ('+d.result+') · verifieringskod '+(d.verification_code||'–')+'.'};
$('preview').onclick=async()=>{const p=$('project').value,i=$('inspection').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/inspections/'+encodeURIComponent(i)+'/intyg/preview',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(build())});if(!r.ok){const d=await r.json();$('message').className='status warning';$('message').textContent='Fel: '+JSON.stringify(d);return}reviewedPreview={revision:r.headers.get('X-OVK-Review-Revision'),project:p,inspection:i,body:JSON.stringify(build())};$('approve').disabled=!reviewedPreview.revision;const blob=await r.blob();window.open(URL.createObjectURL(blob),'_blank');$('message').className='status';$('message').textContent='Utkast öppnat – vattenstämplat, ej giltigt.'};
$('approve').onclick=async()=>{const v=reviewedPreview;if(!v||v.project!==$('project').value||v.inspection!==$('inspection').value||v.body!==JSON.stringify(build())){$('message').textContent='Underlaget har ändrats. Förhandsgranska igen.';return}if(!confirm('Jag har granskat protokoll och intyg och godkänner underlaget för utfärdande. Detta innebär inte att OVK-resultatet är godkänt.'))return;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(v.project)+'/inspections/'+encodeURIComponent(v.inspection)+'/intyg/review',{method:'POST',headers:{'content-type':'application/json','X-OVK-Review-Revision':v.revision},body:v.body});const d=await r.json();$('message').textContent=r.ok?'Underlaget granskat. Intyg kan nu utfärdas.':'Fel: '+JSON.stringify(d);};
$('list').onclick=async()=>{const p=$('project').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/intyg');const d=await r.json();if(!r.ok){$('message').textContent='Fel: '+JSON.stringify(d);return}$('items').innerHTML='<table><tr><th>Intyg</th><th>Besiktning</th><th>Resultat</th><th>Nästa frist</th></tr>'+d.intyg.map(x=>'<tr><td>'+esc(x.intyg_id)+'</td><td>'+esc(x.inspection_id)+'</td><td>'+esc(x.result)+'</td><td>'+esc(x.next_inspection_due||'—')+'</td></tr>').join('')+'</table>'};
$('anslag').onclick=()=>{const p=$('project').value,i=$('intyg').value;window.open('/api/ovk/projects/'+encodeURIComponent(p)+'/intyg/'+encodeURIComponent(i)+'/anslag','_blank')};init();
</script></body></html>"""
