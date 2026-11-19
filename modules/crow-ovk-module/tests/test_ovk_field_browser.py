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


def _reload_after_save(page: Any) -> None:
    """Laddar om sidan först när utkastet är skrivet till IndexedDB.

    Knapptrycken sparar asynkront, så en omladdning direkt efter ett tryck kan
    annars hinna före skrivningen och läsa ett äldre utkast.
    """
    page.evaluate("() => persist()")
    page.reload()


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
    # System F har ingen tilluft via don: räknaren för tilluftsdon visas inte.
    assert flow.page.locator("[aria-label='Öka Tilluftsdon']").count() == 0
    flow.next("clean")
    flow.answer("Smutsiga", "transfer")
    # Saknad överluft i våtrum följs av frågan om friskluftsventil (system F).
    flow.answer("Nej", "fresh")
    flow.page.click("[aria-label='Öka Friskluftsventiler']")
    flow.page.wait_for_function("state.window_vents.length === 1")
    flow.next("remark")
    # Svaret Smutsiga gör Smutsigt don till förvald anmärkning.
    flow.answer("Ja, registrera anmärkning", "remarkText")
    assert flow.page.input_value("#ovkWzRemarkText") == "Smutsigt frånluftsdon"
    flow.next("remarkClass")
    flow.answer("1 · Bör åtgärdas", "remarkPhoto")
    flow.next("remark")
    flow.answer("Nej, inga fler", "done")

    # Sovrum utan don i system F: bara friskluftsventil efterfrågas.
    flow.answer("+ Nästa rum", "room")
    flow.room("Sovrum")
    flow.next("fresh")
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
    ) == ["yes/dirty/no/yes", "no///", "no///"]
    assert flow.state("state.measurements.map(m => m.point_label + ':' + m.point_type)") == [
        "Badrum 1:franluftsdon"
    ]
    assert flow.state("state.window_vents.map(v => v.present + ':' + v.note)") == [
        "true:Antal: 1",
        "false:",
    ]
    assert flow.state(
        "state.findings.map(f => [f.description, f.classification, f.defect_type].join('|'))"
    ) == ["Badrum: Smutsigt frånluftsdon|1|contaminated_extract_terminal"]

    # Det som registrerats ska godtas av serverns validering vid synk.
    data = _validated_payload(flow.state("payload()"))
    assert len(data.visual_checks) == 3
    assert len(data.measurements) == 1

    # Tillbaka går ett steg i taget och mätvarvet startar från sista rummet.
    flow.page.click("#footBack")
    flow.expect_step("remark")
    flow.next("done")
    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Varv 2')"
    )
    # Mätvarvet visar bara rum med don: Badrum, inte Sovrum eller Hall.
    assert flow.state("state.rooms.find(room => room.room_id === state.activeRoomId).name") == (
        "Badrum"
    )
    assert flow.page.text_content("#ovkStepCount") == "Rum 1 av 1"
    assert flow.page.text_content("#footDone") == "Till slutkontroll"
    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Slutkontroll')"
    )
    # Tillbaka från slutkontrollen går till det enda mätrummet.
    flow.page.click("#footBack")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Varv 2')"
    )
    assert flow.state("state.rooms.find(room => room.room_id === state.activeRoomId).name") == (
        "Badrum"
    )
    assert flow.errors == []
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
    # Rummet har bara tilluftsdon, så smutsigt tilluftsdon är förvalt.
    flow.answer("Ja, registrera anmärkning", "remarkText")
    assert flow.page.input_value("#ovkWzRemarkText") == "Smutsigt tilluftsdon"
    assert flow.page.locator("#ovkWizard button:text-is('Smutsigt frånluftsdon')").count() == 0
    flow.page.click("#footBack")
    flow.expect_step("remark")
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


