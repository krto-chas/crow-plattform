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
    # Någon annan sparar samma kund medan formuläret är öppet.
    changed = page.evaluate(
        """async () => {
          const list = await (await fetch('/api/ovk/kunder')).json();
          const kund = list.kunder[0];
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


def test_protocol_draft_is_built_from_a_chosen_inspection_with_aligned_columns(
    data_root: Path,
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    # Fältappen lämnar sina uppgifter om besiktningen innan den synkar.
    context = data_root / "projects" / "p1" / "ovk-field" / "ovk-planerad" / "context.json"
    context.parent.mkdir(parents=True, exist_ok=True)
    record = OvkWorkflowRepository(data_root).load("p1", "ovk-planerad")
    assert record.planning is not None
    context.write_text(
        json.dumps(
            {
                "inspection_id": "ovk-planerad",
                "project_id": "p1",
                "inspector_id": record.planning.inspector_id,
                "previous_inspection_id": record.planning.previous_inspection_id,
                "system_type": record.inspection.systems[0].system_type,
            }
        ),
        encoding="utf-8",
    )
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_function("() => document.querySelectorAll('#pbInspection option').length > 1")

    # Besiktningen väljs i en lista; inga id:n skrivs eller kopieras in.
    assert page.query_selector("#pbProject") is None
    assert page.eval_on_selector("#pbInspection", "s => s.tagName") == "SELECT"
    labels = page.eval_on_selector_all("#pbInspection option", "o => o.map(x => x.textContent)")
    # Bara planerade besiktningar som inte är protokollklara erbjuds; ett nytt
    # utkast ersätter det förra, så protokollklara och utfärdade byggs inte om härifrån.
    assert labels[0] == "Välj besiktning…"
    assert page.eval_on_selector_all("#pbInspection option", "o => o.map(x => x.value)") == [
        "",
        "ovk-granska",
        "ovk-pagaende",
        "ovk-planerad",
    ]
    page.click(".projectbar details > summary")
    page.click("#pbBuild")
    assert page.inner_text("#pbResult") == "Välj en besiktning."

    synced = page.evaluate(
        """() => fetch('/api/ovk/projects/p1/field/ovk-planerad/sync', {
          method: 'PUT', headers: {'content-type': 'application/json'},
          body: JSON.stringify({inspection_id: 'ovk-planerad',
            units: [{unit_id: 'u1', number: '1701', kind: 'apartment'}],
            rooms: [{room_id: 'r1', unit_id: 'u1', name: 'WC'}],
            measurements: [
              {measurement_id: 'm1', unit_id: 'u1', room_id: 'r1', point_type: 'franluftsdon',
               point_label: 'WC 1', designed_value: '20', measured_value: '15',
               measurable: true, unit_of_measure: 'l/s'}]})}).then(r => r.status)"""
    )
    assert synced == 200
    page.select_option("#pbInspection", "ovk-planerad")
    page.click("#pbBuild")
    page.wait_for_function("() => document.getElementById('pbResult').textContent !== 'Bygger…'")
    page.wait_for_selector("#pbResult .review-table", timeout=3000)
    page.click("#pbResult details > summary")

    # Varje rubrik står rakt över sina värden. Textens egen kant mäts, inte
    # cellens: vänsterkanten i textkolumner och högerkanten i talkolumner.
    columns = page.eval_on_selector_all(
        "#pbResult .review-table",
        """tables => tables.flatMap(table => [...table.tHead.rows[0].cells].map((th, index) => {
          const edge = cell => { const range = document.createRange();
            range.selectNodeContents(cell); return range.getBoundingClientRect(); };
          const align = getComputedStyle(th).textAlign, head = edge(th);
          const offsets = [...table.tBodies[0].rows].map(row => {
            const cell = row.cells[index], text = edge(cell);
            return {same: getComputedStyle(cell).textAlign === align,
                    off: Math.abs(align === 'right' ? head.right - text.right
                                                    : head.left - text.left)};
          });
          return {label: th.textContent, align, same: offsets.every(o => o.same),
                  off: Math.max(...offsets.map(o => o.off))};
        }))""",
    )
    assert len(columns) == 24
    assert all(column["same"] for column in columns), columns
    assert [c for c in columns if c["off"] >= 1] == []
    assert {c["label"] for c in columns if c["align"] == "right"} == {
        "Proj. summa",
        "Uppm. summa",
        "Mätta don",
        "Avvikelse",
        "Proj.",
        "Uppm.",
        "Avvikelse (absolut)",
    }
    assert {c["align"] for c in columns} == {"left", "right"}
    assert errors == []
    page.close()


def _answer(status: int, body: str) -> Any:
    def fulfill(route: Any) -> None:
        route.fulfill(status=status, content_type="application/json", body=body)

    return fulfill


def test_protocol_draft_explains_what_is_wrong_in_swedish(
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_function("() => document.querySelectorAll('#pbInspection option').length > 1")
    page.click(".projectbar details > summary")

    def build() -> str:
        page.click("#pbBuild")
        page.wait_for_function(
            "() => document.getElementById('pbResult').textContent.startsWith('Utkastet')"
            " && !document.getElementById('pbBuild').disabled"
        )
        text: str = page.inner_text("#pbResult")
        return text.removeprefix("Utkastet kunde inte byggas: ")

    # Utan synkat fältunderlag.
    page.select_option("#pbInspection", "ovk-planerad")
    assert build() == "Besiktningen har inget synkat fältunderlag ännu."

    # Serverns besked om utkastet, i de former det kommer.
    answers: list[tuple[int, str, str]] = [
        (
            409,
            json.dumps({"detail": {"code": "OVK_INSPECTION_ISSUED"}}),
            "Intyg är redan utfärdat för besiktningen, så utkastet kan inte byggas om.",
        ),
        (
            422,
            json.dumps({"detail": "Planned workflow required"}),
            "Besiktningen är inte planerad i det här projektet. Ange besiktningsman och datum"
            " på besiktningen först.",
        ),
        (
            422,
            json.dumps({"detail": {"code": "INVALID_FIELD_DATA", "message": "<b>unit</b> x"}}),
            "Fältunderlaget är inte fullständigt. Serverns besked: <b>unit</b> x",
        ),
        (
            422,
            json.dumps({"detail": "Something new"}),
            "Servern avvisade begäran. Serverns besked: Something new",
        ),
        (500, "Internal Server Error", "Servern svarade med ett fel som inte gick att läsa."),
    ]
    page.select_option("#pbInspection", "ovk-pagaende")
    for status, body, expected in answers:
        page.unroute("**/protokoll-utkast")
        page.route("**/protokoll-utkast", _answer(status, body))
        assert build() == expected
    # Beskedet visas som text, aldrig som HTML.
    assert page.query_selector("#pbResult b") is None
    assert errors == []
    page.close()


def test_protocol_draft_list_handles_duplicates_and_empty_projects(
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_function("() => document.querySelectorAll('#pbInspection option').length > 1")

    def fill(items: str) -> list[list[str]]:
        result: list[list[str]] = page.evaluate(
            f"""() => {{ fillDraftInspections({items});
              const select = document.getElementById('pbInspection');
              return [[...select.options].map(o => o.textContent), [select.value],
                      [select, document.getElementById('pbBuild')].map(e => String(e.disabled))];
            }}"""
        )
        return result

    plan = "planning: {planned_date: '2027-01-15'}"
    # Samma namn och datum skiljs åt med id; senaste datum först; protokollklara utelämnas.
    assert fill(
        f"""[{{inspection_id: 'a', object_name: 'Hus A', {plan}}},
             {{inspection_id: 'b', object_name: 'Hus A', {plan}}},
             {{inspection_id: 'c', object_name: 'Hus B', planning: {{planned_date: '2027-03-01'}}}},
             {{inspection_id: 'd', object_name: 'Hus C', {plan}, protocol_ready: true}},
             {{inspection_id: 'e', object_name: 'Hus D'}}]"""
    ) == [
        [
            "Välj besiktning…",
            "Hus B · 2027-03-01",
            "Hus A · 2027-01-15 · a",
            "Hus A · 2027-01-15 · b",
        ],
        [""],
        ["false", "false"],
    ]
    # En enda besiktning är förvald.
    assert fill(f"[{{inspection_id: 'a', object_name: 'Hus A', {plan}}}]") == [
        ["Välj besiktning…", "Hus A · 2027-01-15"],
        ["a"],
        ["false", "false"],
    ]
    # Utan något att bygga är både listan och knappen avstängda.
    assert fill("[]") == [["Inga besiktningar väntar på utkast"], [""], ["true", "true"]]
    assert fill("null") == [["Laddar besiktningar…"], [""], ["true", "true"]]

    # Vid projektbyte laddas listan om och ett tidigare resultat tas bort.
    page.evaluate("() => { document.getElementById('pbResult').textContent = 'gammalt'; }")
    page.evaluate("() => loadProject()")
    page.wait_for_function("() => document.querySelectorAll('#pbInspection option').length === 4")
    assert page.inner_text("#pbResult") == ""
    assert errors == []
    page.close()


def test_changed_draft_is_saved_before_it_is_replaced_and_can_be_restored(
    data_root: Path,
    base_url: str,
    browser: Any,  # noqa: F811
) -> None:
    from dataclasses import replace

    from crow_ovk_workflow import ReviewStatus
    from crow_ovk_workflow.models import OvkReviewDecision

    workflows = OvkWorkflowRepository(data_root)
    record = workflows.load("p1", "ovk-planerad")
    assert record.planning is not None
    context = data_root / "projects" / "p1" / "ovk-field" / "ovk-planerad" / "context.json"
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text(
        json.dumps(
            {
                "inspection_id": "ovk-planerad",
                "project_id": "p1",
                "inspector_id": record.planning.inspector_id,
                "previous_inspection_id": record.planning.previous_inspection_id,
                "system_type": record.inspection.systems[0].system_type,
            }
        ),
        encoding="utf-8",
    )
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_function("() => document.querySelectorAll('#pbInspection option').length > 1")
    page.click(".projectbar details > summary")
    assert (
        page.evaluate(
            """() => fetch('/api/ovk/projects/p1/field/ovk-planerad/sync', {
              method: 'PUT', headers: {'content-type': 'application/json'},
              body: JSON.stringify({inspection_id: 'ovk-planerad',
                units: [{unit_id: 'u1', number: '1701', kind: 'apartment'}],
                rooms: [{room_id: 'r1', unit_id: 'u1', name: 'WC'}],
                measurements: [
                  {measurement_id: 'm1', unit_id: 'u1', room_id: 'r1',
                   point_type: 'franluftsdon', point_label: 'WC 1', designed_value: '20',
                   measured_value: '15', measurable: true, unit_of_measure: 'l/s'}]})
            }).then(r => r.status)"""
        )
        == 200
    )

    def build() -> None:
        page.click("#pbBuild")
        page.wait_for_function(
            "() => document.getElementById('pbResult').textContent !== 'Bygger…'"
            " && !document.getElementById('pbBuild').disabled"
        )

    # Första bygget och ett bygge på ett orört utkast frågar inte.
    page.select_option("#pbInspection", "ovk-planerad")
    build()
    page.wait_for_selector("#pbResult .review-table")
    build()
    page.wait_for_selector("#pbResult .review-table")
    assert page.query_selector("#pbConfirm") is None
    assert page.query_selector("#pbSaved") is None

    # Ett granskningsbeslut läggs på utkastet. Nu frågar verktyget först.
    built = workflows.load("p1", "ovk-planerad")
    decision = OvkReviewDecision(
        observation_id="o1",
        source_text="WC 1",
        evidence_ref="m1",
        reason="needs_review",
        status=ReviewStatus.ACCEPTED,
        reviewer="Stoffe",
        note="kontrollerad",
    )
    workflows.save(replace(built, review=(decision,)))
    build()
    page.wait_for_selector("#pbConfirm")
    assert page.inner_text("#pbConfirmTitle") == (
        "Besiktningen har redan ett utkast som har ändrats."
    )
    assert "1 granskningsbeslut" in page.inner_text("#pbConfirm")
    assert "sparas undan först och går att återställa" in page.inner_text("#pbConfirm")
    # Det ofarliga valet är förvalt, och Escape avbryter utan att något ändras.
    assert page.evaluate("() => document.activeElement.id") == "pbConfirmNo"
    page.keyboard.press("Escape")
    assert page.inner_text("#pbResult") == "Inget ändrades."
    assert workflows.load("p1", "ovk-planerad").review == (decision,)

    # Efter bekräftelse sparas utkastet undan och ett nytt byggs.
    build()
    page.click("#pbConfirmYes")
    page.wait_for_selector("#pbSaved [data-saved-draft]")
    assert page.inner_text("#pbSavedNote") == (
        "Det tidigare utkastet är sparat undan och går att återställa under Sparade utkast."
    )
    assert workflows.load("p1", "ovk-planerad").review == ()
    assert page.locator("#pbSaved .saved-draft").count() == 1
    assert "1 granskningsbeslut" in page.inner_text("#pbSaved .saved-draft")

    # Det sparade utkastet tas tillbaka, och det syns också när besiktningen väljs igen.
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#pbSaved [data-saved-draft]")
    page.wait_for_function(
        "() => document.getElementById('pbResult').textContent.includes('är återställt.')"
    )
    assert workflows.load("p1", "ovk-planerad").review == (decision,)
    page.select_option("#pbInspection", "ovk-granska")
    page.select_option("#pbInspection", "ovk-planerad")
    page.wait_for_selector("#pbSaved [data-saved-draft]")
    assert errors == []
    page.close()
