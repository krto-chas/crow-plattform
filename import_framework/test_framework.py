from pathlib import Path

import pytest

from crow_import_framework import ImportManager, create_default_registry


def test_registry_exposes_core_formats() -> None:
    formats = {plugin.format_id for plugin in create_default_registry().plugins()}
    assert {"pdf", "ifc", "dxf", "dwg", "image", "json", "csv", "docx", "xlsx"} <= formats


def test_csv_is_normalized(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_text("name,value\nflow,120\n", encoding="utf-8")
    asset = ImportManager(create_default_registry()).import_file(source)
    assert asset.format_id == "csv"
    assert asset.metadata["row_count"] == 2
    assert len(asset.observations) == 2


def test_ifc_structure_is_normalized(tmp_path: Path) -> None:
    source = tmp_path / "model.ifc"
    source.write_text(
        "ISO-10303-21;\nHEADER;FILE_SCHEMA(('IFC4'));ENDSEC;\nDATA;\n#1=IFCPROJECT('x');\n#2=IFCFLOWSEGMENT('y');\n#3=IFCFLOWSEGMENT('z');\nENDSEC;END-ISO-10303-21;",
        encoding="utf-8",
    )
    asset = ImportManager(create_default_registry()).import_file(source)
    assert asset.metadata["schema"] == "IFC4"
    assert asset.metadata["entity_count"] == 3
    assert any(item["name"] == "IFCFLOWSEGMENT" and item["count"] == 2 for item in asset.structure)


def test_unknown_format_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "unknown.bin"
    source.write_bytes(b"unknown")
    with pytest.raises(ValueError):
        ImportManager(create_default_registry()).import_file(source)


def test_ifc_preview_exposes_model_tree(tmp_path: Path) -> None:
    source = tmp_path / "model.ifc"
    source.write_text(
        "ISO-10303-21;\nHEADER;FILE_SCHEMA(('IFC4'));ENDSEC;\nDATA;\n"
        "#1=IFCPROJECT('gid',$,'Project');\n"
        "#2=IFCBUILDING('gid',$,'Building A');\n"
        "#3=IFCFLOWSEGMENT('gid',$,'Duct 1');\nENDSEC;END-ISO-10303-21;",
        encoding="utf-8",
    )
    asset = ImportManager(create_default_registry()).import_file(source)
    assert asset.preview["kind"] == "ifc_model_tree"
    assert asset.metadata["spatial_count"] == 2
    assert any(item["type"] == "IFCBUILDING" for item in asset.preview["instances"])


def test_dxf_preview_extracts_basic_geometry(tmp_path: Path) -> None:
    source = tmp_path / "drawing.dxf"
    source.write_text(
        "0\nSECTION\n2\nENTITIES\n"
        "0\nLINE\n8\nVENT\n10\n0\n20\n0\n11\n100\n21\n50\n"
        "0\nCIRCLE\n8\nVENT\n10\n20\n20\n20\n40\n5\n"
        "0\nENDSEC\n0\nEOF\n",
        encoding="utf-8",
    )
    asset = ImportManager(create_default_registry()).import_file(source)
    assert asset.preview["kind"] == "dxf_2d"
    assert len(asset.preview["geometry"]) == 2
    assert asset.metadata["preview_entity_count"] == 2