def test_visual_round_resumes_on_the_open_question_after_reload(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    flow.start(field_url)
    flow.room("Badrum")
    flow.page.click("[aria-label='Öka Frånluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 1")
    flow.next("clean")
    flow.answer("Rena", "transfer")

    # Omladdning mitt i rummet: överluftsfrågan är obesvarad och ska visas igen,
    # inte rummets sammanfattning.
    _reload_after_save(flow.page)
    flow.page.wait_for_function("typeof state === 'object' && state.rooms.length === 1")
    flow.page.click("#continueUnit")
    flow.expect_step("transfer")
    flow.answer("Nej", "fresh")

    # Ett halvfärdigt anmärkningssteg återupptas på frågan om anmärkning.
    flow.next("remark")
    flow.answer("Ja, registrera anmärkning", "remarkText")
    _reload_after_save(flow.page)
    flow.page.wait_for_function("typeof state === 'object' && state.rooms.length === 1")
    flow.page.click("#continueUnit")
    flow.expect_step("remark")
    assert flow.errors == []
    context.close()


def test_measurement_round_is_skipped_when_no_room_has_terminals(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    flow.start(field_url)
    flow.room("Hall")
    flow.next("remark")
    flow.answer("Nej, inget att anmärka", "done")
    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Slutkontroll')"
    )
    flow.page.click("#footBack")
    flow.expect_step("done")
    assert flow.errors == []
    context.close()


def test_key_overview_registers_receipt_and_return_method(field_url: str, browser: Any) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.fill("#inspection", "nyckeltest")
    page.fill("#inspector", "Test Testsson")
    page.fill("#unitSeries", "1001-1003")
    page.click("#start")
    page.wait_for_function("state.units.length === 3")
    assert page.text_content("#ovkKeySummary") == "Inga nycklar mottagna"

    page.click("#ovkKeyToggle")
    rows = page.locator("#ovkKeyList .ovk-key-row")
    assert rows.count() == 4
    assert rows.nth(0).locator("strong").text_content() == "Huvudnyckel"

    # Ta emot huvudnyckeln och en lägenhetsnyckel var för sig.
    rows.nth(0).locator("button:text-is('Ta emot')").click()
    rows.nth(1).locator("button:text-is('Ta emot')").click()
    page.wait_for_function("state.master_key && state.master_key.received === true")
    assert page.text_content("#ovkKeySummary") == "2 nycklar ute"

    # Massmottagning kräver två tryck.
    page.click("#ovkKeyReceiveAll")
    assert (
        page.evaluate("() => state.units.filter(unit => unit.key && unit.key.received).length") == 1
    )
    assert page.text_content("#ovkKeyReceiveAll") == "Bekräfta: ta emot 2"
    assert page.evaluate("() => state.master_key.received_at") is not None
    page.click("#ovkKeyReceiveAll")
    page.wait_for_function("state.units.every(unit => unit.key && unit.key.received)")
    assert page.text_content("#ovkKeySummary") == "4 nycklar ute"

    # Återlämning med valt sätt, per nyckel.
    rows.nth(1).locator("button:text-is('Brevlåda')").click()
    rows.nth(2).locator("button:text-is('I handen')").click()
    page.wait_for_function("state.units[1].key.returned === true")
    assert page.evaluate("() => state.units.map(unit => unit.key.returned_method)") == [
        "mailbox",
        "hand",
        "",
    ]
    assert page.text_content("#ovkKeySummary") == "2 nycklar ute · 2 återlämnade"
    assert "i brevlådan" in (rows.nth(1).locator("span").text_content() or "")

    # Filtret visar bara nycklar som fortfarande är ute.
    page.check("#ovkKeyOnlyHeld")
    assert page.locator("#ovkKeyList .ovk-key-row").count() == 2

    data = _validated_payload(page.evaluate("() => payload()"))
    assert data.master_key is not None
    assert data.master_key.received is True
    assert data.master_key.returned is False
    assert [unit.key.returned_method for unit in data.units if unit.key is not None] == [
        "mailbox",
        "hand",
        "",
    ]

    # Omladdning: huvudnyckeln och återlämningssätten ligger kvar i utkastet.
    _reload_after_save(page)
    page.wait_for_function("typeof state === 'object' && state.units.length === 3")
    assert page.evaluate("() => payload().master_key.received") is True
    assert page.evaluate("() => state.units.map(unit => unit.key.returned_method)") == [
        "mailbox",
        "hand",
        "",
    ]
    assert page.text_content("#ovkKeySummary") == "2 nycklar ute · 2 återlämnade"

    # Lämna alla kräver två tryck och stämplar bara nycklar som är ute.
    page.click("#ovkKeyToggle")
    page.click("#ovkKeyReturnAllMailbox")
    assert page.evaluate("() => state.master_key.returned") is False
    page.click("#ovkKeyReturnAllMailbox")
    page.wait_for_function("state.master_key.returned === true")
    assert page.evaluate("() => state.units.map(unit => unit.key.returned_method)") == [
        "mailbox",
        "hand",
        "mailbox",
    ]
    assert page.text_content("#ovkKeySummary") == "Alla 4 nycklar återlämnade"

    # Ångra i två steg på huvudnyckeln: först återlämningen, sedan mottagandet.
    master = page.locator("#ovkKeyList .ovk-key-row").nth(0)
    master.locator("button:text-is('Ångra')").click()
    page.wait_for_function("state.master_key.returned === false")
    master.locator("button:text-is('Ångra')").click()
    page.wait_for_function("state.master_key === null")
    assert page.evaluate("() => 'master_key' in payload()") is False
    _validated_payload(page.evaluate("() => payload()"))
    assert errors == []
    context.close()


def test_unit_key_card_asks_how_the_key_is_returned(field_url: str, browser: Any) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    flow.start(field_url)
    # Tillbaka från första steget leder till enhetens nyckelkort.
    flow.page.click("#footBack")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('nycklar')"
    )
    flow.page.click("#keyIn")
    assert flow.page.is_hidden("#keyMethodRow")
    flow.page.click("#keyOut")
    assert flow.page.is_visible("#keyMethodRow")
    assert flow.state("state.units[0].key.returned") is False
    flow.page.click("#keyReturnMailbox")
    flow.page.wait_for_function("state.units[0].key.returned === true")
    assert flow.state("state.units[0].key.returned_method") == "mailbox"
    assert "i brevlådan" in (flow.page.text_content("#keyInfo") or "")
    assert flow.page.is_hidden("#keyMethodRow")
    # Ett nytt tryck ångrar återlämningen och nollställer sättet.
    flow.page.click("#keyOut")
    flow.page.wait_for_function("state.units[0].key.returned === false")
    assert flow.state("state.units[0].key.returned_method") == ""
    assert flow.errors == []
    _validated_payload(flow.state("payload()"))
    context.close()


