"""Omsättning av registrerad besiktningsman till intygets funktionskontrollant."""

from __future__ import annotations

from crow_ovk_intyg import Behorighet as IntygBehorighet
from crow_ovk_intyg import Funktionskontrollant

from .models import Besiktningsman


def funktionskontrollant_from(person: Besiktningsman) -> Funktionskontrollant:
    return Funktionskontrollant(
        name=person.namn,
        behorighet=IntygBehorighet(person.behorighet.value),
        certification_body=person.certifieringsorgan,
        certificate_number=person.certnummer,
        certificate_valid_to=person.giltig_till,
    )
