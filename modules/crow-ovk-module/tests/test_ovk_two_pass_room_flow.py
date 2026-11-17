"""Tvåvarvsflödet: ett rum i taget i varv 1, samma ordning i varv 2, slutkontroll."""

from __future__ import annotations

import re
from importlib import resources


def _page() -> str:
    return (
        resources.files("crow_ovk_module")
        .joinpath("assets", "field.html")
        .read_text(encoding="utf-8")
    )


def test_unit_view_has_one_card_per_step() -> None:
    page = _page()
    start = page.index('<section class="view" id="viewUnit">')
    unit_view = page[start : page.index("</section>", start)]
    assert len(re.findall(r'^    <div class="card">', unit_view, flags=re.MULTILINE)) == 4
    assert "const STEP={setup:0,visual:1,measure:2,review:3};" in page
    assert "'rooms'].includes" not in page


def test_rooms_are_added_one_at_a_time_inside_the_visual_round() -> None:
    page = _page()
    visual = page[page.index("Varv 1 · Visuell kontroll · ") : page.index("Varv 2 · Mätning · ")]
    for element_id in ("roomChips", "roomPresetChips", "ovkRoomName", "ovkRoomSave"):
        assert f'id="{element_id}"' in visual
    assert 'id="fieldTemplatePanel"' in visual
    assert "Lägg till första rummet" in page
    assert "Lägg till minst ett rum innan mätvarvet startar." in page


def test_legacy_room_step_progress_resumes_in_visual_round() -> None:
    page = _page()
    assert "progress.phase==='rooms'?'visual'" in page
    assert "['setup','visual','measure','review'].includes(saved)?saved:'visual'" in page


def test_review_compiles_checks_measurements_findings_and_photos() -> None:
    page = _page()
    for element_id in (
        "ovkUnitReview",
        "ovkReviewWarnings",
        "ovkReviewRooms",
        "unitFindings",
        "ovkFindingActions",
        "classRow",
        "note",
        "ovkReviewPhotoSlot",
        "ovkFindingDelete",
    ):
        assert f'id="{element_id}"' in page
    assert "function reviewWarnings(rooms){" in page
    assert "don finns men ingen mätpunkt är registrerad" in page
    assert "': mätvärde saknas'" in page
    assert "': ej mätbart don saknar foto'" in page
    assert "Varningarna hindrar inte att enheten slutförs." in page


def test_photo_field_follows_the_active_step() -> None:
    page = _page()
    assert 'id="ovkMeasurePhotoSlot" hidden' in page
    assert "$id('ovkMeasurePhotoSlot').hidden=phase!=='measure'||!selected;" in page
    assert "$id('ovkFindingActions').hidden=phase!=='review'||!selected;" in page
    assert page.count('id="photo"') == 1


def test_deleting_a_finding_releases_its_dependents() -> None:
    page = _page()
    assert "state.findings=state.findings.filter(item=>item!==finding);" in page
    assert "if(photo.finding_id===finding.finding_id)photo.finding_id=null;" in page
    assert "point.measurable=true;point.not_measurable_reason=''" in page
    assert "status:'not_checked',note:'',current_finding_id:null,photo_ids:[]" in page