def test_measurement_round_skips_room_without_terminals_between_two_others(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    flow.start(field_url)

    def finish_room(name: str, terminals: int) -> None:
        flow.room(name)
        for _ in range(terminals):
            flow.page.click("[aria-label='Öka Frånluftsdon']")
        flow.page.wait_for_function(
            "count => state.measurements.filter(point => point.room_id === state.activeRoomId)"
            ".length === count",
            arg=terminals,
        )
        for _ in range(6):
            if flow.state("document.getElementById('ovkWizard').dataset.step") == "remark":
                break
            flow.page.click("#footDone")
            flow.page.wait_for_timeout(150)
        flow.answer("Nej, inget att anmärka", "done")

    finish_room("Badrum", 1)
    flow.answer("+ Nästa rum", "room")
    finish_room("Hall", 0)
    flow.answer("+ Nästa rum", "room")
    finish_room("Kök", 1)

    def active_room() -> Any:
        return flow.state("activeRoom().name")

    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Varv 2')"
    )
    assert active_room() == "Badrum"
    assert flow.page.text_content("#ovkStepCount") == "Rum 1 av 2"
    assert flow.page.text_content("#footDone") == "Nästa rum"
    flow.page.click("#footDone")
    flow.page.wait_for_function("activeRoom().name === 'Kök'")
    assert flow.page.text_content("#ovkStepCount") == "Rum 2 av 2"
    assert flow.page.text_content("#footDone") == "Till slutkontroll"
    flow.page.click("#footBack")
    flow.page.wait_for_function("activeRoom().name === 'Badrum'")

    # Omladdning mitt i mätvarvet återupptar på samma mätrum.
    _reload_after_save(flow.page)
    flow.page.wait_for_function("typeof state === 'object' && state.rooms.length === 3")
    flow.page.click("#continueUnit")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Varv 2')"
    )
    assert active_room() == "Badrum"
    assert flow.errors == []
    context.close()
