"""Isolated DWG→DXF conversion via the ODA File Converter.

The converter is an external, licensed-but-free binary from Open Design
Alliance. Crow never links against it: it is executed as an isolated
subprocess with timeout and size limits, in a scratch directory, and the
result is registered as a *derived* artefact linked to the untouched
original through SHA-256 checksums (the original DWG remains the
authoritative evidence — the policy already stated in the geometry
adapters).

Failure is always structured: an unavailable converter, a timeout or a
failed conversion produces a ConversionResult with status and reason,
never an exception mid-pipeline and never a silent loss.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "crow-dwg-conversion-v0.1"
CONVERTER_ENV_VAR = "CROW_ODA_CONVERTER"
DEFAULT_TIMEOUT_S = 120
DEFAULT_MAX_INPUT_BYTES = 500 * 1024 * 1024
DEFAULT_OUTPUT_VERSION = "ACAD2018"


class ConversionStatus(StrEnum):
    CONVERTED = "converted"
    CONVERTER_UNAVAILABLE = "converter_unavailable"
    INPUT_REJECTED = "input_rejected"
    TIMEOUT = "timeout"
    FAILED = "failed"


@dataclass(frozen=True)
class ConversionResult:
    status: ConversionStatus
    source_path: Path
    source_sha256: str | None = None
    derived_path: Path | None = None
    derived_sha256: str | None = None
    converter: str | None = None
    output_version: str = DEFAULT_OUTPUT_VERSION
    reason: str | None = None
    stderr_tail: str | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status.value,
            "source": str(self.source_path),
            "source_sha256": self.source_sha256,
            "derived": str(self.derived_path) if self.derived_path else None,
            "derived_sha256": self.derived_sha256,
            "converter": self.converter,
            "output_version": self.output_version,
            "reason": self.reason,
            "policy": (
                "Original DWG bevaras oförändrad och förblir auktoritativ evidens; "
                "härledd DXF länkas med checksumma och konverterarversion."
            ),
        }


@dataclass(frozen=True)
class OdaConverter:
    """Locates and runs the ODA File Converter in isolation."""

    executable: Path
    timeout_s: int = DEFAULT_TIMEOUT_S
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES
    output_version: str = DEFAULT_OUTPUT_VERSION
    extra_env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def discover(cls, *, timeout_s: int = DEFAULT_TIMEOUT_S) -> OdaConverter | None:
        candidate = os.environ.get(CONVERTER_ENV_VAR)
        if candidate:
            path = Path(candidate)
            if path.is_file() and os.access(path, os.X_OK):
                return cls(executable=path, timeout_s=timeout_s)
            return None
        found = shutil.which("ODAFileConverter")
        if found:
            return cls(executable=Path(found), timeout_s=timeout_s)
        return None

    def convert(self, source: Path, *, output_dir: Path | None = None) -> ConversionResult:
        rejection = self._reject_reason(source)
        if rejection is not None:
            return ConversionResult(ConversionStatus.INPUT_REJECTED, source, reason=rejection)
        source_sha = _sha256_file(source)

        with (
            tempfile.TemporaryDirectory(prefix="crow-oda-in-") as in_dir_raw,
            tempfile.TemporaryDirectory(prefix="crow-oda-out-") as out_dir_raw,
        ):
            in_dir = Path(in_dir_raw)
            out_dir = Path(out_dir_raw)
            safe_name = _safe_stem(source) + ".dwg"
            shutil.copyfile(source, in_dir / safe_name)

            command = [
                str(self.executable),
                str(in_dir),
                str(out_dir),
                self.output_version,
                "DXF",
                "0",  # no recursion
                "1",  # audit input file
            ]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    env={**os.environ, **self.extra_env},
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return ConversionResult(
                    ConversionStatus.TIMEOUT,
                    source,
                    source_sha256=source_sha,
                    converter=str(self.executable),
                    reason=f"Converter exceeded {self.timeout_s}s",
                )

            produced = out_dir / (Path(safe_name).stem + ".dxf")
            if completed.returncode != 0 or not produced.is_file():
                return ConversionResult(
                    ConversionStatus.FAILED,
                    source,
                    source_sha256=source_sha,
                    converter=str(self.executable),
                    reason=f"Converter exit code {completed.returncode}, derived DXF missing"
                    if not produced.is_file()
                    else f"Converter exit code {completed.returncode}",
                    stderr_tail=(completed.stderr or "")[-500:] or None,
                )

            destination_dir = output_dir or source.parent
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / (source.stem + ".derived.dxf")
            shutil.copyfile(produced, destination)
            return ConversionResult(
                ConversionStatus.CONVERTED,
                source,
                source_sha256=source_sha,
                derived_path=destination,
                derived_sha256=_sha256_file(destination),
                converter=str(self.executable),
                output_version=self.output_version,
            )

    def _reject_reason(self, source: Path) -> str | None:
        if not source.is_file():
            return "Source file does not exist"
        if source.suffix.lower() != ".dwg":
            return f"Unexpected extension {source.suffix!r}; only .dwg is accepted"
        size = source.stat().st_size
        if size == 0:
            return "Source file is empty"
        if size > self.max_input_bytes:
            return f"Source exceeds size limit ({size} > {self.max_input_bytes} bytes)"
        header = source.open("rb").read(2)
        if header != b"AC":
            return "File signature is not a DWG header (expected 'AC…')"
        return None


def convert_dwg(source: Path, *, output_dir: Path | None = None) -> ConversionResult:
    """Convenience entry: discover the converter and convert one file."""
    converter = OdaConverter.discover()
    if converter is None:
        return ConversionResult(
            ConversionStatus.CONVERTER_UNAVAILABLE,
            source,
            reason=(
                "ODA File Converter hittades inte. Installera den och sätt "
                f"{CONVERTER_ENV_VAR} eller lägg ODAFileConverter i PATH; "
                "tills dess registreras DWG utan semantisk tolkning."
            ),
        )
    return converter.convert(source, output_dir=output_dir)


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_stem(source: Path) -> str:
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in source.stem)
    return stem[:80] or "drawing"
