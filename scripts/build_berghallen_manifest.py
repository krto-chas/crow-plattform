"""Bygg Berghällen-datasetmanifestet från förfrågningszipen.

Kundfilerna checkas aldrig in; endast checksummor och metadata registreras.
Kör:  python scripts/build_berghallen_manifest.py /sökväg/till/Förfrågan_vent_Berghällen.zip
"""

from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

from crow_project_dataset import (
    ProjectDataset,
    ReferenceQuality,
    SourceRole,
    inspect_source,
    write_manifest,
)

_ROLES: dict[str, tuple[SourceRole, ReferenceQuality]] = {
    "V-57-Besk.pdf": (SourceRole.SPECIFICATION, ReferenceQuality.AUTHORITATIVE),
    "V-57-HF-BH.pdf": (SourceRole.SPECIFICATION, ReferenceQuality.AUTHORITATIVE),
    "V-57-8-100.pdf": (SourceRole.DRAWING, ReferenceQuality.AUTHORITATIVE),
    "AF-del Norrberget AB 04.pdf": (SourceRole.SPECIFICATION, ReferenceQuality.AUTHORITATIVE),
    "Förfrågningsbrev.pdf": (SourceRole.SPECIFICATION, ReferenceQuality.SUPPORTING),
    "Förtydligande av ingående arbeten Vent-installationer.pdf": (
        SourceRole.SPECIFICATION,
        ReferenceQuality.AUTHORITATIVE,
    ),
}

_LIMITATIONS = (
    "Vindsplanens rektangulära stråk är bedömda ur etikettkoordinater, inte uppmätt "
    "geometri; DWG-original förbättrar precisionen.",
    "Lägenhetsinventering kräver flera textextraktorer: pdftotext missar delar av "
    "textlagret på V-57-1-4xx04-serien (trapphus 4) som pypdf läser komplett; "
    "enkälleläsning undervärderade trh 4 med 5 lgh i det manuella anbudsarbetet.",
    "Kanallängder i facit är bedömningar från plushöjder och etikettkoordinater "
    "(tolerans 20 %), inte uppmätt verklighet.",
)


def _decoded_name(raw: str) -> str:
    try:
        return raw.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def build(archive: Path, output: Path) -> ProjectDataset:
    sources = [
        inspect_source(
            archive,
            source_id="forfragan-arkiv",
            role=SourceRole.PROJECT_ARCHIVE,
            reference_quality=ReferenceQuality.AUTHORITATIVE,
        )
    ]
    with tempfile.TemporaryDirectory() as scratch, zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            if info.is_dir():
                continue
            name = _decoded_name(info.filename)
            basename = name.rsplit("/", 1)[-1]
            is_plan = basename.startswith("V-57-1-") and basename.endswith(".pdf")
            if basename not in _ROLES and not is_plan:
                continue
            target = Path(scratch) / basename
            target.write_bytes(bundle.read(info))
            role, quality = _ROLES.get(
                basename, (SourceRole.DRAWING, ReferenceQuality.AUTHORITATIVE)
            )
            source = inspect_source(
                target,
                source_id=basename.rsplit(".", 1)[0].lower().replace(" ", "-"),
                role=role,
                reference_quality=quality,
            )
            sources.append(
                type(source)(
                    **{**source.to_dict(), "external_path": name, "notes": tuple(source.notes)}
                )
            )
    dataset = ProjectDataset(
        dataset_id="berghallen-kfu",
        title="Brf Berghällen, Norrberget etapp 2 — förfrågningspaket luftbehandling",
        description=(
            "Komplett förfrågningszip (bygghandling 2025-01-17) som golden project för "
            "provtrycknings- och kalkylkedjan. Kundfiler hålls utanför repot."
        ),
        sources=tuple(sources),
        known_limitations=_LIMITATIONS,
        metadata={"client": "Besqab Projektutveckling AB", "discipline": "V57"},
    )
    write_manifest(dataset, output)
    return dataset


if __name__ == "__main__":
    archive_path = Path(sys.argv[1])
    manifest_path = Path(__file__).resolve().parents[1] / (
        "evidence/reference_datasets/berghallen/manifest.json"
    )
    built = build(archive_path, manifest_path)
    print(f"{len(built.sources)} källor → {manifest_path}")
