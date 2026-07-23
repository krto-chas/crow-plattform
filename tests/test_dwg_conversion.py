"""Tests use a fake converter executable so the full flow — discovery,
isolation, derivative linking, failure modes — is verified without the
proprietary ODA binary. The real binary honours the same CLI contract."""

import stat
from pathlib import Path

from crow_dwg_conversion import (
    CONVERTER_ENV_VAR,
    ConversionStatus,
    OdaConverter,
    convert_dwg,
)

FAKE_OK = """#!/usr/bin/env python3
import sys
from pathlib import Path
in_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
for dwg in in_dir.glob("*.dwg"):
    content = "0\\nSECTION\\n2\\nENTITIES\\n0\\nENDSEC\\n0\\nEOF\\n"
    (out_dir / (dwg.stem + ".dxf")).write_text(content)
"""

FAKE_HANG = "#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n"
FAKE_FAIL = "#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n"


def make_fake(tmp_path: Path, script: str) -> Path:
    exe = tmp_path / "ODAFileConverter"
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def make_dwg(tmp_path: Path, name: str = "V-57-1-01.dwg", header: bytes = b"AC1032rest") -> Path:
    path = tmp_path / name
    path.write_bytes(header)
    return path


def test_successful_conversion_links_original_and_derivative(tmp_path: Path) -> None:
    converter = OdaConverter(executable=make_fake(tmp_path, FAKE_OK), timeout_s=30)
    source = make_dwg(tmp_path)
    result = converter.convert(source, output_dir=tmp_path / "out")

    assert result.status is ConversionStatus.CONVERTED
    assert result.derived_path is not None and result.derived_path.is_file()
    assert result.derived_path.name == "V-57-1-01.derived.dxf"
    assert result.source_sha256 and result.derived_sha256
    assert result.source_sha256 != result.derived_sha256
    payload = result.as_payload()
    assert payload["policy"].startswith("Original DWG bevaras")
    # original untouched
    assert source.read_bytes().startswith(b"AC")


def test_input_hardening_rejects_bad_signature_size_and_extension(tmp_path: Path) -> None:
    converter = OdaConverter(executable=make_fake(tmp_path, FAKE_OK))
    not_dwg = make_dwg(tmp_path, header=b"PK\x03\x04zip")
    assert converter.convert(not_dwg).status is ConversionStatus.INPUT_REJECTED

    wrong_ext = tmp_path / "model.dxf"
    wrong_ext.write_bytes(b"AC1032")
    assert converter.convert(wrong_ext).status is ConversionStatus.INPUT_REJECTED

    empty = tmp_path / "empty.dwg"
    empty.write_bytes(b"")
    assert converter.convert(empty).status is ConversionStatus.INPUT_REJECTED

    small_limit = OdaConverter(executable=make_fake(tmp_path, FAKE_OK), max_input_bytes=4)
    assert small_limit.convert(make_dwg(tmp_path, "big.dwg")).status is (
        ConversionStatus.INPUT_REJECTED
    )


def test_timeout_is_reported_not_raised(tmp_path: Path) -> None:
    converter = OdaConverter(executable=make_fake(tmp_path, FAKE_HANG), timeout_s=1)
    result = converter.convert(make_dwg(tmp_path))
    assert result.status is ConversionStatus.TIMEOUT
    assert "1s" in (result.reason or "")


def test_converter_failure_captures_exit_code(tmp_path: Path) -> None:
    converter = OdaConverter(executable=make_fake(tmp_path, FAKE_FAIL), timeout_s=10)
    result = converter.convert(make_dwg(tmp_path))
    assert result.status is ConversionStatus.FAILED
    assert "exit code 3" in (result.reason or "")


def test_unavailable_converter_yields_structured_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(CONVERTER_ENV_VAR, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))  # empty dir: nothing discoverable
    result = convert_dwg(make_dwg(tmp_path))
    assert result.status is ConversionStatus.CONVERTER_UNAVAILABLE
    assert CONVERTER_ENV_VAR in (result.reason or "")


def test_discovery_via_env_var(tmp_path: Path, monkeypatch) -> None:
    exe = make_fake(tmp_path, FAKE_OK)
    monkeypatch.setenv(CONVERTER_ENV_VAR, str(exe))
    converter = OdaConverter.discover()
    assert converter is not None and converter.executable == exe
