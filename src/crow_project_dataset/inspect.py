from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path

from .models import DatasetSource, ReferenceQuality, SourceRole, relative_external_path

_DWG_VERSIONS = {
    b"AC1015": "AutoCAD 2000/2000i/2002",
    b"AC1018": "AutoCAD 2004/2005/2006",
    b"AC1021": "AutoCAD 2007/2008/2009",
    b"AC1024": "AutoCAD 2010/2011/2012",
    b"AC1027": "AutoCAD 2013/2014/2015/2016/2017",
    b"AC1032": "AutoCAD 2018+",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def detect_format(path: Path) -> tuple[str, str, str | None]:
    suffix = path.suffix.lower()
    head = path.read_bytes()[:4096]
    if suffix == ".dwg" or head[:6] in _DWG_VERSIONS:
        signature = head[:6]
        version = _DWG_VERSIONS.get(signature, signature.decode("ascii", "replace"))
        return "dwg", "application/acad", version
    if suffix == ".ifc" or b"ISO-10303-21" in head:
        text = head.decode("latin-1", "ignore")
        match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text, re.IGNORECASE)
        return "ifc", "application/x-step", match.group(1) if match else None
    if suffix == ".pdf" or head.startswith(b"%PDF-"):
        pdf_version: str | None = None
        if head.startswith(b"%PDF-"):
            pdf_version = head[5:8].decode("ascii", "replace")
        return "pdf", "application/pdf", pdf_version
    if suffix == ".dxf":
        return "dxf", "image/vnd.dxf", None
    if suffix == ".zip" or head.startswith(b"PK\x03\x04"):
        return "zip", "application/zip", None
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return suffix.lstrip(".") or "binary", media_type, None


def inspect_source(
    path: Path,
    *,
    source_id: str,
    role: SourceRole,
    reference_quality: ReferenceQuality,
    notes: tuple[str, ...] = (),
    external_base: Path | None = None,
) -> DatasetSource:
    if not path.is_file():
        raise FileNotFoundError(path)
    format_id, media_type, format_version = detect_format(path)
    return DatasetSource(
        source_id=source_id,
        filename=path.name,
        role=role,
        reference_quality=reference_quality,
        size_bytes=path.stat().st_size,
        checksum_sha256=sha256_file(path),
        media_type=media_type,
        format_id=format_id,
        format_version=format_version,
        notes=notes,
        external_path=relative_external_path(path, external_base),
    )
