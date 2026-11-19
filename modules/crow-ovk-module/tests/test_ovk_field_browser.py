"""Körda webbläsartester för fältappen i mobil-vy.

Fältappens JavaScript testas i övrigt genom textjämförelser. De här testerna
kör appen i en riktig webbläsare och kontrollerar det som bara syns då: att
varv 1 går att genomföra en fråga i taget utan att någon vy scrollar, och att
det som registreras godtas av serverns validering.

Testerna hoppas över om Playwright eller en Chrome-installation saknas.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from pytest import MonkeyPatch
from test_ovk_workflow import _write_entitlements

from crow_ovk_module.ovk_field_surface import _validated_payload
from crow_workbench.shell import create_app

playwright_api = pytest.importorskip("playwright.sync_api")

# Liten iPhone (SE) och en vanlig iPhone: stegvyn ska rymmas på båda.
_VIEWPORTS = [(375, 667), (390, 844)]

_MEASURE_VIEW = """() => {
  const card = document.querySelector('#viewUnit>.card.ovk-step-active');
  const wizard = document.getElementById('ovkWizard');
  const box = card.getBoundingClientRect();
  const controls = [...card.querySelectorAll('button,input,textarea,select')]
    .filter(node => node.offsetParent !== null && node.getBoundingClientRect().width > 0);
  return {
    step: wizard.dataset.step,
    controls: controls.length,
    outside: controls.filter(node => {
      const rect = node.getBoundingClientRect();
      return rect.bottom > box.bottom + 1 || rect.top < box.top - 1;
    }).length,
    cardOverflow: card.scrollHeight - card.clientHeight,
    wizardOverflow: wizard.scrollHeight - wizard.clientHeight,
    pageOverflow: document.documentElement.scrollHeight - window.innerHeight,
  };
}"""


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


@pytest.fixture
def field_url(tmp_path: Path, monkeypatch: MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
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
            pytest.fail("fältappens testserver startade inte")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}/ovk/falt"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture
def browser() -> Iterator[Any]:
    with playwright_api.sync_playwright() as playwright:
        launched = None
        for options in ({"channel": "chrome"}, {}):
            try:
                launched = playwright.chromium.launch(args=["--no-sandbox"], **options)
                break
            except playwright_api.Error:
                continue
        if launched is None:
            pytest.skip("ingen Chrome- eller Chromium-installation för Playwright")
        try:
            yield launched
        finally:
            launched.close()


class _Flow:
    """Går igenom varv 1 och kontrollerar varje vy som visas."""

    def __init__(self, page: Any) -> None:
        self.page = page
        self.errors: list[str] = []
        self.steps: list[str] = []
        page.on("pageerror", lambda error: self.errors.append(str(error)))

    def start(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
        self.page.fill("#inspection", "webblasartest")
        self.page.fill("#inspector", "Test Testsson")
        self.page.fill("#unitSeries", "1001-1002")
        self.page.click("#start")
        self.page.click("#continueUnit")
        self.expect_step("room")

    def expect_step(self, step: str) -> None:
        self.page.wait_for_function(
            "step => document.getElementById('ovkWizard').dataset.step === step", arg=step
        )
        view = self.page.evaluate(_MEASURE_VIEW)
        self.steps.append(step)
        assert view["outside"] == 0, f"{step}: {view['outside']} kontroller utanför kortet"
        assert view["cardOverflow"] <= 0, f"{step}: kortet scrollar {view['cardOverflow']} px"
        assert view["wizardOverflow"] <= 0, f"{step}: vyn scrollar {view['wizardOverflow']} px"
        assert view["pageOverflow"] <= 0, f"{step}: sidan scrollar {view['pageOverflow']} px"
        assert view["controls"] >= 1

    def answer(self, label: str, then: str) -> None:
        self.page.click(f"#ovkWizard button:text-is('{label}')")
        self.expect_step(then)

    def next(self, then: str) -> None:
        self.page.click("#footDone")
        self.expect_step(then)

    def room(self, name: str) -> None:
        self.page.click(f"#ovkWizard [data-room='{name}']")
        self.expect_step("don")

    def state(self, expression: str) -> Any:
        return self.page.evaluate(f"() => ({expression})")


@pytest.mark.parametrize(("width", "height"), _VIEWPORTS)
def test_visual_round_runs_one_question_at_a_time_without_scrolling(
    field_url: str, browser: Any, width: int, height: int
) -> None:
    context = browser.new_context(
        viewport={"width": width, "height": height}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    flow.start(field_url)

    # Badrum: rummet skapas utan don, och ett tryck ger exakt ett don.
    flow.room("Badrum")
    assert flow.state("state.measurements.length") == 0
    flow.page.click("[aria-label='Öka Frånluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 1")
    flow.page.click("[aria-label='Öka Frånluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 2")
    flow.page.click("[aria-label='Minska Frånluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 1")
    flow.next("clean")
    flow.answer("Rena", "transfer")
    # Saknad överluft i våtrum följs av frågan om friskluftsventil (system F).
    flow.answer("Nej", "fresh")
    flow.page.click("[aria-label='Öka Friskluftsventiler']")
    flow.page.wait_for_function("state.window_vents.length === 1")
    flow.next("remark")
    flow.answer("Ja, registrera anmärkning", "remarkText")
    flow.page.fill("#ovkWzRemarkText", "Sprucket don")
    flow.next("remarkClass")
    flow.answer("1 · Bör åtgärdas", "remarkPhoto")
    flow.next("remark")
    flow.answer("Nej, inga fler", "done")

    # Sovrum med enbart tilluft: frågan om överluft ställs utan att vara våtrum.
    flow.answer("+ Nästa rum", "room")
    flow.room("Sovrum")
    flow.page.click("[aria-label='Öka Tilluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 2")
    flow.next("clean")
    flow.answer("Rena", "transfer")
    flow.answer("Ja", "fresh")
    flow.next("remark")
    flow.answer("Nej, inget att anmärka", "done")

    # Hall utan don: varken renhet, överluft eller friskluftsventil efterfrågas.
    flow.answer("+ Nästa rum", "room")
    flow.room("Hall")
    flow.next("remark")
    flow.answer("Nej, inget att anmärka", "done")

    assert flow.errors == []
    assert flow.state("state.rooms.map(room => room.name)") == ["Badrum", "Sovrum", "Hall"]
    assert flow.state(
        "state.visual_checks.map(c => [c.don, c.clean, c.transfer, c.fresh].join('/'))"
    ) == ["yes/clean/no/yes", "yes/clean/yes/", "no///"]
    assert flow.state("state.measurements.map(m => m.point_label + ':' + m.point_type)") == [
        "Badrum 1:franluftsdon",
        "Sovrum 1:tilluftsdon",
    ]
    assert flow.state("state.window_vents.map(v => v.present + ':' + v.note)") == [
        "true:Antal: 1",
        "false:",
    ]
    assert flow.state("state.findings.map(f => f.description + '|' + f.classification)") == [
        "Badrum: Sprucket don|1"
    ]

    # Det som registrerats ska godtas av serverns validering vid synk.
    data = _validated_payload(flow.state("payload()"))
    assert len(data.visual_checks) == 3
    assert len(data.measurements) == 2

    # Tillbaka går ett steg i taget och mätvarvet startar från sista rummet.
    flow.page.click("#footBack")
    flow.expect_step("remark")
    flow.next("done")
    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Varv 2')"
    )
    context.close()


def test_visual_round_resumes_room_and_skips_vent_question_for_ftx(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    flow.start(field_url)
    flow.state("state.system_type = 'FTX'")

    flow.room("Sovrum")
    flow.page.click("[aria-label='Öka Tilluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 1")
    flow.next("clean")
    flow.answer("Smutsiga", "transfer")
    # FTX: ingen fråga om friskluftsventil.
    flow.answer("Ej kontrollerat", "remark")
    flow.answer("Nej, inget att anmärka", "done")

    # Ändra svar: ta bort donet, då registreras att don saknas och renheten nollställs.
    flow.answer("Ändra svar", "don")
    flow.page.click("[aria-label='Minska Tilluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 0")
    flow.next("remark")
    assert flow.state("state.visual_checks.map(c => [c.don, c.clean].join('/'))") == ["no/"]
    assert flow.errors == []
    _validated_payload(flow.state("payload()"))
    context.close()
