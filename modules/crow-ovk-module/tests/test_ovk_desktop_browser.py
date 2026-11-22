"""Körda webbläsartester för skrivbordsarbetsplatsens översikt.

Sidan ritas helt av skript, så textjämförelser av filerna visar inte om
arbetskön faktiskt kommer upp. De här testerna kör sidan mot en riktig server
med sparade uppdrag.

Testerna hoppas över om Playwright eller en Chrome-installation saknas.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from crow_ovk_fastighet import Adress, Byggnad, Fastighet, FastighetRepository
from pytest import MonkeyPatch
from test_ovk_field_browser import _free_port, browser  # noqa: F401
from test_ovk_overview_surface import _DONE, _issue, _record, _snapshot
from test_ovk_workflow import _write_entitlements

from crow_document_intelligence.service import create_project
from crow_ovk_module.ovk_protocol_source import save_protocol_source
from crow_ovk_workflow import OvkWorkflowRepository
from crow_workbench.shell import create_app

pytest.importorskip("playwright.sync_api")

_DESKTOP = {"width": 1366, "height": 800}
_PHONE = {"width": 390, "height": 844}


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """Ett uppdrag i varje läge som arbetskön ska kunna visa."""
    # Mobilens startsida listar Workbench-projekt, så projektet måste finnas där.
    create_project(tmp_path / "projects" / "p1", "Kv. Lärkan", "p1")
    workflows = OvkWorkflowRepository(tmp_path)
    workflows.save(_record("ovk-planerad"))
    workflows.save(_record("ovk-pagaende"))
    _snapshot(tmp_path, "ovk-pagaende")
    workflows.save(_record("ovk-granska"))
    _snapshot(tmp_path, "ovk-granska", completed=_DONE)
    # Protokollklart men inte klarmarkerat i fält: leveransklart med upplysning.
    unmarked = _record("ovk-omarkerad", ready=True)
    workflows.save(unmarked)
    _snapshot(tmp_path, "ovk-omarkerad")
    save_protocol_source(tmp_path, "p1", "ovk-omarkerad", unmarked)
    workflows.save(_record("ovk-klar", ready=True))
    issued = _record("ovk-utfardad", ready=True)
    workflows.save(issued)
    _issue(tmp_path, issued)
    return tmp_path


@pytest.fixture
def base_url(data_root: Path, monkeypatch: MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    monkeypatch.delenv("CROW_AUTH_MODE", raising=False)
    _write_entitlements(data_root)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(data_root), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("testservern startade inte")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _open(browser: Any, url: str, viewport: dict[str, int]) -> tuple[Any, list[str], list[str]]:  # noqa: F811
    page = browser.new_page(viewport=viewport)
    errors: list[str] = []
    requests: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))
    page.goto(url)
    return page, errors, requests


def _statuses(page: Any) -> list[str]:
    result: list[str] = page.eval_on_selector_all(
        "#overviewItems tr", "rows => rows.map(row => row.dataset.status)"
    )
    return result


def _queue(page: Any) -> dict[str, str]:
    result: dict[str, str] = page.eval_on_selector_all(
        "#queue button",
        "cards => Object.fromEntries(cards.map(c => "
        "[c.dataset.status, c.querySelector('strong').textContent]))",
    )
    return result


def test_overview_shows_the_work_queue_with_next_steps(base_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    assert _queue(page) == {
        "att_granska": "1",
        "leveransklar": "2",
        "pagaende": "1",
        "planerad": "1",
        "utfardad": "1",
    }
    # Det som kräver handling står först.
    assert _statuses(page) == [
        "att_granska",
        "leveransklar",
        "leveransklar",
        "pagaende",
        "planerad",
        "utfardad",
    ]
    assert page.inner_text("#overviewStatus") == "Visar 6 uppdrag."
    assert page.is_hidden("#overviewWarning")
    steps = page.eval_on_selector_all(
        "#overviewItems tr a.button", "links => links.map(a => [a.textContent, a.pathname])"
    )
    assert ["Utfärda intyg", "/ovk/intyg"] in steps
    assert ["Öppna i fält", "/ovk/falt"] in steps
    assert ["Granska", "/ovk/besiktning"] in steps
    # Inga interna id:n i tabellen.
    table = page.inner_text("#overviewTable")
    assert "ovk-" not in table
    assert "p1" not in table
    assert errors == []
    page.close()


def test_unmarked_field_work_is_a_hint_not_an_obstacle(base_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    hints = page.eval_on_selector_all(
        "#overviewItems tr",
        "rows => rows.map(row => [...row.querySelectorAll('.ovk-hint')].map(h => h.textContent))",
    )
    marked = [row for row in hints if "Fältarbetet är inte klarmarkerat i fältappen." in row]
    assert len(marked) == 1
    row = page.locator("#overviewItems tr", has_text="klarmarkerat")
    assert row.get_attribute("data-status") == "leveransklar"
    assert row.locator("a.button").inner_text() == "Utfärda intyg"
    assert errors == []
    page.close()


def test_queue_card_and_search_filter_the_list(base_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    card = "#queue button[data-status=leveransklar]"
    page.focus(card)
    page.keyboard.press("Enter")
    assert _statuses(page) == ["leveransklar", "leveransklar"]
    assert page.input_value("#overviewFilter") == "leveransklar"
    assert page.get_attribute(card, "aria-pressed") == "true"
    assert page.inner_text("#overviewStatus") == "Visar 2 av 6 uppdrag."
    # Korten ritas om; tangentbordsfokus ska stå kvar på det aktiverade kortet.
    assert page.evaluate("() => document.activeElement.dataset.status") == "leveransklar"

    page.keyboard.press("Enter")
    assert len(_statuses(page)) == 6

    page.fill("#overviewSearch", "finns inte")
    assert page.is_hidden("#overviewTable")
    assert page.inner_text("#overviewEmpty") == "Inga uppdrag matchar urvalet."
    page.fill("#overviewSearch", "lärkan")
    assert len(_statuses(page)) == 6
    assert errors == []
    page.close()


def test_navigation_has_eight_workspaces_and_review_is_a_view(base_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, base_url + "/ovk?vy=granskning", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    entries = page.eval_on_selector_all(
        "#ovkNav > *", "nodes => nodes.map(n => [n.tagName, n.textContent.trim()])"
    )
    assert [text for _, text in entries] == [
        "Översikt och arbetskö",
        "Uppdrag och planering",
        "Kunder och fastigheter",
        "Besiktningar och uppföljning",
        "Granskning",
        "Protokoll, intyg och bilagor",
        "Bevakning och ombesiktningar",
        "Administration och inställningar Kommer",
    ]
    # Ytan som inte finns ännu är inte en länk.
    assert entries[-1][0] == "SPAN"
    assert page.inner_text("#ovkNav a[aria-current=page]") == "Granskning"
    # Plattformens egen navigation står kvar ovanför.
    assert page.locator("aside nav").first.locator("a", has_text="OVK").count() == 1
    assert page.input_value("#overviewFilter") == "vy:granskning"
    assert _statuses(page) == ["att_granska", "leveransklar", "leveransklar"]
    assert errors == []
    page.close()


def test_unreadable_assignments_are_announced(
    base_url: str,
    data_root: Path,
    browser: Any,  # noqa: F811
) -> None:
    (data_root / "projects" / "p1" / "ovk" / "trasig.json").write_text("{", encoding="utf-8")
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    warning = page.inner_text("#overviewWarning")
    assert "Översikten är ofullständig." in warning
    assert "Uppdrag trasig i projekt p1: besiktningsposten går inte att läsa." in warning
    assert len(_statuses(page)) == 6
    assert errors == []
    page.close()


def test_overview_fits_the_desktop_without_sideways_scroll(base_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0
    assert errors == []
    page.close()


def test_phone_keeps_the_field_home_and_skips_the_desktop_queue(
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, requests = _open(browser, base_url + "/ovk", _PHONE)
    page.wait_for_selector("#fieldPrepared:not([hidden]) .field-card")

    assert page.is_visible("#fieldHomeTitle")
    assert page.is_hidden("#overview")
    assert page.locator("#fieldPrepared .field-card").count() == 1
    assert page.locator("#fieldOngoing .field-card").count() == 2
    assert not any(url.endswith("/api/ovk/uppdrag") for url in requests)
    assert errors == []
    page.close()


def test_other_workspace_ids_do_not_select_a_view(base_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, base_url + "/ovk?vy=uppdrag", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    assert page.inner_text("#ovkNav a[aria-current=page]") == "Översikt och arbetskö"
    assert page.input_value("#overviewFilter") == ""
    assert errors == []
    page.close()


def test_failed_assignment_request_is_stated_not_shown_as_empty(
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page = browser.new_page(viewport=_DESKTOP)
    page.route("**/api/ovk/uppdrag", lambda route: route.fulfill(status=500, body="{}"))
    page.goto(base_url + "/ovk")
    page.wait_for_function(
        "() => document.getElementById('overviewStatus').textContent.startsWith('Uppdragen kunde')"
    )

    assert page.is_hidden("#overviewTable")
    assert page.is_hidden("#overviewEmpty")
    assert page.locator("#queue button").count() == 0
    page.close()


def test_empty_but_incomplete_overview_does_not_claim_there_is_nothing(
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    body = (
        '{"uppdrag":[],"antal":{},"statusar":{"planerad":"Planerad"},"fullstandig":false,'
        '"ej_lasbara":[{"project_id":"p1","inspection_id":"","orsak":"projekt"}]}'
    )
    page = browser.new_page(viewport=_DESKTOP)
    page.route(
        "**/api/ovk/uppdrag",
        lambda route: route.fulfill(status=200, content_type="application/json", body=body),
    )
    page.goto(base_url + "/ovk")
    page.wait_for_selector("#overviewWarning:not([hidden])")

    assert page.inner_text("#overviewEmpty") == "Inga uppdrag kunde läsas. Se varningen ovan."
    assert "Projekt p1: projektets register går inte att läsa." in page.inner_text(
        "#overviewWarning"
    )
    page.close()


def test_names_from_the_server_are_shown_as_text(base_url: str, browser: Any) -> None:  # noqa: F811
    hostile = "<img src=x onerror=window.__hit=1>"
    body = json.dumps(
        {
            "uppdrag": [
                {
                    "project_id": "p1",
                    "inspection_id": "i1",
                    "objekt": "X",
                    "fastighetsbeteckning": hostile,
                    "adress": None,
                    "byggnad": None,
                    "system": [],
                    "besiktningsman": None,
                    "planerat_datum": None,
                    "status": "ny_status",
                    "status_text": "Ny status",
                    "oppna_granskningar": 0,
                    "falt": {"synkad": False, "ogonblicksbild_andrad": None, "avslutat": None},
                    "nasta_steg": {"text": "Ut", "href": "https://example.invalid/"},
                }
            ],
            "antal": {"ny_status": 1},
            "statusar": {"ny_status": "Ny status"},
            "fullstandig": True,
            "ej_lasbara": [],
        }
    )
    page = browser.new_page(viewport=_DESKTOP)
    page.route(
        "**/api/ovk/uppdrag",
        lambda route: route.fulfill(status=200, content_type="application/json", body=body),
    )
    page.goto(base_url + "/ovk")
    page.wait_for_selector("#overviewItems tr")

    assert page.inner_text("#overviewItems tr td:first-child") == hostile
    assert page.evaluate("() => window.__hit") is None
    # En status som skriptet inte känner till syns ändå i kön och i filtret.
    assert _queue(page)["ny_status"] == "1"
    assert page.locator("#overviewFilter option[value=ny_status]").count() == 1
    # En länk utanför OVK följs inte.
    assert page.locator("#overviewItems tr a").count() == 0
    page.close()


def test_phone_home_works_when_the_desktop_scripts_fail_to_load(
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page = browser.new_page(viewport=_PHONE)
    for script in ("skal.js", "oversikt.js"):
        page.route("**/ovk/" + script, lambda route: route.abort())
    page.goto(base_url + "/ovk")
    page.wait_for_selector("#fieldPrepared:not([hidden]) .field-card")

    assert page.locator("#fieldOngoing .field-card").count() == 2
    # Utan skalets skript står de statiska länkarna kvar.
    assert page.locator("#ovkNav a").count() == 5
    page.close()


def test_resizing_switches_between_phone_home_and_desktop_queue(
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, requests = _open(browser, base_url + "/ovk", _PHONE)
    page.wait_for_selector("#fieldPrepared:not([hidden]) .field-card")
    assert not any(url.endswith("/api/ovk/uppdrag") for url in requests)

    page.set_viewport_size(_DESKTOP)
    page.wait_for_selector("#overviewItems tr")
    assert len(_statuses(page)) == 6

    page.set_viewport_size(_PHONE)
    page.wait_for_selector("#fieldPrepared:not([hidden]) .field-card")
    assert page.is_hidden("#overview")
    assert errors == []
    page.close()


@pytest.fixture
def register_url(tmp_path: Path, monkeypatch: MonkeyPatch) -> Iterator[str]:
    """Två fastigheter i var sitt Workbench-projekt, den ena med besiktningar."""
    for project_id, name in (("p1", "Kv. Lärkan"), ("p2", "Kv. Örnen")):
        create_project(tmp_path / "projects" / project_id, name, project_id)
    repository = FastighetRepository(tmp_path)
    repository.save(
        Fastighet(
            fastighet_id="object-1",
            project_id="p1",
            fastighetsbeteckning="Lärkan 4",
            byggnadens_adress=Adress(gata="Storgatan 1", postnr="185 31", ort="Vaxholm"),
            byggnadsagare_namn="Brf Lärkan",
            byggnader=(Byggnad(byggnad_id="building-1", internt_namn="Hus A"),),
        )
    )
    repository.save(
        Fastighet(
            fastighet_id="object-2",
            project_id="p2",
            fastighetsbeteckning="Örnen 1",
            byggnadens_adress=Adress(gata="Bergsvägen 3", postnr="183 30", ort="Täby"),
            byggnadsagare_namn="<b>Örnen Fastigheter</b>",
        )
    )
    issued = _record("ovk-utfardad", ready=True)
    OvkWorkflowRepository(tmp_path).save(issued)
    _issue(tmp_path, issued)
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    monkeypatch.delenv("CROW_AUTH_MODE", raising=False)
    _write_entitlements(tmp_path)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(tmp_path), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("testservern startade inte")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _register_rows(page: Any) -> list[list[str]]:
    result: list[list[str]] = page.eval_on_selector_all(
        "#registerItems tr",
        # Kolumnen Kund (index 1) läses för sig, så att övriga index står kvar.
        "rows => rows.map(row => [...row.cells].filter((_, i) => i !== 1).slice(0, 5)"
        ".map(c => c.innerText.trim()))",
    )
    return result


def test_property_register_lists_all_properties(register_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")

    rows = _register_rows(page)
    assert [row[0].splitlines()[0] for row in rows] == ["Lärkan 4", "Örnen 1"]
    assert rows[0][0].splitlines()[1] == "Storgatan 1, 185 31 Vaxholm"
    assert rows[0][1] == "Brf Lärkan"
    assert rows[0][2].splitlines() == ["1", "Hus A"]
    assert rows[0][3].splitlines() == ["2026-12-02", "1 besiktning"]
    assert rows[0][4] != "—"
    # En fastighet utan byggnader och besiktningar påstår ingenting.
    assert rows[1][2] == "—"
    assert rows[1][3] == "Ingen besiktning"
    assert rows[1][4] == "—"
    # Namn från registret visas som text.
    assert rows[1][1] == "<b>Örnen Fastigheter</b>"
    assert page.inner_text("#registerStatus") == "Visar 2 fastigheter."
    assert page.inner_text("#ovkNav a[aria-current=page]") == "Kunder och fastigheter"
    assert page.locator("#ovkNav > *").count() == 8
    assert errors == []
    page.close()


def test_property_register_search_and_open(register_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")

    page.fill("#registerSearch", "täby")
    assert [row[0].splitlines()[0] for row in _register_rows(page)] == ["Örnen 1"]
    assert page.inner_text("#registerStatus") == "Visar 1 av 2 fastigheter."
    page.fill("#registerSearch", "finns inte")
    assert page.inner_text("#registerEmpty") == "Inga fastigheter matchar sökningen."
    page.fill("#registerSearch", "")

    page.locator("#registerItems tr", has_text="Lärkan 4").locator("button").click()
    page.wait_for_function("() => document.getElementById('beteckning').value === 'Lärkan 4'")
    assert page.input_value("#project") == "p1"
    assert page.input_value("#fastighetList") == "object-1"
    assert page.input_value("#agare") == "Brf Lärkan"
    assert errors == []
    page.close()


def test_new_inspection_from_the_register_selects_the_property(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")

    page.locator("#registerItems tr", has_text="Lärkan 4").locator("a.button").click()
    page.wait_for_function(
        "() => document.getElementById('selectedPropertyTitle')?.textContent === 'Lärkan 4'"
    )

    assert "/ovk/besiktning" in page.url
    assert page.is_visible("#draftForm")
    assert page.is_hidden("#propertySearchForm")
    assert page.input_value("#draftProject") == "p1"
    assert page.input_value("#draftProperty") == "object-1"
    assert page.input_value("#draftBuilding") == "building-1"
    assert errors == []
    page.close()


def test_unknown_property_in_the_link_falls_back_to_search(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    url = register_url + "/ovk/besiktning?new=1&project_id=p1&fastighet_id=finns-inte"
    page, errors, _ = _open(browser, url, _DESKTOP)
    page.wait_for_function(
        "() => document.getElementById('propertySearchStatus')"
        ".textContent.startsWith('Fastigheten kunde')"
    )

    assert page.is_visible("#propertySearchForm")
    assert page.is_hidden("#draftForm")
    assert errors == []
    page.close()


def test_opening_from_the_register_changes_nothing_when_declined(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")
    page.wait_for_selector("#project option[value=p1]", state="attached")
    # Användaren har börjat fylla i en ny fastighet i ett annat projekt.
    page.select_option("#project", "p2")
    page.fill("#beteckning", "Påbörjad 9")
    questions: list[str] = []

    def decline(dialog: Any) -> None:
        questions.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", decline)
    page.locator("#registerItems tr", has_text="Lärkan 4").locator("button").click()
    page.wait_for_function("() => true")

    assert questions == ["Formuläret innehåller uppgifter. Ersätt dem med den valda fastigheten?"]
    # Projektet är inte bytt, så det påbörjade kan inte sparas i fel projekt.
    assert page.input_value("#project") == "p2"
    assert page.input_value("#beteckning") == "Påbörjad 9"
    assert errors == []
    page.close()


def test_opening_a_property_whose_project_is_not_listed_is_refused(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")
    page.wait_for_selector("#project option[value=p1]", state="attached")
    page.evaluate("() => document.querySelector('#project option[value=p1]').remove()")

    page.locator("#registerItems tr", has_text="Lärkan 4").locator("button").click()
    page.wait_for_function(
        "() => document.getElementById('status').textContent.startsWith('Fastighetens projekt')"
    )

    assert page.input_value("#project") == ""
    assert page.input_value("#beteckning") == ""
    assert errors == []
    page.close()


def test_register_request_failure_is_stated(register_url: str, browser: Any) -> None:  # noqa: F811
    page = browser.new_page(viewport=_DESKTOP)
    page.route("**/api/ovk/fastigheter", lambda route: route.fulfill(status=500, body="{}"))
    page.goto(register_url + "/ovk/fastighet")
    page.wait_for_function(
        "() => document.getElementById('registerStatus')"
        ".textContent.startsWith('Fastigheterna kunde')"
    )

    assert page.is_hidden("#registerTable")
    assert page.is_hidden("#registerEmpty")
    page.close()


def test_register_marks_unclear_certificates_and_partial_deadlines(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    def item(name: str, **changes: Any) -> dict[str, Any]:
        return {
            "project_id": "p1",
            "fastighet_id": name,
            "fastighetsbeteckning": name,
            "gata": None,
            "postnr": None,
            "ort": None,
            "kund": None,
            "byggnadsagare": None,
            "byggnader": [],
            "antal_besiktningar": 1,
            "senast_utfardat": None,
            "nasta_besiktning": None,
            "byggnader_utan_frist": 0,
            "intyg_oklart": False,
            "forekomster": 1,
            **changes,
        }

    body = json.dumps(
        {
            "fastigheter": [
                item("Oklar 1", intyg_oklart=True),
                item(
                    "Delvis 2",
                    senast_utfardat="2026-12-02",
                    nasta_besiktning="2029-12-01",
                    byggnader_utan_frist=2,
                ),
                item("Dubbel 3", forekomster=2),
            ],
            "ej_lasbara": [{"project_id": "p9", "orsak": "intyg"}],
            "fullstandig": False,
        }
    )
    page = browser.new_page(viewport=_DESKTOP)
    page.route(
        "**/api/ovk/fastigheter",
        lambda route: route.fulfill(status=200, content_type="application/json", body=body),
    )
    page.goto(register_url + "/ovk/fastighet")
    page.wait_for_selector("#registerItems tr")

    rows = {row[0].splitlines()[0]: row for row in _register_rows(page)}
    assert "Intygets ställning går inte att fastställa." in rows["Oklar 1"][3]
    assert rows["Delvis 2"][4].splitlines() == [
        "2029-12-01",
        "2 byggnader saknar gällande frist.",
    ]
    assert "Finns 2 gånger i registret" in rows["Dubbel 3"][0]
    warning = page.inner_text("#registerWarning")
    assert "p9 (ett intyg anger ett annat projekt)" in warning
    page.close()


def test_kund_is_registered_linked_to_a_property_and_shown_in_the_register(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")
    assert page.inner_text("#kundEmpty") == "Inga kunder är registrerade ännu."

    page.click("#kundNew")
    page.fill("#kundNamn", "Brf Lärkan <b>")
    page.fill("#kundKontaktperson", "Anna Ek")
    page.fill("#kundEpost", "styrelsen@larkan.example")
    page.click("#kundSave")
    page.wait_for_selector("#kundItems tr")

    assert page.is_hidden("#kundForm")
    assert page.inner_text("#kundItems tr td:first-child") == "Brf Lärkan <b>"
    assert page.inner_text("#kundItems tr td:nth-child(3)") == "0"
    assert page.inner_text("#kundStatus") == "Kunden Brf Lärkan <b> är sparad."

    # Kunden väljs på fastigheten och följer med när fastigheten sparas.
    page.locator("#registerItems tr", has_text="Lärkan 4").locator("button").click()
    page.wait_for_function("() => document.getElementById('beteckning').value === 'Lärkan 4'")
    page.select_option("#kund", label="Brf Lärkan <b>")
    page.click("#saveFastighet")
    page.wait_for_function(
        "() => document.querySelector('#registerItems tr td:nth-child(2)').innerText"
        " === 'Brf Lärkan <b>'"
    )
    page.wait_for_function(
        "() => document.querySelector('#kundItems tr td:nth-child(3)').innerText === '1'"
    )

    # Efter omladdning är kunden vald när fastigheten öppnas igen.
    page.reload()
    page.wait_for_selector("#registerItems tr")
    page.wait_for_selector("#kund option:nth-child(2)", state="attached")
    page.locator("#registerItems tr", has_text="Lärkan 4").locator("button").click()
    page.wait_for_function("() => document.getElementById('beteckning').value === 'Lärkan 4'")
    assert page.eval_on_selector("#kund", "s => s.selectedOptions[0].textContent") == (
        "Brf Lärkan <b>"
    )
    page.fill("#registerSearch", "brf lärkan")
    assert len(_register_rows(page)) == 1
    assert errors == []
    page.close()


def test_kund_changed_elsewhere_is_not_overwritten(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")
    page.click("#kundNew")
    page.fill("#kundNamn", "Brf Lärkan")
    page.click("#kundSave")
    page.wait_for_selector("#kundItems tr")

    page.click("#kundItems tr button")
    page.wait_for_selector("#kundForm:not([hidden])")
    # Någon annan sparar samma kund medan formuläret är öppet.
    changed = page.evaluate(
        """async () => {
          const list = await (await fetch('/api/ovk/kunder')).json();
          const kund = await (await fetch('/api/ovk/kunder/' + list.kunder[0].kund_id)).json();
          const response = await fetch('/api/ovk/kunder/' + kund.kund_id, {
            method: 'PUT',
            headers: {'content-type': 'application/json', 'X-OVK-Base-Revision': kund.revision},
            body: JSON.stringify({namn: 'Brf Lärkan', telefon: '08-1'}),
          });
          return response.status;
        }"""
    )
    assert changed == 200
    page.fill("#kundTelefon", "08-2")
    page.click("#kundSave")
    page.wait_for_function(
        "() => document.getElementById('kundFormStatus')"
        ".textContent.startsWith('Kunden har ändrats')"
    )

    assert page.is_visible("#kundForm")
    stored = page.evaluate("async () => (await (await fetch('/api/ovk/kunder')).json()).kunder[0]")
    assert stored["telefon"] == "08-1"
    assert errors == []
    page.close()


def test_organisationsnummer_is_checked_and_kept_on_the_kund(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")
    page.click("#kundNew")
    page.fill("#kundNamn", "Brf Lärkan")
    page.fill("#kundOrganisationsnummer", "2120000143")
    page.click("#kundSave")
    page.wait_for_function(
        "() => document.getElementById('kundFormStatus')"
        ".textContent.startsWith('Organisationsnumret stämmer inte')"
    )
    assert page.is_visible("#kundForm")
    assert page.locator("#kundItems tr").count() == 0

    page.fill("#kundOrganisationsnummer", "2120000142")
    page.click("#kundSave")
    page.wait_for_selector("#kundItems tr")
    page.click("#kundItems tr button")
    # Kunden hämtas när formuläret öppnas; numret finns inte i listan.
    page.wait_for_function(
        "() => document.getElementById('kundOrganisationsnummer').value === '212000-0142'"
    )
    assert page.is_visible("#kundForm")
    assert errors == []
    page.close()


def test_trapphus_is_registered_and_groups_the_units(
    register_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, register_url + "/ovk/fastighet", _DESKTOP)
    page.wait_for_selector("#registerItems tr")
    page.locator("#registerItems tr", has_text="Lärkan 4").locator("button").click()
    page.wait_for_function("() => document.getElementById('beteckning').value === 'Lärkan 4'")
    page.select_option("#inventoryBuilding", label="Hus A")
    page.wait_for_function("() => !document.getElementById('inventoryFields').disabled")
    # Utan trapphus finns varken val på enheten eller i massregistreringen.
    assert page.is_disabled("#bulkTrapphus")

    page.click("#inventoryAddTrapphus")
    page.click("#inventorySave")
    assert page.inner_text("#inventoryStatus") == "Ange namn på varje trapphus."
    page.fill("#inventoryTrapphus .bygg:nth-child(1) label:nth-of-type(1) input", "A <b>")
    page.fill("#inventoryTrapphus .bygg:nth-child(1) label:nth-of-type(2) input", "Storgatan 1A")
    page.click("#inventoryAddTrapphus")
    page.fill("#inventoryTrapphus .bygg:nth-child(2) label:nth-of-type(1) input", "B")

    # Massregistrering lägger lägenheterna i valt trapphus.
    page.eval_on_selector("#bulkPanel", "d => { d.open = true }")
    page.fill("#bulkFloors", "1")
    page.fill("#bulkPerFloor", "2")
    page.select_option("#bulkTrapphus", label="A <b> – Storgatan 1A")
    page.click("#bulkPreview")
    assert page.inner_text("#bulkStatus").startswith("Trapphus A <b> – Storgatan 1A · 2 lägenheter")
    page.click("#bulkApply")
    page.click("#inventoryAddUnit")
    headings = page.eval_on_selector_all(
        "#inventoryUnits .trapphus-group h4", "items => items.map(h => h.textContent)"
    )
    assert headings == [
        "Trapphus A <b> – Storgatan 1A · 2 enheter",
        "Trapphus B · 0 enheter",
        "Utan trapphus · 1 enhet",
    ]

    # Den lösa enheten flyttas till trapphus B och hamnar under den rubriken.
    loose = page.locator("#inventoryUnits .trapphus-group").nth(2)
    loose.locator("input").first.fill("1101")
    loose.locator("select[aria-label='Trapphus för enheten']").select_option(label="B")
    assert page.eval_on_selector_all(
        "#inventoryUnits .trapphus-group h4", "items => items.map(h => h.textContent)"
    ) == ["Trapphus A <b> – Storgatan 1A · 2 enheter", "Trapphus B · 1 enhet"]

    # Ett trapphus med enheter kan inte tas bort.
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#inventoryTrapphus .bygg").nth(1).locator("button").click()
    assert "Flytta först trapphusets lägenheter" in page.inner_text("#inventoryStatus")

    page.click("#inventorySave")
    page.wait_for_function(
        "() => document.getElementById('inventoryStatus').textContent"
        " === 'Byggnadsstruktur sparad.'"
    )
    stored = page.evaluate(
        "() => fetch('/api/ovk/projects/p1/fastighet/object-1/byggnad/building-1/struktur',"
        " {cache: 'no-store'}).then(r => r.json())"
    )
    assert [item["namn"] for item in stored["trapphus"]] == ["A <b>", "B"]
    names = {item["trapphus_id"]: item["namn"] for item in stored["trapphus"]}
    assert sorted((unit["number"], names[unit["trapphus_id"]]) for unit in stored["units"]) == [
        ("1001", "A <b>"),
        ("1002", "A <b>"),
        ("1101", "B"),
    ]
    assert errors == []
    page.close()
