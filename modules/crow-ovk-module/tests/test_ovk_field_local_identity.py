from pathlib import Path

from test_ovk_field_history import _client


def test_field_uses_composite_local_keys(tmp_path: Path) -> None:
    client = _client(tmp_path)
    script = client.get("/ovk/falt/app.js").text
    assert "const DB_VERSION = 3;" in script
    assert "keyPath:['project_id','inspection_id']" in script
    assert "keyPath:['project_id','inspection_id','photo_id']" in script
    assert "blob.inspection_id===draft.inspection_id" in script
    assert "blob.sha256===photo.sha256" in script
    assert "dbGet(DRAFT_STORE,draftKey(projectId,inspectionId))" in script
    assert "dbGet(MEDIA_STORE,mediaKey(projectId,inspectionId,photo.photo_id))" in script
    assert "deleteObjectStore" not in script
