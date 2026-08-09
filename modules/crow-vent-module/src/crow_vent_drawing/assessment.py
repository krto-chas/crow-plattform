from __future__ import annotations

from .models import DrawingTextAssessment
from .parser import extract_apartments, extract_levels, parse_drawing_number

_PLAN_PARTS_WITH_APARTMENTS = {"01", "03", "04"}
_APARTMENT_PLAN_RANGE = range(10, 14)


def assess_drawing_text(
    text: str,
    document_id: str,
    extraction_status: str,
) -> DrawingTextAssessment:
    """Bedömer om ritningens textlager räcker för lägenhetsdata.

    En planritning för bostadsplan (del 01/03/04, plan 10–13) utan
    lägenhetsetiketter flaggas för rasterläsning eller DWG-original i stället
    för att tolkas som "inga lägenheter". Enkälleläsning utan denna flagga är
    exakt felet som undervärderade trapphus 4 i det manuella anbudsarbetet.
    """
    apartments = extract_apartments(text, document_id)
    levels = extract_levels(text, document_id)
    drawing = parse_drawing_number(document_id)
    notes: list[str] = []
    expects_apartments = (
        drawing is not None
        and (drawing.series == "5" or drawing.part in _PLAN_PARTS_WITH_APARTMENTS)
        and drawing.plan.isdigit()
        and int(drawing.plan) in _APARTMENT_PLAN_RANGE
    )
    needs_review = extraction_status != "text_available"
    if expects_apartments and not apartments:
        needs_review = True
        notes.append(
            "Bostadsplanritning utan lägenhetsetiketter i textlagret; "
            "kräver raster/OCR eller DWG-original."
        )
    return DrawingTextAssessment(
        document_id=document_id,
        extraction_status=extraction_status,
        apartment_label_count=len(apartments),
        level_label_count=len(levels),
        needs_raster_review=needs_review,
        notes=tuple(notes),
    )
