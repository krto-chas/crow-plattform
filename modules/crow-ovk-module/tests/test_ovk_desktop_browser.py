"""Körda webbläsartester för skrivbordsarbetsplatsens översikt.

Sidan ritas helt av skript, så textjämförelser av filerna visar inte om
arbetskön faktiskt kommer upp. De här testerna kör sidan mot en riktig server
med sparade uppdrag.

Testerna hoppas över om Playwright eller en Chrome-installation saknas.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
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
    # Protokollklart men inte klarmarkerat i fält: ska till granskning med upplysning.
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
        "att_granska": "2",
        "leveransklar": "1",
        "pagaende": "1",
        "planerad": "1",
        "utfardad": "1",
    }
    # Det som kräver handling står först.
    assert _statuses(page) == [
        "att_granska",
        "att_granska",
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
    assert row.locator("a.button").inner_text() == "Granska"
    assert errors == []
    page.close()


def test_queue_card_and_search_filter_the_list(base_url: str, browser: Any) -> None:  # noqa: F811
    page, errors, _ = _open(browser, base_url + "/ovk", _DESKTOP)
    page.wait_for_selector("#overviewItems tr")

    page.click("#queue button[data-status=att_granska]")
    assert _statuses(page) == ["att_granska", "att_granska"]
    assert page.input_value("#overviewFilter") == "att_granska"
    assert page.get_attribute("#queue button[data-status=att_granska]", "aria-pressed") == "true"
    assert page.inner_text("#overviewStatus") == "Visar 2 av 6 uppdrag."

    page.click("#queue button[data-status=att_granska]")
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
    assert _statuses(page) == ["att_granska", "att_granska", "leveransklar"]
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
    assert "besiktningsposten går inte att läsa" in warning
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
