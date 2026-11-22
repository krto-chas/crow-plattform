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
        self.page.click("#ovkStartMore > summary")
        self.page.fill("#inspection", "webblasartest")
        self.page.fill("#inspector", "Test Testsson")
        self.page.select_option("#systemType", "F")
        self.page.fill("#unitSeries", "1001-1002")
        self.page.click("#footDone")
        self.page.click("#footDone")
        self.expect_step("room")

    def expect_step(self, step: str, controls: int = 1) -> None:
        self.page.wait_for_function(
            "step => document.getElementById('ovkWizard').dataset.step === step", arg=step
        )
        view = self.page.evaluate(_MEASURE_VIEW)
        self.steps.append(step)
        assert view["outside"] == 0, f"{step}: {view['outside']} kontroller utanför kortet"
        assert view["cardOverflow"] <= 0, f"{step}: kortet scrollar {view['cardOverflow']} px"
        assert view["wizardOverflow"] <= 0, f"{step}: vyn scrollar {view['wizardOverflow']} px"
        assert view["pageOverflow"] <= 0, f"{step}: sidan scrollar {view['pageOverflow']} px"
        assert view["controls"] >= controls

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
    flow.expect_step("point")
    assert flow.page.text_content("#ovkStepCount") == "0 av 1 don klara"
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
    flow.page.click("#footDone")
    flow.expect_step("transfer")
    flow.answer("Nej", "fresh")

    # Ett halvfärdigt anmärkningssteg återupptas på frågan om anmärkning.
    flow.next("remark")
    flow.answer("Ja, registrera anmärkning", "remarkText")
    _reload_after_save(flow.page)
    flow.page.wait_for_function("typeof state === 'object' && state.rooms.length === 1")
    flow.page.click("#footDone")
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
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "nyckeltest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1001-1003")
    page.click("#footDone")
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
    flow.expect_step("point")
    assert flow.page.text_content("#ovkStepCount") == "0 av 2 don klara"
    assert flow.page.text_content("#footDone") == "Nästa don"
    flow.page.click("#footDone")
    flow.page.wait_for_function("activeRoom().name === 'Kök'")
    assert flow.page.text_content("#footDone") == "Till slutkontroll"
    flow.page.click("#footBack")
    flow.page.wait_for_function("activeRoom().name === 'Badrum'")

    # Omladdning mitt i mätvarvet återupptar på samma mätrum.
    _reload_after_save(flow.page)
    flow.page.wait_for_function("typeof state === 'object' && state.rooms.length === 3")
    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Varv 2')"
    )
    assert active_room() == "Badrum"
    assert flow.errors == []
    context.close()


def test_measurement_round_takes_one_terminal_at_a_time(field_url: str, browser: Any) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    flow.start(field_url)

    def visual_room(name: str, terminals: int) -> None:
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

    visual_room("Badrum", 2)
    flow.answer("+ Nästa rum", "room")
    visual_room("Kök", 1)
    flow.page.click("#footDone")
    flow.expect_step("point")

    def heading() -> str:
        return (
            (flow.page.text_content("#ovkWizard .ovk-wz-room") or "")
            + " | "
            + (flow.page.text_content("#ovkWizard .ovk-wz-title") or "")
        )

    def hint() -> str:
        return flow.page.text_content("#ovkWzDeviation") or ""

    # Utan tidigare besiktning visas ingen historik.
    assert flow.page.locator("#ovkWzHistory").count() == 0

    # Med tidigare mätvärden visas förra värdet för samma don och rummets historik.
    flow.page.evaluate(
        """() => {
          const [first, second] = state.measurements;
          state.previous_inspection_id = 'ovk-2023';
          state.historical_measurements = [
            {...first, measured_value: '14', measurable: true},
            {...second, measurement_id: 'okand-punkt', measured_value: '9', measurable: true},
          ];
        }"""
    )
    # Ett steg bort och tillbaka ritar om mätvyn med historiken.
    flow.answer("+ Don i rummet", "addPoint")
    flow.page.click("#footBack")
    flow.expect_step("point")
    assert "Förra besiktningen: " in (flow.page.text_content("#ovkWizard") or "")
    assert "14" in (flow.page.text_content("#ovkWizard") or "")
    # Historikvyn är ren läsning: den har inga egna kontroller utöver sidfoten.
    assert (flow.page.text_content("#ovkWzHistory") or "").endswith("Tidigare mätvärden (2)")
    flow.page.click("#ovkWzHistory")
    flow.expect_step("history", controls=0)
    history = flow.page.text_content("#ovkWizard") or ""
    assert "ovk-2023" in history
    assert history.count("ingen säker donmatchning") == 1
    flow.next("point")

    # Don 1: mätvärde med decimalkomma och projekterat värde ger avvikelse.
    assert heading() == "Badrum · Don 1 av 3 | Frånluft · Badrum 1"
    assert flow.page.get_attribute("#ovkWzFlow", "inputmode") == "decimal"
    flow.page.fill("#ovkWzFlow", "12,5")
    flow.page.fill("#ovkWzDesigned", "15")
    assert hint() == "Avvikelse mot projekterat: -2,5 l/s (-17 %)"

    # Ogiltigt värde stoppar Nästa tills det rättats.
    flow.page.fill("#ovkWzFlow", "tolv")
    flow.page.click("#footDone")
    flow.expect_step("point")
    assert "inte ett giltigt flöde" in (flow.page.text_content("#ovkWizard") or "")
    assert heading().startswith("Badrum · Don 1 av 3")
    flow.page.fill("#ovkWzFlow", "12,5")
    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.querySelector('#ovkWizard .ovk-wz-room').textContent.includes('Don 2 av 3')"
    )
    flow.expect_step("point")
    assert flow.page.text_content("#ovkStepCount") == "1 av 3 don klara"

    # Don 2: summering per rum visas när rummet har flera don av samma typ.
    flow.page.fill("#ovkWzFlow", "10")
    assert hint() == "Rummet hittills: frånluft 22,5 l/s på 2 av 2 don"

    # Ej mätbar kräver orsak och sparas som anmärkning på donet.
    flow.answer("Ej mätbar", "reason")
    flow.next("reason")
    assert "Ange en orsak" in (flow.page.text_content("#ovkWizard") or "")
    flow.answer("Ej åtkomligt", "reason")
    flow.next("remarkPhoto")
    flow.next("point")
    assert "Ej mätbar: Ej åtkomligt" in (flow.page.text_content("#ovkWizard") or "")
    assert flow.state(
        "state.measurements.map(m => [m.measurable, m.measured_value, m.designed_value].join('/'))"
    ) == ["true/12.5/15", "false//", "true//"]
    assert flow.page.text_content("#ovkStepCount") == "2 av 3 don klara"

    # Don 3 ligger i nästa rum; ett extra don läggs till och mäts direkt.
    flow.page.click("#footDone")
    flow.page.wait_for_function("activeRoom().name === 'Kök'")
    flow.expect_step("point")
    assert heading() == "Kök · Don 3 av 3 | Frånluft · Kök 1"
    flow.page.fill("#ovkWzFlow", "20")
    flow.answer("+ Don i rummet", "addPoint")
    # System F: tilluftsdon erbjuds inte.
    assert flow.page.locator("#ovkWizard button:text-is('Tilluftsdon')").count() == 0
    flow.answer("Överluftsdon", "point")
    assert heading().startswith("Kök · Don 4 av 4 | Överluft")
    flow.page.fill("#ovkWzFlow", "8")

    # Anmärkning från mätvyn bär donets namn och avvikande flöde som snabbval.
    flow.answer("Anmärkning", "remarkText")
    flow.answer("Avvikande luftflöde", "remarkText")
    flow.next("remarkClass")
    flow.answer("1 · Bör åtgärdas", "remarkPhoto")
    flow.next("point")
    findings = flow.state("state.findings.map(f => f.defect_type + '|' + f.description)")
    assert findings[0] == "terminal_not_measurable|Badrum: Badrum 2 ej mätbart – Ej åtkomligt"
    assert findings[1].startswith("incorrect_airflow|Kök: ")
    assert findings[1].endswith(" – Avvikande luftflöde")

    data = _validated_payload(flow.state("payload()"))
    assert [str(item.measured_value) for item in data.measurements] == [
        "12.5",
        "None",
        "20",
        "8",
    ]
    assert str(data.measurements[0].designed_value) == "15"
    assert data.measurements[1].measurable is False

    # Omladdning återupptar på samma don, och Tillbaka går ett don i taget.
    _reload_after_save(flow.page)
    flow.page.wait_for_function("typeof state === 'object' && state.rooms.length === 2")
    flow.page.click("#footDone")
    flow.expect_step("point")
    assert heading().startswith("Kök · Don 4 av 4")
    assert flow.page.input_value("#ovkWzFlow") == "8"
    flow.page.click("#footBack")
    flow.page.wait_for_function(
        "document.querySelector('#ovkWizard .ovk-wz-room').textContent.includes('Don 3 av 4')"
    )
    flow.page.click("#footBack")
    flow.page.wait_for_function("activeRoom().name === 'Badrum'")
    flow.expect_step("point")
    assert heading().startswith("Badrum · Don 2 av 4")
    # Ångra ej mätbar gör donet mätbart igen.
    flow.answer("Ångra – donet går att mäta", "point")
    assert flow.state("state.measurements[1].measurable") is True
    # Anmärkningen som skapades för det ej mätbara donet följer med bort.
    assert flow.state("state.measurements[1].finding_id") is None
    assert flow.state("state.findings.map(f => f.defect_type)") == ["incorrect_airflow"]
    _validated_payload(flow.state("payload()"))

    # Framåt från sista donet leder till slutkontrollen, och Tillbaka därifrån till sista donet.
    for _ in range(2):
        flow.page.click("#footDone")
        flow.page.wait_for_timeout(200)
    assert flow.page.text_content("#footDone") == "Till slutkontroll"
    flow.page.click("#footDone")
    flow.page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Slutkontroll')"
    )
    flow.page.click("#footBack")
    flow.expect_step("point")
    assert heading().startswith("Kök · Don 4 av 4")
    assert flow.errors == []
    context.close()


def _record_dialogs(page: Any, dialogs: list[str]) -> None:
    """Samla och avfärda webbläsardialoger så att testet kan kräva att inga visas."""

    def on_dialog(dialog: Any) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", on_dialog)


def test_equipment_checkpoints_are_answered_with_buttons(field_url: str, browser: Any) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "aggregattest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1001")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 1")
    # Benämning och placering anges i appens inmatningsblad, inte i en dialogruta.
    page.click("#addFlaktrum")
    page.click("#ovkSheet [data-sheet-submit]")
    assert "Benämning måste fyllas i." in (page.text_content("#ovkSheet") or "")
    page.click("#ovkSheet [data-sheet-cancel]")
    assert page.locator("#ovkSheet").count() == 0
    assert page.evaluate("() => state.technical_spaces.length") == 0
    page.click("#addFlaktrum")
    page.fill("#ovkSheet_label", "Fläktrum plan 10, LB01")
    page.fill("#ovkSheet_location", "Vind")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.checkpoints.length > 2")
    assert page.evaluate(
        "() => [state.technical_spaces[0].label, state.technical_spaces[0].location]"
    ) == [
        "Fläktrum plan 10, LB01",
        "Vind",
    ]
    items = page.locator("#cplist .cp-item")
    assert items.count() == page.evaluate("() => state.checkpoints.length")

    def status(index: int) -> Any:
        return page.evaluate(
            "index => [state.checkpoints[index].status, state.checkpoints[index].note]", index
        )

    # UA sätts med ett tryck, utan dialog.
    items.nth(0).locator("button:text-is('UA')").click()
    page.wait_for_function("state.checkpoints[0].status === 'pass'")
    assert items.nth(0).locator("button:text-is('UA')").get_attribute("aria-pressed") == "true"

    # Anmärkning kräver motivering i fältet under knapparna.
    items.nth(1).locator("button:text-is('Anmärkning')").click()
    assert status(1) == ["not_checked", ""]
    items.nth(1).locator("button:text-is('Spara')").click()
    assert "Skriv en motivering" in (items.nth(1).text_content() or "")
    assert status(1) == ["not_checked", ""]
    items.nth(1).locator("textarea").fill("Filter igensatt")
    items.nth(1).locator("button:text-is('Spara')").click()
    page.wait_for_function("state.checkpoints[1].status === 'fail'")
    assert status(1) == ["fail", "Filter igensatt"]
    assert "Filter igensatt" in (items.nth(1).text_content() or "")

    # Ej tillämplig kräver också motivering, och Avbryt ändrar ingenting.
    items.nth(2).locator("button:text-is('Ej tillämplig')").click()
    items.nth(2).locator("button:text-is('Avbryt')").click()
    assert status(2) == ["not_checked", ""]
    items.nth(2).locator("button:text-is('Ej tillämplig')").click()
    items.nth(2).locator("textarea").fill("Aggregatet saknar värmeåtervinning")
    items.nth(2).locator("button:text-is('Spara')").click()
    page.wait_for_function("state.checkpoints[2].status === 'not_applicable'")

    # Ett nytt tryck på valt resultat nollställer punkten till ej kontrollerad.
    items.nth(0).locator("button:text-is('UA')").click()
    page.wait_for_function("state.checkpoints[0].status === 'not_checked'")
    # Från anmärkning till UA rensas motiveringen.
    items.nth(1).locator("button:text-is('UA')").click()
    page.wait_for_function("state.checkpoints[1].status === 'pass'")
    assert status(1) == ["pass", ""]

    assert dialogs == []
    assert errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_text_is_entered_in_app_sheets_instead_of_browser_dialogs(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "bladtest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1001")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 1")

    def sheet_fits() -> None:
        box = page.evaluate(
            """() => {
              const node = document.querySelector('#ovkSheet .ovk-sheet-panel');
              const panel = node.getBoundingClientRect();
              return [panel.top >= 0, panel.bottom <= window.innerHeight + 1];
            }"""
        )
        assert box == [True, True]

    # Lägenheter läggs till som nummerserie.
    page.click("#addUnit")
    sheet_fits()
    page.fill("#ovkSheet_numbers", "1101-1102")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.units.length === 3")

    # Avbryt och Escape ändrar ingenting.
    page.click("#addPremises")
    page.keyboard.press("Escape")
    assert page.locator("#ovkSheet").count() == 0
    assert page.evaluate("() => state.units.length") == 3

    # Lokal läggs till med namn och öppnas direkt; Enter sparar.
    page.click("#addPremises")
    page.fill("#ovkSheet_name", "Frisör Anna")
    page.keyboard.press("Enter")
    page.wait_for_function("state.units.length === 4 && state.activeUnitId")
    assert page.evaluate("() => activeUnit().label") == "Frisör Anna"

    # Lokalrum frågar efter rumsnummer i bladet.
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'room'")
    page.locator("#ovkWizard .ovk-wz-grid button").first.click()
    sheet_fits()
    page.fill("#ovkSheet_nr", "101")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.rooms.length === 1")
    assert page.evaluate("() => state.rooms[0].name").endswith(" 101")
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'don'")

    # Systemtyp per enhet väljs med knappar.
    page.click("#footBack")
    page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('nycklar')"
    )
    page.click("#unitSystemBtn")
    sheet_fits()
    assert page.locator("#ovkSheet [data-sheet-choice]").count() == 6
    page.click("#ovkSheet [data-sheet-choice='FTX']")
    page.wait_for_function("activeUnit().system_type === 'FTX'")
    page.click("#unitSystemBtn")
    page.click("#ovkSheet [data-sheet-choice='']")
    page.wait_for_function("activeUnit().system_type === null")

    # Huvudnyckel kräver kommentar.
    page.click("#keyMaster")
    page.click("#ovkSheet [data-sheet-submit]")
    assert "Kommentar måste fyllas i." in (page.text_content("#ovkSheet") or "")
    assert page.evaluate("() => Boolean(activeUnit().key && activeUnit().key.master_key_used)") is (
        False
    )
    page.fill("#ovkSheet_note", "Lånad av fastighetsskötaren")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("activeUnit().key && activeUnit().key.master_key_used === true")
    assert page.evaluate("() => activeUnit().key.master_key_note") == "Lånad av fastighetsskötaren"

    assert dialogs == []
    assert errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_remarks_can_be_listed_and_removed_in_both_rounds(field_url: str, browser: Any) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    dialogs: list[str] = []
    _record_dialogs(flow.page, dialogs)
    flow.start(field_url)
    flow.room("Badrum")
    flow.page.click("[aria-label='Öka Frånluftsdon']")
    flow.page.wait_for_function("state.measurements.length === 1")
    for _ in range(6):
        if flow.state("document.getElementById('ovkWizard').dataset.step") == "remark":
            break
        flow.page.click("#footDone")
        flow.page.wait_for_timeout(150)
    assert flow.page.locator("#ovkWzRemarkList").count() == 0

    # Varv 1: registrera en anmärkning av misstag och ta bort den igen.
    flow.answer("Ja, registrera anmärkning", "remarkText")
    flow.page.fill("#ovkWzRemarkText", "Spricka i taket")
    flow.next("remarkClass")
    flow.answer("2 · Väsentlig brist", "remarkPhoto")
    flow.next("remark")
    assert (flow.page.text_content("#ovkWzRemarkList") or "").startswith("1 anmärkning registrerad")
    flow.page.click("#ovkWzRemarkList")
    flow.expect_step("remarkList")
    remove = flow.page.locator("#ovkWizard [data-remove]")
    assert remove.count() == 1
    # En återkontroll från förra besiktningen pekar på anmärkningen.
    flow.page.evaluate(
        """() => { state.finding_followups.push({
          source_inspection_id: 'tidigare', source_finding_id: 'gammal',
          unit_id: state.findings[0].unit_id, status: 'remaining', note: 'Kvarstår',
          current_finding_id: state.findings[0].finding_id, photo_ids: [] }); }"""
    )
    remove.first.click()
    # Första trycket ber om bekräftelse och tar inte bort något.
    assert flow.page.locator("#ovkWizard [data-remove]").first.text_content() == "Bekräfta"
    assert flow.state("state.findings.length") == 1
    flow.page.locator("#ovkWizard [data-remove]").first.click()
    flow.page.wait_for_function("state.findings.length === 0")
    flow.expect_step("remark")
    assert flow.state("state.finding_followups[0].current_finding_id") is None
    assert flow.state("state.finding_followups[0].status") == "not_checked"
    flow.state("(state.finding_followups.length = 0, 0)")
    assert flow.page.locator("#ovkWzRemarkList").count() == 0
    flow.answer("Nej, inget att anmärka", "done")

    # Varv 2: ej mätbar skapar en anmärkning; tas den bort blir donet mätbart igen.
    flow.page.click("#footDone")
    flow.expect_step("point")
    flow.answer("Ej mätbar", "reason")
    flow.answer("Ej åtkomligt", "reason")
    flow.next("remarkPhoto")
    flow.next("point")
    assert flow.state("state.measurements[0].measurable") is False
    flow.answer("Ångra – donet går att mäta", "point")
    assert flow.state("state.findings.length") == 0
    flow.answer("Ej mätbar", "reason")
    flow.answer("Ej åtkomligt", "reason")
    flow.next("remarkPhoto")
    flow.next("point")
    assert flow.state("state.findings.length") == 1
    flow.page.click("#ovkWzRemarkList")
    flow.expect_step("remarkList")
    flow.page.locator("#ovkWizard [data-remove]").first.click()
    flow.page.locator("#ovkWizard [data-remove]").first.click()
    flow.page.wait_for_function("state.findings.length === 0")
    flow.expect_step("point")
    assert flow.state("state.measurements[0].measurable") is not False
    assert flow.state("state.measurements[0].finding_id || null") is None
    _validated_payload(flow.page.evaluate("() => payload()"))
    assert dialogs == []
    assert flow.errors == []
    context.close()


def test_unit_list_shows_progress_filters_and_guards_finished_units(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "listtest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1101-1103, 1201")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 4")

    def tags() -> dict[str, str]:
        result: dict[str, str] = page.evaluate(
            """() => Object.fromEntries([...document.querySelectorAll('#unitList .unitrow')]
              .map(row => [row.querySelector('.nr').textContent,
                           row.querySelector('.tag').textContent]))"""
        )
        return result

    def to_list() -> None:
        page.evaluate("() => { renderRond(); view('viewRond'); }")

    assert set(tags().values()) == {"Ej påbörjad"}

    # Fri ordning: sista lägenheten öppnas först och besiktigas på riktigt en bit.
    page.click("#unitList [data-unit] >> text=1201")
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'room'")
    page.click("#ovkWizard [data-room='Badrum']")
    page.click("[aria-label='Öka Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 1")
    to_list()
    assert tags()["1201"] == "Pågående"

    # Framdriften följer genomförda moment.
    page.evaluate(
        """() => {
          const unit = state.units.find(item => item.number === '1201');
          state.field_progress[unit.unit_id] = {phase: 'measure', room_id: state.rooms[0].room_id};
          renderRond();
        }"""
    )
    assert tags()["1201"] == "Okulär kontroll klar"
    page.evaluate(
        """() => {
          const first = state.measurements[0];
          state.measurements.push({...first, measurement_id: 'm-extra', point_id: 'p-extra',
            point_label: 'F2', measured_value: '12'});
          renderRond();
        }"""
    )
    assert tags()["1201"] == "Mätning återstår"
    page.evaluate("() => { state.measurements[0].measured_value = '10'; renderRond(); }")
    assert tags()["1201"] == "Slutkontroll återstår"
    page.evaluate(
        """() => {
          const unit = state.units.find(item => item.number === '1201');
          unit.status = 'ua'; unit.checked_at = new Date().toISOString();
          const bom = state.units.find(item => item.number === '1102');
          bom.status = 'bom'; bom.bom_at = new Date().toISOString();
          renderRond();
        }"""
    )
    assert tags() == {
        "1101": "Ej påbörjad",
        "1102": "Ej tillgänglig · BOM",
        "1103": "Ej påbörjad",
        "1201": "Klar · UA",
    }

    # Filter på status och våning.
    def shown(status: str = "all", floor: str = "") -> list[str]:
        page.select_option("#unitFilter", status)
        page.select_option("#unitFloor", floor)
        return sorted(tags())

    assert page.is_visible("#unitFloor")
    assert shown("not_started") == ["1101", "1103"]
    assert shown("pending") == ["1101", "1103"]
    assert shown("checked") == ["1201"]
    assert shown("bom") == ["1102"]
    assert shown("ongoing") == []
    assert shown("all", "11") == ["1101", "1102", "1103"]
    assert shown("all", "12") == ["1201"]
    assert shown() == ["1101", "1102", "1103", "1201"]

    # Ett valt plan får inte ligga kvar dolt när bara ett plan återstår.
    page.select_option("#unitFloor", "11")
    page.evaluate(
        """() => { const hidden = state.units.find(item => item.number === '1201');
          hidden.number = 'A1'; renderRond(); }"""
    )
    assert not page.is_visible("#unitFloor")
    assert sorted(tags()) == ["1101", "1102", "1103", "A1"]
    page.evaluate(
        """() => { state.units.find(item => item.number === 'A1').number = '1201';
          renderRond(); }"""
    )

    # En färdig lägenhet öppnas aldrig direkt.
    def open_finished() -> None:
        page.click("#unitList [data-progress='done']")
        page.wait_for_selector("#ovkSheet")

    open_finished()
    assert "Lägenhet 1201 är redan färdigbesiktigad." in (page.text_content("#ovkSheet") or "")
    assert page.locator("#ovkSheet [data-sheet-choice]").count() == 2
    assert page.text_content("#ovkSheet [data-sheet-cancel]") == "Välj annan lägenhet"
    page.click("#ovkSheet [data-sheet-cancel]")
    assert page.evaluate("() => document.querySelector('.view.on').id") == "viewRond"

    before = page.evaluate("() => JSON.stringify(payload())")
    open_finished()
    page.click("#ovkSheet [data-sheet-choice='view']")
    page.wait_for_selector("#ovkUnitSummary")
    summary = page.text_content("#ovkUnitSummary") or ""
    assert "Visning – inget ändras här." in summary
    assert "Badrum" in summary
    assert "10 l/s" in summary
    assert "12 l/s" in summary
    fits = page.evaluate(
        """() => {
          const actions = document.querySelector('.ovk-summary-actions').getBoundingClientRect();
          return actions.bottom <= window.innerHeight + 1 && actions.top > 0;
        }"""
    )
    assert fits is True
    page.click("#ovkUnitSummary [data-summary-close]")
    assert page.locator("#ovkUnitSummary").count() == 0
    assert page.evaluate("() => document.querySelector('.view.on').id") == "viewRond"
    assert page.evaluate("() => JSON.stringify(payload())") == before

    open_finished()
    page.click("#ovkSheet [data-sheet-choice='amend']")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewUnit'")
    assert page.evaluate("() => activeUnit().number") == "1201"
    # Kompletteringen skriver inte över resultatet av sig själv.
    assert page.evaluate("() => activeUnit().status") == "ua"

    assert dialogs == []
    assert errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


@pytest.mark.parametrize(("width", "height"), [(375, 667), (393, 664)])
def test_start_and_round_views_fit_the_first_screen(
    field_url: str, browser: Any, width: int, height: int
) -> None:
    context = browser.new_context(
        viewport={"width": width, "height": height}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")

    # Startsidan: allt som behövs för att starta syns utan att rulla.
    page.wait_for_function("document.getElementById('footDone').textContent === 'Starta rondering'")
    assert page.evaluate("() => document.documentElement.scrollHeight - window.innerHeight") <= 0
    for selector in ("#inspector", "#systemType", "#unitSeries", "#footDone"):
        assert page.is_visible(selector)
    # Vägen tillbaka till OVK-modulens startsida finns på startsidan och i sidhuvudet.
    assert page.is_visible("#ovkHomeLink")
    assert page.get_attribute("#ovkHomeLink", "href") == "/ovk"
    assert page.get_attribute("#ovkHome", "href") == "/ovk"
    assert page.text_content("#footBack") == "OVK-översikt"
    page.click("#footBack")
    page.wait_for_url("**/ovk")
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.wait_for_function("document.getElementById('footDone').textContent === 'Starta rondering'")
    # Sällan ändrade uppgifter finns kvar, ett tryck bort.
    assert not page.is_visible("#inspection")
    page.click("#ovkStartMore > summary")
    for selector in ("#project", "#inspection", "#objectType", "#generate"):
        assert page.is_visible(selector)
    page.fill("#inspection", f"forstaskarm-{width}")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1101-1104, 1201")
    page.click("#footDone")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")

    # Ronderingsvyn: sök, filter och de första lägenheterna ligger ovanför sidfoten.
    foot_top = page.evaluate("() => document.querySelector('.foot').getBoundingClientRect().top")
    rows = page.evaluate(
        """() => [...document.querySelectorAll('#unitList .unitrow')]
          .map(row => row.getBoundingClientRect().bottom)"""
    )
    assert sum(1 for bottom in rows if bottom <= foot_top) >= 3
    assert (
        page.evaluate("() => document.getElementById('unitSearch').getBoundingClientRect().bottom")
        < foot_top
    )
    assert page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0

    # Nästa steg ligger i sidfoten tillsammans med synk.
    assert page.text_content("#footDone") == "Fortsätt · lgh 1101"
    assert page.is_visible("#footSync")
    page.click("#footDone")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewUnit'")
    assert page.evaluate("() => activeUnit().number") == "1101"
    assert not page.is_visible("#footSync")

    page.evaluate(
        """() => { for (const unit of state.units) {
            unit.status = 'ua'; unit.checked_at = new Date().toISOString(); }
          renderRond(); view('viewRond'); }"""
    )
    # Utan återstående enheter är nästa steg att granska och avsluta; synk ligger bredvid.
    assert page.text_content("#footDone") == "Granska och avsluta"
    assert page.is_visible("#footSync")
    assert errors == []
    context.close()


def test_premises_are_inspected_room_by_room_in_one_pass(field_url: str, browser: Any) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    page = flow.page
    dialogs: list[str] = []
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "lokaltest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "FTX")
    page.fill("#unitSeries", "1001")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 1")
    page.click("#addPremises")
    page.fill("#ovkSheet_name", "Kontor AB")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.activeUnitId && activeUnit().kind === 'premises'")

    def step() -> str:
        return str(flow.state("document.getElementById('ovkWizard').dataset.step"))

    def advance_to(target: str, never: str = "") -> None:
        for _ in range(8):
            if step() == target:
                break
            assert not never or step() != never
            page.click("#footDone")
            page.wait_for_timeout(120)
        flow.expect_step(target)

    # Rum 1: inventera, kontrollera, mät, dokumentera – i ett svep.
    flow.expect_step("room")
    page.locator("#ovkWizard .ovk-wz-grid button").first.click()
    page.fill("#ovkSheet_nr", "101")
    page.click("#ovkSheet [data-sheet-submit]")
    flow.expect_step("don")
    page.click("[aria-label='Öka Tilluftsdon']")
    page.wait_for_function("state.measurements.length === 1")
    page.click("[aria-label='Öka Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 2")
    advance_to("point")
    assert "Mätning i rummet" in (page.text_content("#ovkStepTitle") or "")
    assert "Don 1 av 2" in (page.text_content("#ovkWizard .ovk-wz-room") or "")
    assert page.text_content("#footDone") == "Nästa don"
    page.fill("#ovkWzFlow", "20")
    flow.next("point")
    assert "Don 2 av 2" in (page.text_content("#ovkWizard .ovk-wz-room") or "")
    assert page.text_content("#footDone") == "Till anmärkningar"
    page.fill("#ovkWzFlow", "18")
    flow.next("remark")
    assert "Rum för rum" in (page.text_content("#ovkStepTitle") or "")
    # Tillbaka från anmärkningssteget landar på rummets sista don, inte i ett annat varv.
    page.click("#footBack")
    flow.expect_step("point")
    assert "Don 2 av 2" in (page.text_content("#ovkWizard .ovk-wz-room") or "")
    assert page.input_value("#ovkWzFlow") == "18"
    flow.next("remark")
    flow.answer("Nej, inget att anmärka", "done")
    assert page.text_content("#ovkWizard .ovk-wz-title") == "Rummet är klart"
    assert "Mätt 2 av 2 don" in (page.text_content("#ovkWizard") or "")
    assert page.text_content("#footDone") == "+ Nästa rum"

    # Byt namn: kopplingarna till don och mätvärden ligger kvar.
    room_id = flow.state("state.rooms[0].room_id")
    page.click("#ovkWzRename")
    page.fill("#ovkSheet_name", "Mötesrum Alfa")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.rooms[0].name === 'Mötesrum Alfa'")
    flow.expect_step("done")
    assert flow.state("state.rooms[0].room_id") == room_id
    assert (
        flow.state("state.measurements.filter(m => m.room_id === state.rooms[0].room_id).length")
        == 2
    )
    assert (page.text_content("#ovkWizard .ovk-wz-room") or "") == "Mötesrum Alfa"

    # Ett don utan värde nås direkt från klarsteget, även utan sparat varvläge.
    assert page.locator("#ovkWzMeasureRoom").count() == 0
    page.evaluate(
        """() => { state.measurements[1].measured_value = null;
          delete state.field_progress[state.activeUnitId]; renderUnit(); }"""
    )
    flow.expect_step("done")
    assert page.text_content("#ovkWzMeasureRoom") == "Mät rummets don (1 kvar)"
    page.click("#ovkWzMeasureRoom")
    flow.expect_step("point")
    assert "Don 2 av 2" in (page.text_content("#ovkWizard .ovk-wz-room") or "")
    page.fill("#ovkWzFlow", "18")
    flow.next("remark")
    flow.answer("Nej, inget att anmärka", "done")
    assert page.locator("#ovkWzMeasureRoom").count() == 0

    # Rum 2 utan don: mätmomentet hoppas över.
    flow.next("room")
    page.fill("#ovkWzRoomName", "Förråd väst")
    page.click("#ovkWzRoomSave")
    flow.expect_step("don")
    advance_to("done", never="point")
    assert "Mätt" not in (page.text_content("#ovkWizard") or "")

    # Ingen separat mätrunda: sista rummet leder direkt till slutkontrollen.
    page.click("#ovkWizard button:text-is('Alla rum klara – till slutkontroll')")
    page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Slutkontroll')"
    )
    page.click("#footBack")
    flow.expect_step("done")
    assert flow.state("state.measurements.map(m => m.measured_value).sort().join()") == "18,20"
    assert dialogs == []
    assert flow.errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_premises_rooms_suggest_the_last_verified_room_of_the_same_type(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    page = flow.page
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "kopieratest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "FTX")
    page.fill("#unitSeries", "1001")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 1")
    page.click("#addPremises")
    page.fill("#ovkSheet_name", "Kontor AB")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.activeUnitId && activeUnit().kind === 'premises'")

    def step() -> str:
        return str(flow.state("document.getElementById('ovkWizard').dataset.step"))

    def finish_room() -> None:
        for _ in range(10):
            if step() == "done":
                break
            if step() == "remark":
                page.click("#ovkWizard button:text-is('Nej, inget att anmärka')")
            elif step() == "clean":
                page.click("#ovkWizard button:text-is('Rena')")
            else:
                page.click("#footDone")
            page.wait_for_timeout(120)
        flow.expect_step("done")

    def add_room(name: str) -> None:
        flow.expect_step("room")
        page.fill("#ovkWzRoomName", name)
        page.click("#ovkWzRoomSave")
        flow.expect_step("don")

    def room_points(index: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = flow.state(
            f"state.measurements.filter(m => m.room_id === state.rooms[{index}].room_id)"
        )
        return result

    # Kontor 101: två frånluft och en tilluft, med projekterat flöde och mätvärde.
    add_room("Kontor 101")
    assert page.locator("#ovkWzCopyRoom").count() == 0
    page.click("[aria-label='Öka Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 1")
    page.click("[aria-label='Öka Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 2")
    page.click("[aria-label='Öka Tilluftsdon']")
    page.wait_for_function("state.measurements.length === 3")
    page.evaluate(
        """() => { state.measurements[0].designed_value = '15';
          state.measurements[0].measured_value = '14'; }"""
    )
    finish_room()

    # Kontor 102 får förslaget, med källan utskriven.
    flow.next("room")
    add_room("Kontor 102")
    assert page.text_content("#ovkWzCopyRoom") == "Som Kontor 101: 1 tilluft · 2 frånluft"
    page.click("#ovkWzCopyRoom")
    page.wait_for_function("state.measurements.length === 6")
    flow.expect_step("don")
    copied = room_points(1)
    original_ids = {point["measurement_id"] for point in room_points(0)}
    assert sorted(point["point_type"] for point in copied) == [
        "franluftsdon",
        "franluftsdon",
        "tilluftsdon",
    ]
    # Egna id:n, projekterat flöde följer med, mätvärden gör det aldrig.
    assert original_ids.isdisjoint(point["measurement_id"] for point in copied)
    assert [point.get("designed_value") for point in copied].count("15") == 1
    assert all(point.get("measured_value") in (None, "") for point in copied)
    assert flow.state("state.findings.length") == 0
    # Förslaget går att korrigera: ett frånluftsdon tas bort innan rummet verifieras.
    page.click("[aria-label='Minska Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 5")
    finish_room()

    # Annan rumstyp får inget förslag.
    flow.next("room")
    add_room("Förråd väst")
    assert page.locator("#ovkWzCopyRoom").count() == 0
    finish_room()

    # Kontor 103 föreslår den senast verifierade konfigurationen, från Kontor 102.
    flow.next("room")
    add_room("Kontor 103")
    assert page.text_content("#ovkWzCopyRoom") == "Som Kontor 102: 1 tilluft · 1 frånluft"

    # Lämnar man rummet mitt i kopieringen hamnar inga don i ett annat rum.
    before = flow.state("state.measurements.length")
    page.evaluate(
        """() => { document.getElementById('ovkWzCopyRoom').click();
          state.activeRoomId = state.rooms[2].room_id; }"""
    )
    page.wait_for_timeout(400)
    assert len(room_points(2)) == 0
    page.evaluate(
        """() => { const room = state.rooms[3];
          state.measurements = state.measurements.filter(m => m.room_id !== room.room_id);
          state.activeRoomId = room.room_id; renderUnit(); }"""
    )
    assert flow.state("state.measurements.length") == before
    flow.expect_step("don")

    # Funktionen går att stänga av och slå på igen.
    page.click("#ovkWzCopyOff")
    page.wait_for_selector("#ovkWzCopyOn")
    assert page.locator("#ovkWzCopyRoom").count() == 0
    flow.expect_step("don")
    page.click("#ovkWzCopyOn")
    page.wait_for_selector("#ovkWzCopyRoom")
    # Förslaget kan ignoreras: egna don registreras som vanligt.
    page.click("[aria-label='Öka Tilluftsdon']")
    page.wait_for_function("state.measurements.length === 6")
    assert page.locator("#ovkWzCopyRoom").count() == 0

    assert flow.errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_rooms_can_be_opened_in_any_order_and_finished_rooms_ask_first(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    page = flow.page
    dialogs: list[str] = []
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "rumslistetest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "FTX")
    page.fill("#unitSeries", "1001")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 1")
    page.click("#addPremises")
    page.fill("#ovkSheet_name", "Kontor AB")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.activeUnitId && activeUnit().kind === 'premises'")

    def add_room(name: str) -> None:
        flow.expect_step("room")
        page.fill("#ovkWzRoomName", name)
        page.click("#ovkWzRoomSave")
        flow.expect_step("don")

    def advance(target: str) -> None:
        for _ in range(10):
            current = flow.state("document.getElementById('ovkWizard').dataset.step")
            if current == target:
                break
            if current == "clean":
                page.click("#ovkWizard button:text-is('Rena')")
            elif current == "transfer":
                page.click("#ovkWizard button:text-is('Ja')")
            elif current == "remark":
                page.click("#ovkWizard button:text-is('Nej, inget att anmärka')")
            else:
                page.click("#footDone")
            page.wait_for_timeout(120)
        flow.expect_step(target)

    def rows() -> dict[str, str]:
        result: dict[str, str] = page.evaluate(
            """() => Object.fromEntries([...document.querySelectorAll('#ovkWizard .ovk-wz-roomrow')]
              .map(row => [row.querySelector('.ovk-wz-roomname').textContent,
                           row.querySelector('.tag').textContent]))"""
        )
        return result

    # Kontor 101 görs klart, Kontor 102 lämnas halvvägs med ett omätt don.
    assert page.locator("#ovkWzRoomListLink").count() == 0
    add_room("Kontor 101")
    page.click("[aria-label='Öka Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 1")
    advance("point")
    page.fill("#ovkWzFlow", "12")
    advance("done")
    assert page.locator("#ovkWzAllRooms").count() == 0
    flow.next("room")
    add_room("Kontor 102")
    page.click("[aria-label='Öka Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 2")
    advance("point")
    flow.next("remark")
    advance("done")
    flow.next("room")
    add_room("Förråd")

    # Rumslistan nås från rumsväljaren och visar status per rum.
    page.evaluate("() => document.getElementById('footBack').click()")
    page.wait_for_function("state.activeRoomId === state.rooms[1].room_id")
    flow.expect_step("done")
    page.click("#ovkWzAllRooms")
    flow.expect_step("roomList")
    assert rows() == {"Kontor 101": "Klart", "Kontor 102": "1 don omätta", "Förråd": "Pågående"}

    # En obesvarad överluftsfråga gör att rummet inte räknas som klart, och rummet
    # öppnas på den frågan utan mellanfråga.
    page.evaluate(
        """() => { const check = state.visual_checks.find(
            item => item.room_id === state.rooms[0].room_id);
          check.transfer = ''; renderUnit(); }"""
    )
    assert rows()["Kontor 101"] == "Pågående"
    page.click("#ovkWizard .ovk-wz-roomrow >> text=Kontor 101")
    flow.expect_step("transfer")
    assert page.locator("#ovkSheet").count() == 0
    flow.answer("Ja", "point")
    advance("done")
    page.evaluate("() => document.getElementById('footDone').click()")
    page.wait_for_function("state.activeRoomId === state.rooms[1].room_id")
    advance("done")
    page.click("#ovkWzAllRooms")
    flow.expect_step("roomList")
    assert rows()["Kontor 101"] == "Klart"

    # Ett klart rum öppnas inte direkt.
    page.click("#ovkWizard .ovk-wz-roomrow >> text=Kontor 101")
    page.wait_for_selector("#ovkSheet")
    assert "Kontor 101 är redan klart." in (page.text_content("#ovkSheet") or "")
    assert page.text_content("#ovkSheet [data-sheet-cancel]") == "Välj annat rum"
    page.click("#ovkSheet [data-sheet-cancel]")
    flow.expect_step("roomList")
    assert flow.state("state.activeRoomId === state.rooms[1].room_id") is True

    page.click("#ovkWizard .ovk-wz-roomrow >> text=Kontor 101")
    page.click("#ovkSheet [data-sheet-choice='view']")
    flow.expect_step("done")
    assert (page.text_content("#ovkWizard .ovk-wz-room") or "") == "Kontor 101"

    page.click("#ovkWzAllRooms")
    flow.expect_step("roomList")
    page.click("#ovkWizard .ovk-wz-roomrow >> text=Kontor 101")
    page.click("#ovkSheet [data-sheet-choice='amend']")
    flow.expect_step("don")
    assert (page.text_content("#ovkWizard .ovk-wz-room") or "") == "Kontor 101"
    assert flow.state("state.measurements[0].measured_value") == "12"

    # Ett påbörjat rum öppnas direkt där arbetet står.
    advance("done")
    page.click("#ovkWzAllRooms")
    page.click("#ovkWizard .ovk-wz-roomrow >> text=Förråd")
    flow.expect_step("don")
    assert page.locator("#ovkSheet").count() == 0
    assert (page.text_content("#ovkWizard .ovk-wz-room") or "") == "Förråd"

    assert dialogs == []
    assert flow.errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_start_page_offers_continue_and_new_inspection(field_url: str, browser: Any) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")

    def on_view(name: str) -> None:
        page.wait_for_function("name => document.querySelector('.view.on').id === name", arg=name)

    # Utan sparade besiktningar visas formuläret direkt.
    page.wait_for_function("document.getElementById('footDone').textContent === 'Starta rondering'")
    assert not page.is_visible("#ovkContinueCard")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "forsta-besiktningen")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1001-1003")
    page.click("#footDone")
    on_view("viewRond")
    page.evaluate("() => persist()")

    # Tillbaka på startsidan: Fortsätt först, formuläret ett tryck bort.
    page.click("#footBack")
    on_view("viewStart")
    page.wait_for_selector("#ovkContinueCard [data-inspection='forsta-besiktningen']")
    assert not page.is_visible("#inspector")
    assert "0/3 besiktigade" in (page.text_content("#ovkContinueCard") or "")
    assert page.text_content("#footDone") == "Fortsätt · forsta-besiktningen"
    assert page.evaluate("() => document.documentElement.scrollHeight - window.innerHeight") <= 0
    page.click("#footDone")
    on_view("viewRond")
    assert page.evaluate("() => state.units.length") == 3

    # Ny besiktning får ett eget id och skriver inte i den som var öppen.
    page.click("#footBack")
    on_view("viewStart")
    page.click("#ovkNewInspection")
    assert page.is_visible("#inspector")
    assert page.text_content("#footDone") == "Starta rondering"
    new_id = page.input_value("#inspection")
    assert new_id.startswith("ovk-") and new_id != "forsta-besiktningen"
    assert page.input_value("#unitSeries") == ""
    page.fill("#unitSeries", "2001")
    # Systemtypen ärvs inte från den förra besiktningen: den måste väljas.
    assert page.input_value("#systemType") == ""
    page.click("#footDone")
    page.wait_for_function(
        "document.getElementById('draftStatus').textContent.includes('systemtyp')"
    )
    assert page.evaluate("() => document.querySelector('.view.on').id") == "viewStart"
    assert page.evaluate("() => state.inspection_id") == "forsta-besiktningen"
    page.select_option("#systemType", "FTX")
    # Enhetslistan kan inte byggas på i den tidigare besiktningen härifrån.
    assert not page.is_visible("#generate")
    page.evaluate("() => document.getElementById('generate').onclick()")
    page.wait_for_timeout(200)
    assert page.evaluate("() => [state.inspection_id, state.units.length]") == [
        "forsta-besiktningen",
        3,
    ]
    page.click("#footDone")
    on_view("viewRond")
    page.wait_for_function("state.units.length === 1")
    assert page.evaluate("() => state.inspection_id") == new_id
    page.evaluate("() => persist()")

    # Båda finns kvar och går att växla mellan.
    page.click("#footBack")
    on_view("viewStart")
    page.wait_for_function(
        "document.querySelectorAll('#ovkContinueCard [data-inspection]').length === 2"
    )
    page.click("#ovkContinueCard [data-inspection='forsta-besiktningen']")
    on_view("viewRond")
    page.wait_for_function("state.inspection_id === 'forsta-besiktningen'")
    assert page.evaluate("() => state.units.map(unit => unit.number).join()") == "1001,1002,1003"

    assert dialogs == []
    assert errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_access_revisit_and_key_status_are_registered_and_summarised(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "tilltradestest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1101-1104")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 4")

    def unit(number: str) -> dict[str, Any]:
        result: dict[str, Any] = page.evaluate(
            "number => payload().units.find(item => item.number === number)", number
        )
        return result

    def open_key_step(number: str) -> None:
        page.click(f"#unitList [data-unit] >> text={number}")
        page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'room'")
        page.click("#footBack")
        page.wait_for_function(
            "document.getElementById('ovkStepTitle').textContent.includes('nycklar')"
        )

    def to_list() -> None:
        page.evaluate("() => { renderRond(); view('viewRond'); }")

    # Tillträde väljs med knappar och är skilt från nyckeln.
    open_key_step("1101")
    assert page.evaluate("() => document.documentElement.scrollHeight - window.innerHeight") <= 0
    assert page.text_content("#unitAccessBtn") == "Tillträde: –"
    page.click("#unitAccessBtn")
    assert page.locator("#ovkSheet [data-sheet-choice]").count() == 5
    page.click("#ovkSheet [data-sheet-choice='resident']")
    page.wait_for_function("activeUnit().access === 'resident'")
    assert page.text_content("#unitAccessBtn") == "Tillträde: Boende öppnade"
    assert unit("1101")["access"] == "resident"
    assert unit("1101").get("key") is None

    # Huvudnyckel som tillträde kräver kommentaren om huvudnyckeln. Avbryts
    # kommentaren ändras varken tillträdet eller nyckeln.
    page.click("#unitAccessBtn")
    page.click("#ovkSheet [data-sheet-choice='master_key']")
    page.wait_for_selector("#ovkSheet_note")
    page.click("#ovkSheet [data-sheet-cancel]")
    page.wait_for_selector("#ovkSheet", state="detached")
    assert unit("1101")["access"] == "resident"
    assert not (unit("1101").get("key") or {}).get("master_key_used")
    page.click("#unitAccessBtn")
    page.click("#ovkSheet [data-sheet-choice='master_key']")
    page.wait_for_selector("#ovkSheet_note")
    page.fill("#ovkSheet_note", "Lånad av förvaltaren")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("activeUnit().key && activeUnit().key.master_key_used === true")
    page.wait_for_function("activeUnit().access === 'master_key'")
    assert unit("1101")["access"] == "master_key"
    # Tillträdet rör inte enhetens egen nyckel: den är fortfarande inte mottagen.
    assert unit("1101")["key"]["received"] is False
    # Byts tillträdet följer huvudnyckelmarkeringen med, och tvärtom.
    page.click("#unitAccessBtn")
    page.click("#ovkSheet [data-sheet-choice='open']")
    page.wait_for_function("activeUnit().access === 'open'")
    assert unit("1101")["key"]["master_key_used"] is False
    page.click("#unitAccessBtn")
    page.click("#ovkSheet [data-sheet-choice='master_key']")
    page.fill("#ovkSheet_note", "Lånad av förvaltaren")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("activeUnit().access === 'master_key'")
    page.click("#keyMaster")
    page.wait_for_function("activeUnit().access === ''")
    assert unit("1101")["key"]["master_key_used"] is False
    page.click("#unitAccessBtn")
    page.click("#ovkSheet [data-sheet-choice='master_key']")
    page.fill("#ovkSheet_note", "Lånad av förvaltaren")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("activeUnit().access === 'master_key'")

    # Återbesök kan sättas på en enhet som är besiktad till en del.
    assert page.text_content("#unitRevisitBtn") == "Återbesök: nej"
    page.click("#unitRevisitBtn")
    page.wait_for_function("activeUnit().revisit_required === true")
    assert page.text_content("#unitRevisitBtn") == "Återbesök krävs"
    assert unit("1101")["revisit_required"] is True
    # Oanvända fält skickas inte alls.
    assert "access" not in unit("1102")
    assert "revisit_required" not in unit("1102")

    # BOM frågar efter notering och om återbesök krävs.
    to_list()
    open_key_step("1102")
    # Avbryt registrerar ingen BOM och ändrar ingenting.
    page.click("#unitRevisitBtn")
    page.wait_for_function("activeUnit().revisit_required === true")
    before_bom = page.evaluate("() => JSON.stringify(payload())")
    page.click("#bom")
    page.fill("#ovkSheet_note", "Skrivet men avbrutet")
    page.click("#ovkSheet [data-sheet-cancel]")
    page.wait_for_selector("#ovkSheet", state="detached")
    assert page.evaluate("() => document.querySelector('.view.on').id") == "viewUnit"
    assert page.evaluate("() => JSON.stringify(payload())") == before_bom
    page.click("#unitRevisitBtn")
    page.wait_for_function("activeUnit().revisit_required === false")
    page.click("#bom")
    page.fill("#ovkSheet_note", "Ingen hemma")
    page.click("#ovkSheet [data-sheet-choice='revisit']")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")
    assert unit("1102")["status"] == "bom"
    assert unit("1102")["revisit_required"] is True
    to_list()
    open_key_step("1103")
    page.click("#bom")
    page.click("#ovkSheet [data-sheet-choice='none']")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")
    assert unit("1103")["status"] == "bom"
    assert "revisit_required" not in unit("1103")

    # Listan visar återbesök och kan filtrera på det.
    rows = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('#unitList .unitrow')]
          .map(row => [row.querySelector('.nr').textContent, row.dataset.revisit]))"""
    )
    assert rows == {"1101": "true", "1102": "true", "1103": "false", "1104": "false"}
    page.select_option("#unitFilter", "revisit")
    assert page.locator("#unitList .unitrow").count() == 2
    page.select_option("#unitFilter", "all")

    # Nyckelstatus: saknas och ej aktuell, och de tas inte emot av "Ta emot alla".
    page.click("#ovkKeyToggle")
    key_row = "#ovkKeyList [data-key='{}']"
    unit_ids = page.evaluate(
        "() => Object.fromEntries(state.units.map(u => [u.number, u.unit_id]))"
    )
    page.click(key_row.format(unit_ids["1103"]) + " button:text-is('Saknas')")
    page.click(key_row.format(unit_ids["1104"]) + " button:text-is('Ej aktuell')")
    assert unit("1103")["key"]["state"] == "missing"
    assert unit("1104")["key"]["state"] == "not_applicable"
    assert "Saknas" in (page.text_content(key_row.format(unit_ids["1103"])) or "")
    # Ångra tar bort markeringen, och den går att sätta igen.
    page.click(key_row.format(unit_ids["1103"]) + " button:text-is('Ångra')")
    assert unit("1103")["key"].get("state", "") == ""
    page.click(key_row.format(unit_ids["1103"]) + " button:text-is('Saknas')")
    page.click("#ovkKeyReceiveAll")
    page.click("#ovkKeyReceiveAll")
    page.wait_for_function(
        "state.units.find(item => item.number === '1102').key && "
        "state.units.find(item => item.number === '1102').key.received === true"
    )
    assert unit("1103")["key"]["received"] is False
    assert unit("1104")["key"]["received"] is False
    # Tas en nyckel ändå emot försvinner den uttryckliga statusen.
    page.click(key_row.format(unit_ids["1104"]) + " button:text-is('Ta emot')")
    assert unit("1104")["key"]["received"] is True
    assert unit("1104")["key"].get("state", "") == ""
    page.click("#ovkKeyToggle")

    # En nyckel som är "ej aktuell" och sedan används som huvudnyckel eller lämnas
    # tillbaka från enhetskortet får inte fastna i en kombination som synken avvisar.
    page.evaluate(
        """() => { const u = state.units.find(item => item.number === '1104');
          u.key = {received: false, received_at: null, returned: false, returned_at: null,
                   master_key_used: false, master_key_note: '', returned_method: '',
                   state: 'not_applicable'};
          state.activeUnitId = u.unit_id; }"""
    )
    page.evaluate("() => returnActiveKey('hand')")
    page.wait_for_function("activeUnit().key.returned === true")
    assert unit("1104")["key"].get("state", "") == ""
    _validated_payload(page.evaluate("() => payload()"))
    page.evaluate(
        """() => { const key = activeUnit().key;
          Object.assign(key, {received: false, received_at: null, returned: false,
            returned_at: null, returned_method: '', state: 'not_applicable'}); }"""
    )
    page.evaluate("() => { void recordMasterKey(); }")
    page.wait_for_selector("#ovkSheet_note")
    page.fill("#ovkSheet_note", "Lånad igen")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("activeUnit().key.master_key_used === true")
    assert unit("1104")["key"].get("state", "") == ""
    _validated_payload(page.evaluate("() => payload()"))
    page.evaluate("() => { state.activeUnitId = null; return persist(); }")

    # Dagsavslut samlar det som måste vara omhändertaget.
    page.click("#ovkDayEnd")
    page.wait_for_selector("#ovkDayEndView")
    sections = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('#ovkDayEndView [data-section]')]
          .map(block => [block.dataset.section,
                         [...block.querySelectorAll('p')].map(p => p.textContent)]))"""
    )
    assert len(sections["Nycklar ute"]) == 3
    assert sections["Nycklar som saknas"] == ["Lgh 1103"]
    assert sections["Återbesök krävs"] == ["Lgh 1101", "Lgh 1102 · Ingen hemma"]
    assert len(sections["Ej tillgängliga (BOM)"]) == 2
    assert sections["Ej påbörjade"] == ["Lgh 1101", "Lgh 1104"]
    before = page.evaluate("() => JSON.stringify(payload())")
    page.click("#ovkDayEndView [data-day-end-close]")
    assert page.locator("#ovkDayEndView").count() == 0
    assert page.evaluate("() => JSON.stringify(payload())") == before

    # Allt överlever omladdning och godtas av synkkontraktet.
    _reload_after_save(page)
    page.wait_for_function("typeof state === 'object' && state.units.length === 4")
    assert unit("1101")["access"] == "master_key"
    assert unit("1102")["revisit_required"] is True
    assert unit("1103")["key"]["state"] == "missing"
    assert dialogs == []
    assert errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_system_type_is_chosen_explicitly_and_can_be_corrected(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    page = flow.page
    dialogs: list[str] = []
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")

    # Ingen systemtyp är förvald: utan val startar ingen rondering.
    assert page.input_value("#systemType") == ""
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "systemtest")
    page.fill("#inspector", "Test Testsson")
    page.fill("#unitSeries", "1101")
    page.click("#footDone")
    page.wait_for_function(
        "document.getElementById('draftStatus').textContent.includes('systemtyp')"
    )
    assert page.evaluate("() => document.querySelector('.view.on').id") == "viewStart"
    page.select_option("#systemType", "F")
    page.click("#footDone")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")

    # Ronderingsvyn säger vad systemtypen innebär.
    assert page.text_content("#roundSystemBtn") == "System: F · friskluft"

    def don_step_offers_supply() -> bool:
        page.click("#footDone")
        page.wait_for_function("document.querySelector('.view.on').id === 'viewUnit'")
        flow.expect_step("room")
        flow.room("Sovrum")
        offered = bool(page.locator("[aria-label='Öka Tilluftsdon']").count() > 0)
        page.evaluate("() => { renderRond(); view('viewRond'); }")
        return offered

    assert don_step_offers_supply() is False

    # Fel vald systemtyp rättas härifrån, utan att börja om.
    page.click("#roundSystemBtn")
    assert page.locator("#ovkSheet [data-sheet-choice]").count() == 5
    page.click("#ovkSheet [data-sheet-choice='FTX']")
    page.wait_for_function("state.system_type === 'FTX'")
    assert page.text_content("#roundSystemBtn") == "System: FTX · tilluft"
    assert page.input_value("#systemType") == "FTX"
    # Ett uppdrag från kontoret vars tillåtna systemtyper inte är inlästa erbjuder inget
    # byte, och ett inläst uppdrag erbjuder bara sina egna typer.
    page.evaluate("() => { state.assignment_name = 'Brf Exempel'; renderRond(); }")
    assert page.text_content("#roundSystemBtn") == "System: FTX · tilluft"
    assert page.is_disabled("#roundSystemBtn")
    page.evaluate(
        """() => { for (const option of document.getElementById('systemType').options)
            option.disabled = !['FT', 'FTX'].includes(option.value);
          renderRond(); }"""
    )
    page.click("#roundSystemBtn")
    assert page.locator("#ovkSheet [data-sheet-choice]").count() == 2
    page.click("#ovkSheet [data-sheet-cancel]")
    page.evaluate(
        """() => { for (const option of document.getElementById('systemType').options)
            option.disabled = false;
          state.assignment_name = ''; renderRond(); }"""
    )

    _reload_after_save(page)
    page.wait_for_function("typeof state === 'object' && state.units.length === 1")
    assert page.evaluate("() => state.system_type") == "FTX"
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")

    page.click("#footDone")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewUnit'")
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'don'")
    assert page.locator("[aria-label='Öka Tilluftsdon']").count() == 1
    page.click("[aria-label='Öka Tilluftsdon']")
    page.wait_for_function("state.measurements.some(m => m.point_type === 'tilluftsdon')")
    # Med tilluft ställs ingen fråga om friskluftsventil.
    for _ in range(8):
        step = flow.state("document.getElementById('ovkWizard').dataset.step")
        assert step != "fresh"
        if step == "remark":
            break
        if step == "clean":
            page.click("#ovkWizard button:text-is('Rena')")
        elif step == "transfer":
            page.click("#ovkWizard button:text-is('Ja')")
        else:
            page.click("#footDone")
        page.wait_for_timeout(120)
    flow.expect_step("remark")

    assert dialogs == []
    assert flow.errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


def test_field_work_is_reviewed_and_finished_from_the_round_view(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "avslutstest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1101-1103")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 3")

    def sections() -> dict[str, list[str]]:
        result: dict[str, list[str]] = page.evaluate(
            """() => Object.fromEntries(
              [...document.querySelectorAll('#ovkFinishView [data-section]')]
                .map(block => [block.dataset.section,
                               [...block.querySelectorAll('p')].map(p => p.textContent)]))"""
        )
        return result

    def set_units(script: str) -> None:
        page.evaluate(f"() => {{ {script}; renderRond(); view('viewRond'); }}")

    # 1101 klar med ett mätt don, 1102 påbörjad men inte klar, 1103 orörd.
    set_units(
        """const [a, b] = state.units;
        a.status = 'ua'; a.checked_at = new Date().toISOString();
        state.rooms.push({room_id: 'r1', unit_id: a.unit_id, name: 'Badrum'},
                         {room_id: 'r2', unit_id: b.unit_id, name: 'Badrum'});
        state.measurements.push({measurement_id: 'm1', inspection_id: state.inspection_id,
          unit_id: a.unit_id, room_id: 'r1', point_id: 'p1', point_label: 'F1',
          point_type: 'franluftsdon', measured_value: '12', designed_value: null,
          measurable: true, note: '', photo_ids: []})"""
    )
    _validated_payload(page.evaluate("() => payload()"))

    # En påbörjad enhet som inte är klar hindrar avslut.
    page.click("#ovkFinishOpen")
    page.wait_for_selector("#ovkFinishView")
    found = sections()
    assert found["Måste åtgärdas först"] == ["Lgh 1102 är påbörjad men inte klar"]
    assert "Lgh 1103 är inte besiktad" in found["Kräver uppmärksamhet"]
    assert "1 av 3 enheter besiktade" in found["Genomfört"]
    assert "1 don mätta" in found["Genomfört"]
    # Ett don som inte gått att mäta räknas inte som mätt.
    page.click("#ovkFinishView [data-finish-close]")
    set_units(
        """state.measurements.push({...state.measurements[0], measurement_id: 'm2',
          point_id: 'p2', point_label: 'F2', measured_value: null, measurable: false,
          not_measurable_reason: 'Ej åtkomligt'})"""
    )
    page.click("#ovkFinishOpen")
    page.wait_for_selector("#ovkFinishView")
    assert "1 don mätta · 1 ej mätbara" in sections()["Genomfört"]
    page.click("#ovkFinishView [data-finish-close]")
    set_units("state.measurements = state.measurements.filter(m => m.measurement_id !== 'm2')")
    page.click("#ovkFinishOpen")
    page.wait_for_selector("#ovkFinishView")
    assert page.is_disabled("#ovkFinishConfirm")
    page.click("#ovkFinishView [data-finish-close]")
    assert page.evaluate("() => state.field_work_completed_at") is None

    # Utan tillträde går det att avsluta, men omfattningen måste dokumenteras.
    set_units(
        """const [, b, c] = state.units;
        state.rooms = state.rooms.filter(room => room.unit_id !== b.unit_id);
        for (const unit of [b, c]) { unit.status = 'bom'; unit.bom_at = new Date().toISOString(); }
        b.bom_note = 'Ingen hemma'; b.revisit_required = true"""
    )
    assert page.text_content("#footDone") == "Granska och avsluta"
    page.click("#footDone")
    page.wait_for_selector("#ovkFinishView")
    found = sections()
    assert "Måste åtgärdas först" not in found
    assert (
        "Lgh 1102 – ingen tillgång (BOM): Ingen hemma · återbesök krävs"
        in found["Kräver uppmärksamhet"]
    )
    assert page.is_enabled("#ovkFinishConfirm")
    page.click("#ovkFinishConfirm")
    assert "Skriv vilka enheter" in (page.text_content("#ovkFinishMsg") or "")
    assert page.evaluate("() => state.field_work_completed_at") is None
    page.fill("#ovkFinishNote", "1102 och 1103 ej tillgängliga, återbesök bokas.")
    page.click("#ovkFinishConfirm")
    page.wait_for_function("Boolean(state.field_work_completed_at)")
    assert page.locator("#ovkFinishView").count() == 0

    # Fältarbetet är avslutat utan att något protokoll finns; knappen är inaktiv.
    banner = page.text_content("#ovkFieldWork") or ""
    assert "Fältarbete avslutat" in banner
    assert "Protokoll: inte skapat" in banner
    assert page.is_disabled("#ovkProtocolBtn")
    assert "Kommer snart" in (page.text_content("#ovkProtocolBtn") or "")
    # Bannern är låg nog att enhetslistan syns under den.
    assert (
        page.evaluate(
            "() => document.getElementById('ovkFieldWork').getBoundingClientRect().height"
        )
        <= 120
    )
    assert page.text_content("#footDone") == "Synka"
    sent = page.evaluate("() => payload()")
    assert sent["field_work_note"] == "1102 och 1103 ej tillgängliga, återbesök bokas."
    data = _validated_payload(sent)
    assert data.field_work_completed_at == sent["field_work_completed_at"]

    # Blir en enhet åter påbörjad men inte klar gäller avslutet inte längre: det skickas
    # inte, tas bort i vyn och måste göras om.
    saved_at = sent["field_work_completed_at"]
    page.evaluate(
        """() => { const a = state.units[0]; a.status = 'ej_paborjad'; a.checked_at = null; }"""
    )
    assert "field_work_completed_at" not in page.evaluate("() => payload()")
    set_units("void 0")
    assert page.evaluate("() => state.field_work_completed_at") is None
    assert not page.is_visible("#ovkFieldWork")
    assert "Avslutet togs bort" in (page.text_content("#ovkFieldWorkNote") or "")
    set_units(
        f"""const a = state.units[0]; a.status = 'ua'; a.checked_at = new Date().toISOString();
        state.field_work_completed_at = '{saved_at}';
        state.field_work_note = '1102 och 1103 ej tillgängliga, återbesök bokas.'"""
    )
    page.wait_for_function("Boolean(state.field_work_completed_at)")
    assert page.is_visible("#ovkFieldWork")
    assert (page.text_content("#ovkFieldWorkNote") or "") == ""

    # Läggs en enhet till efter ett avslut utan notering gäller avslutet inte längre.
    set_units(
        """for (const unit of state.units) { unit.status = 'ua'; unit.bom_at = null;
          unit.bom_note = ''; unit.revisit_required = false;
          unit.checked_at = new Date().toISOString(); }
        state.field_work_note = ''"""
    )
    assert page.is_visible("#ovkFieldWork")
    assert "field_work_completed_at" in page.evaluate("() => payload()")
    set_units(
        """state.units.push({unit_id: 'u-ny', inspection_id: state.inspection_id,
          number: '1104', kind: 'apartment', label: '', status: 'ej_paborjad', checked_at: null,
          bom_at: null, bom_note: '', key: null, system_type: null})"""
    )
    assert page.evaluate("() => state.field_work_completed_at") is None
    assert "Avslutet togs bort" in (page.text_content("#ovkFieldWorkNote") or "")
    set_units(
        f"""state.units = state.units.filter(unit => unit.unit_id !== 'u-ny');
        const [, b, c] = state.units;
        for (const unit of [b, c]) {{ unit.status = 'bom'; unit.checked_at = null;
          unit.bom_at = new Date().toISOString(); }}
        b.bom_note = 'Ingen hemma'; b.revisit_required = true;
        state.field_work_completed_at = '{saved_at}';
        state.field_work_note = '1102 och 1103 ej tillgängliga, återbesök bokas.'"""
    )
    page.wait_for_function("Boolean(state.field_work_completed_at)")

    # I ett uppdrag från kontoret är rum förifyllda: en orörd enhet är inte påbörjad
    # och hindrar inte avslut.
    set_units(
        """state.assignment_name = 'Brf Exempel';
        state.rooms.push({room_id: 'r-plan', unit_id: state.units[1].unit_id, name: 'Kök'});
        state.units[1].status = 'ej_paborjad'; state.units[1].bom_at = null"""
    )
    assert page.evaluate("() => unitProgress(state.units[1])") == "not_started"
    assert page.evaluate("() => Boolean(state.field_work_completed_at)") is True
    set_units(
        """state.assignment_name = '';
        state.rooms = state.rooms.filter(room => room.room_id !== 'r-plan');
        state.units[1].status = 'bom'; state.units[1].bom_at = new Date().toISOString()"""
    )

    # Första trycket på Öppna igen följer inte med till en annan besiktning.
    page.click("#ovkReopen")
    assert page.text_content("#ovkReopen") == "Bekräfta"
    set_units("state.inspection_id = 'annan-besiktning'")
    assert page.text_content("#ovkReopen") == "Öppna igen"
    set_units("state.inspection_id = 'avslutstest'")
    assert page.text_content("#ovkReopen") == "Öppna igen"

    # Avslutet överlever omladdning och går att öppna igen med två tryck.
    _reload_after_save(page)
    page.wait_for_function("typeof state === 'object' && state.units.length === 3")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")
    assert page.evaluate("() => Boolean(state.field_work_completed_at)") is True
    page.click("#ovkReopen")
    assert page.evaluate("() => Boolean(state.field_work_completed_at)") is True
    page.click("#ovkReopen")
    page.wait_for_function("state.field_work_completed_at === null")
    assert not page.is_visible("#ovkFieldWork")
    reopened = page.evaluate("() => payload()")
    assert "field_work_completed_at" not in reopened
    assert "field_work_note" not in reopened

    assert dialogs == []
    assert errors == []
    _validated_payload(reopened)
    context.close()


def test_keys_are_numbered_in_reception_order_and_returned_top_down(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _record_dialogs(page, dialogs)
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.click("#ovkStartMore > summary")
    page.fill("#inspection", "nyckelnummertest")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1101-1102, 1201, 1301")
    page.click("#footDone")
    page.wait_for_function("state.units.length === 4")
    ids = page.evaluate("() => Object.fromEntries(state.units.map(u => [u.number, u.unit_id]))")

    def row(number: str) -> str:
        return f"#ovkKeyList [data-key='{ids[number]}']"

    def tags() -> dict[str, Any]:
        result: dict[str, Any] = page.evaluate(
            "() => Object.fromEntries(payload().units.map(u => [u.number, u.key && u.key.tag]))"
        )
        return result

    # Nycklarna tas emot i porten i den ordning de boende kommer.
    page.click("#ovkKeyToggle")
    for number in ("1201", "1101", "1301"):
        page.click(row(number) + " button:text-is('Ta emot')")
    assert tags() == {"1101": 2, "1102": None, "1201": 1, "1301": 3}
    assert "Lgh 1201 · nr 1" in (page.text_content(row("1201")) or "")
    assert "Huvudnyckel" in (page.text_content("#ovkKeyList [data-key='master']") or "")
    page.click("#ovkKeyList [data-key='master'] button:text-is('Ta emot')")
    assert page.evaluate("() => payload().master_key.tag === undefined") is True

    # Numret syns i enhetslistan, så att rätt bricka tas fram vid lägenheten.
    meta = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('#unitList .unitrow')]
          .map(r => [r.querySelector('.nr').textContent, r.textContent]))"""
    )
    assert "Nyckel nr 2 ute" in meta["1101"]
    assert "Nyckel" not in meta["1102"]

    # Ångras mottagandet behålls numret, och nästa nyckel får nästa lediga nummer.
    page.click(row("1101") + " button:text-is('Ångra')")
    assert tags()["1101"] == 2
    page.click(row("1102") + " button:text-is('Ta emot')")
    assert tags()["1102"] == 4
    page.click(row("1101") + " button:text-is('Ta emot')")
    assert tags()["1101"] == 2

    # Fel bricka rättas, men två lägenheter kan inte få samma nummer.
    # Felet visas i bladet, som stannar öppet så att inmatningen inte går förlorad.
    page.click(f"[data-key-tag='{ids['1102']}']")
    page.fill("#ovkSheet_tag", "3")
    page.click("#ovkSheet [data-sheet-submit]")
    assert "Nr 3 används redan av lgh 1301" in (page.text_content("#ovkSheet") or "")
    assert page.is_visible("#ovkSheet .ovk-sheet-status")
    assert tags()["1102"] == 4
    page.fill("#ovkSheet_tag", "abc")
    page.click("#ovkSheet [data-sheet-submit]")
    assert "heltal från 1 till 999" in (page.text_content("#ovkSheet") or "")
    page.fill("#ovkSheet_tag", "0")
    page.click("#ovkSheet [data-sheet-submit]")
    assert "heltal från 1 till 999" in (page.text_content("#ovkSheet") or "")
    page.fill("#ovkSheet_tag", "9")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.units.find(unit => unit.number === '1102').key.tag === 9")
    assert page.locator("#ovkSheet").count() == 0

    # Rättas ett nummer upp till taket fortsätter numreringen på lägsta lediga nummer,
    # och en mottagen nyckel utan nummer kan alltid numreras för hand.
    assert (
        page.evaluate(
            """() => { const keep = state.units.map(u => u.key && u.key.tag);
          state.units[0].key.tag = 999; const next = nextKeyTag();
          state.units.forEach((u, i) => { if (u.key) u.key.tag = keep[i]; });
          return next; }"""
        )
        == 2
    )
    page.evaluate(
        """() => { state.units.find(u => u.number === '1301').key.tag = undefined;
          renderRond(); }"""
    )
    assert page.text_content(f"[data-key-tag='{ids['1301']}']") == "Sätt nr"
    page.click(f"[data-key-tag='{ids['1301']}']")
    page.fill("#ovkSheet_tag", "3")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("state.units.find(unit => unit.number === '1301').key.tag === 3")

    # En enhet som öppnats med huvudnyckel har ingen egen nyckel: återlämning från
    # enhetskortet delar inte ut något nummer.
    page.evaluate(
        """async () => { const unit = state.units.find(u => u.number === '1101');
          const saved = unit.key;
          unit.key = {received: false, received_at: null, returned: false, returned_at: null,
            master_key_used: true, master_key_note: 'Lånad', returned_method: '', state: ''};
          state.activeUnitId = unit.unit_id;
          await returnActiveKey('hand');
          window.masterOnlyTag = unit.key.tag === undefined ? null : unit.key.tag;
          unit.key = saved; state.activeUnitId = null; await persist(); }"""
    )
    assert page.evaluate("() => window.masterOnlyTag") is None

    # Enhetskortet visar numret.
    page.click("#ovkKeyToggle")
    page.click("#unitList [data-unit] >> text=1201")
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'room'")
    page.click("#footBack")
    page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('nycklar')"
    )
    assert "Nyckel nr 1" in (page.text_content("#keyInfo") or "")
    page.evaluate("() => { renderRond(); view('viewRond'); }")

    # Återlämningsrundan: bara nycklar som är ute, högsta våningen först.
    page.click("#ovkKeyToggle")
    page.check("#ovkKeyOnlyHeld")
    order = page.evaluate(
        "() => [...document.querySelectorAll('#ovkKeyList .ovk-key-row strong')]"
        ".map(node => node.textContent)"
    )
    assert order == [
        "Lgh 1301 · nr 3",
        "Lgh 1201 · nr 1",
        "Lgh 1101 · nr 2",
        "Lgh 1102 · nr 9",
        "Huvudnyckel",
    ]
    # Lokaler och nummer utan våningsplan ligger efter lägenheterna, huvudnyckeln sist.
    page.evaluate(
        """() => { const stamp = new Date().toISOString();
          const key = tag => ({received: true, received_at: stamp, returned: false,
            returned_at: null, master_key_used: false, master_key_note: '',
            returned_method: '', state: '', tag});
          state.units.unshift(
            {unit_id: 'u-lokal', inspection_id: state.inspection_id, number: 'L2',
             kind: 'premises', label: 'Tvättstuga', status: 'ej_paborjad', checked_at: null,
             bom_at: null, bom_note: '', key: key(21), system_type: null},
            {unit_id: 'u-udda', inspection_id: state.inspection_id, number: '901',
             kind: 'apartment', label: '', status: 'ej_paborjad', checked_at: null,
             bom_at: null, bom_note: '', key: key(22), system_type: null});
          renderRond(); }"""
    )
    mixed = page.evaluate(
        "() => [...document.querySelectorAll('#ovkKeyList .ovk-key-row strong')]"
        ".map(node => node.textContent)"
    )
    assert mixed == [
        "Lgh 1301 · nr 3",
        "Lgh 1201 · nr 1",
        "Lgh 1101 · nr 2",
        "Lgh 1102 · nr 9",
        "Lgh 901 · nr 22",
        "Tvättstuga · nr 21",
        "Huvudnyckel",
    ]
    page.evaluate(
        """() => { state.units = state.units.filter(
            unit => !['u-lokal', 'u-udda'].includes(unit.unit_id)); renderRond(); }"""
    )
    page.click(row("1301") + " button:text-is('Brevlåda')")
    assert "Lgh 1301" not in (page.text_content("#ovkKeyList") or "")
    assert (
        page.evaluate("() => state.units.find(u => u.number === '1301').key.returned_method")
        == "mailbox"
    )

    # Sammanställningen namnger nycklar som är ute med nummer.
    page.click("#ovkFinishOpen")
    page.wait_for_selector("#ovkFinishView")
    assert "Lgh 1201 (nr 1)" in (page.text_content("#ovkFinishView") or "")
    page.click("#ovkFinishView [data-finish-close]")

    # Numren överlever omladdning och godtas av synkkontraktet.
    _reload_after_save(page)
    page.wait_for_function("typeof state === 'object' && state.units.length === 4")
    assert tags() == {"1101": 2, "1102": 9, "1201": 1, "1301": 3}
    assert dialogs == []
    assert errors == []
    _validated_payload(page.evaluate("() => payload()"))
    context.close()


_CONTRAST_AUDIT = """() => {
  const parse = value => {
    const m = /rgba?\\(([^)]+)\\)/.exec(value);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const over = (top, under) => ({
    r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a),
    b: top.b * top.a + under.b * (1 - top.a), a: 1});
  const lum = c => { const f = v => { v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const background = node => {
    const layers = [];
    for (let at = node; at; at = at.parentElement) {
      const c = parse(getComputedStyle(at).backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
    }
    let result = parse(getComputedStyle(document.documentElement).backgroundColor) ||
      {r: 255, g: 255, b: 255, a: 1};
    if (result.a < 1) result = {r: 255, g: 255, b: 255, a: 1};
    for (const layer of layers.reverse()) result = over(layer, result);
    return result;
  };
  const failures = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  for (let text = walker.nextNode(); text; text = walker.nextNode()) {
    const node = text.parentElement;
    if (!node || seen.has(node) || !text.textContent.trim()) continue;
    seen.add(node);
    if (['SCRIPT', 'STYLE', 'OPTION'].includes(node.tagName)) continue;
    const box = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    if (!box.width || !box.height || style.visibility === 'hidden') continue;
    if (node.closest('[hidden]') || node.closest('[disabled]')) continue;
    const bg = background(node);
    const fg = over(parse(style.color), bg);
    const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
    const ratio = (a + 0.05) / (b + 0.05);
    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5))
      failures.push(node.tagName + '#' + node.id + '.' + node.className + ' "' +
        text.textContent.trim().slice(0, 30) + '" ' + ratio.toFixed(2));
  }
  return failures;
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_both_themes_keep_text_readable(field_url: str, browser: Any, scheme: str) -> None:
    context = browser.new_context(
        viewport={"width": 375, "height": 667},
        is_mobile=True,
        has_touch=True,
        color_scheme=scheme,
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(field_url)
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    page.wait_for_function("document.getElementById('footDone').textContent === 'Starta rondering'")

    def audit(where: str) -> None:
        failures = page.evaluate(_CONTRAST_AUDIT)
        assert failures == [], f"{scheme} / {where}: {failures}"

    def paper() -> float:
        value: float = page.evaluate(
            """() => { const m = /rgba?\\(([^)]+)\\)/.exec(
                getComputedStyle(document.documentElement).backgroundColor);
              const [r, g, b] = m[1].split(',').map(Number); return (r + g + b) / 3; }"""
        )
        return value

    # Temat följer telefonens inställning.
    assert (paper() < 60) is (scheme == "dark")
    page.click("#ovkStartMore > summary")
    audit("start")
    page.fill("#inspection", f"tematest-{scheme}")
    page.fill("#inspector", "Test Testsson")
    page.select_option("#systemType", "F")
    page.fill("#unitSeries", "1101-1103")
    page.click("#footDone")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")
    page.evaluate(
        """() => { const [a, b] = state.units;
          a.status = 'ua'; a.checked_at = new Date().toISOString();
          b.status = 'bom'; b.bom_at = new Date().toISOString(); b.revisit_required = true;
          renderRond(); }"""
    )
    audit("rondering")
    page.click("#ovkKeyToggle")
    page.locator("#ovkKeyList button:text-is('Ta emot')").nth(1).click()
    audit("nycklar")
    page.click("#ovkKeyToggle")
    page.click("#ovkFinishOpen")
    page.wait_for_selector("#ovkFinishView")
    audit("sammanställning")
    page.click("#ovkFinishView [data-finish-close]")
    page.click("#footDone")
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'room'")
    audit("rumsval")
    page.click("#ovkWizard [data-room='Badrum']")
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'don'")
    page.click("[aria-label='Öka Frånluftsdon']")
    page.wait_for_function("state.measurements.length === 1")
    audit("don")
    page.click("#footDone")
    page.wait_for_function("document.getElementById('ovkWizard').dataset.step === 'clean'")
    audit("fråga")
    for _ in range(6):
        if "nycklar" in (page.text_content("#ovkStepTitle") or ""):
            break
        page.click("#footBack")
        page.wait_for_timeout(150)
    page.wait_for_selector("#unitAccessBtn", state="visible")
    audit("enhetskort")
    page.click("#unitAccessBtn")
    page.wait_for_selector("#ovkSheet")
    audit("blad")
    page.click("#ovkSheet [data-sheet-cancel]")

    # Valet på startsidan går före telefonens inställning och finns kvar efter omladdning.
    other = "light" if scheme == "dark" else "dark"
    page.evaluate("() => { view('viewStart'); }")
    page.click("#ovkNewInspection")
    page.select_option("#ovkTheme", other)
    assert (paper() < 60) is (other == "dark")
    audit("start, valt tema")
    page.reload()
    page.wait_for_function("typeof state === 'object' && typeof payload === 'function'")
    assert page.evaluate("() => document.documentElement.dataset.theme") == other
    assert (paper() < 60) is (other == "dark")
    assert errors == []
    context.close()


def test_ports_keep_four_digit_numbers_and_ask_for_the_next_port(
    field_url: str, browser: Any
) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    flow = _Flow(context.new_page())
    page = flow.page
    dialogs: list[str] = []
    _record_dialogs(page, dialogs)
    flow.start(field_url)

    def port_options() -> list[str]:
        result: list[str] = page.eval_on_selector_all(
            "#unitPort option", "items => items.map(o => o.textContent)"
        )
        return result

    def rows() -> list[str]:
        result: list[str] = page.eval_on_selector_all(
            "#unitList .unitrow .nr", "items => items.map(n => n.textContent)"
        )
        return result

    # Utan portar är ronderingen som förut: inget portval, bara en länk för att ange port.
    page.evaluate("() => renderRond()")
    assert page.evaluate("() => document.getElementById('unitPort').closest('div').hidden")
    assert not page.evaluate("() => document.getElementById('addPort').hidden")
    assert flow.state("portsInUse()") is False
    assert "port" not in flow.state("payload().units[0]")

    # Första lägenheten går till slutkontroll. Lägenheterna läggs i var sin port,
    # som när uppdraget kommer från kontoret med trapphus.
    flow.room("Hall")
    flow.next("remark")
    flow.answer("Nej, inget att anmärka", "done")
    page.click("#footDone")
    page.wait_for_function(
        "document.getElementById('ovkStepTitle').textContent.includes('Slutkontroll')"
    )
    page.evaluate(
        """() => { state.units[0].port = '54'; state.units[1].port = '56';
                   state.ports = ['54', '56']; state.active_port = '54';
                   updateFooter('viewUnit'); }"""
    )
    assert page.text_content("#ovkStepTitle").startswith("Lgh 54-1001")
    # Nästa lägenhet söks bara i porten: 1002 ligger i port 56.
    assert page.text_content("#footDone") == "Klar – till listan"

    # Portens sista lägenhet klarmarkeras: frågan om nästa port kommer direkt.
    page.click("#footDone")
    page.wait_for_selector("#ovkSheet")
    assert page.text_content("#ovkSheetTitle") == "Port 54 är klar"
    assert page.eval_on_selector_all(
        "#ovkSheet [data-sheet-choice]", "items => items.map(b => b.textContent)"
    ) == ["Gå till port 56", "Ny port", "Granska och avsluta"]
    assert flow.state("state.units[0].status") == "ua"
    page.click("#ovkSheet [data-sheet-choice='next']")
    page.wait_for_function("activePort() === '56'")
    assert rows() == ["1002"]
    assert page.text_content("#rondMeta").endswith("· Port 56")
    assert port_options() == ["Port 54 (1)", "Port 56 (1)", "+ Ny port…"]
    assert page.evaluate("() => document.getElementById('addPort').hidden")
    assert page.text_content("#cTotal") == "1"
    assert page.text_content("#footDone") == "Fortsätt · lgh 56-1002"

    # Tillbaka i den klara porten erbjuder sidfoten samma fråga igen.
    page.select_option("#unitPort", "54")
    page.wait_for_function("activePort() === '54'")
    assert rows() == ["1001"]
    assert page.text_content("#footDone") == "Port 54 klar"
    page.click("#footDone")
    page.wait_for_selector("#ovkSheet")
    page.click("#ovkSheet [data-sheet-cancel]")
    assert flow.state("activePort()") == "54"

    # En ny port anges på ett ställe. Samma fyrsiffriga nummer får finnas där.
    page.select_option("#unitPort", "__new")
    page.wait_for_selector("#ovkSheet")
    page.fill("#ovkSheet_port", "54")
    page.click("#ovkSheet [data-sheet-submit]")
    assert page.text_content("#ovkSheet .ovk-sheet-status") == (
        "Porten finns redan. Välj den i listan."
    )
    page.fill("#ovkSheet_port", "  58  ")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("activePort() === '58'")
    assert rows() == []
    assert page.text_content("#unitEmpty") == (
        "Inga enheter i port 58 ännu. Lägg till lägenheter eller lokaler."
    )
    # En tom port erbjuder inte avslut av hela besiktningen: port 56 har en lägenhet kvar.
    assert flow.state("nextPendingPort()") == "56"
    assert page.text_content("#footDone") != "Granska och avsluta"
    page.click("#footDone")
    assert page.query_selector("#ovkFinishView") is None
    assert page.query_selector("#ovkSheet") is None
    page.click("#addUnit")
    page.wait_for_selector("#ovkSheet")
    page.fill("#ovkSheet_numbers", "1001, 1101")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function("document.querySelectorAll('#unitList .unitrow').length === 2")
    assert rows() == ["1001", "1101"]
    assert page.text_content("#unitAddStatus") == "2 enhet(er) tillagda i port 58: 1001, 1101"
    # Våningsfiltret läser fortfarande våningen ur de fyrsiffriga numren.
    assert not page.evaluate("() => document.getElementById('unitFloor').closest('div').hidden")
    # Samma nummer en gång till i samma port läggs inte till.
    page.click("#addUnit")
    page.wait_for_selector("#ovkSheet")
    page.fill("#ovkSheet_numbers", "1001")
    page.click("#ovkSheet [data-sheet-submit]")
    page.wait_for_function(
        "document.getElementById('unitAddStatus').textContent"
        " === 'Alla angivna enheter finns redan.'"
    )
    assert flow.state("state.units.length") == 4

    # Lägenhetsmallen i fält fungerar med samma nummer i flera portar, och
    # visar vilken port mallen kommer från.
    assert flow.state(
        "fieldTemplateCandidates(state.units.find(u => u.port === '58' && u.number === '1001'))"
        ".map(unitNumberText)"
    ) == ["54-1001"]

    # Porten följer med enheten i synken och godtas av servern.
    data = _validated_payload(flow.state("payload()"))
    assert [(unit.port, unit.number) for unit in data.units] == [
        ("54", "1001"),
        ("56", "1002"),
        ("58", "1001"),
        ("58", "1101"),
    ]
    assert [unit.display_number for unit in data.units] == [
        "54-1001",
        "56-1002",
        "58-1001",
        "58-1101",
    ]

    # Portarna och den valda porten finns kvar efter omladdning.
    _reload_after_save(page)
    page.wait_for_function("typeof state === 'object' && state.units.length === 4")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")
    assert flow.state("activePort()") == "58"
    assert port_options() == ["Port 54 (1)", "Port 56 (1)", "Port 58 (2)", "+ Ny port…"]
    assert rows() == ["1001", "1101"]

    # Ett utkast från före portarna (utan dessa uppgifter) öppnas som förut.
    page.evaluate(
        """async () => {
          for (const unit of state.units) delete unit.port;
          state.units.splice(2); state.ports = []; state.active_port = null;
          await persist();
          const key = draftKey(state.project_id, state.inspection_id);
          const draft = await dbGet(DRAFT_STORE, key);
          delete draft.ports; delete draft.active_port;
          await dbPut(DRAFT_STORE, draft);
        }"""
    )
    page.reload()
    page.wait_for_function("typeof state === 'object' && state.units.length === 2")
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")
    assert flow.state("[state.ports, state.active_port, portsInUse()]") == [[], None, False]
    assert rows() == ["1001", "1002"]
    assert page.evaluate("() => document.getElementById('unitPort').closest('div').hidden")
    assert not page.text_content("#rondMeta").endswith("Port")
    assert all("port" not in unit for unit in flow.state("payload().units"))
    assert flow.errors == []
    assert dialogs == []
    context.close()


def test_assignment_with_trapphus_opens_with_ports_in_the_field(
    field_url: str, browser: Any
) -> None:
    import httpx
    from test_ovk_workflow import _workflow_payload

    root = field_url.removesuffix("/ovk/falt")
    api = httpx.Client(base_url=root)
    property_url = "/api/ovk/projects/p1/fastighet/object-1"
    assert (
        api.put(
            property_url,
            json={
                "fastighetsbeteckning": "Björken 12",
                "byggnader": [{"byggnad_id": "building-1", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    assert (
        api.put(
            "/api/ovk/registry/besiktningsman/person-1",
            json={
                "namn": "Test Kontrollant",
                "behorighet": "K",
                "certifieringsorgan": "Test",
                "certnummer": "123",
                "giltig_till": "2030-12-31",
            },
        ).status_code
        == 200
    )
    structure = {
        "trapphus": [
            # Ett trapphus utan enheter står först i registret.
            {"trapphus_id": "t-52", "namn": "52", "adress": ""},
            {"trapphus_id": "t-54", "namn": "54", "adress": "Storgatan 54"},
            {"trapphus_id": "t-56", "namn": "56", "adress": "Storgatan 56"},
        ],
        "units": [
            {"unit_id": "u1", "number": "1001", "kind": "apartment", "trapphus_id": "t-54"},
            {"unit_id": "u2", "number": "1101", "kind": "apartment", "trapphus_id": "t-54"},
            {"unit_id": "u3", "number": "1001", "kind": "apartment", "trapphus_id": "t-56"},
        ],
        "systems": [{"system_id": "FTX01", "system_type": "FTX", "label": "LB01"}],
        "technical_spaces": [],
    }
    assert api.put(property_url + "/byggnad/building-1/struktur", json=structure).status_code == 200
    payload = _workflow_payload()
    payload["planning"] = {
        "inspector_id": "person-1",
        "planned_date": "2027-01-15",
        "inspection_type": "aterkommande",
    }
    assert api.put("/api/ovk/projects/p1/inspections/ovk-001", json=payload).status_code == 200

    context = browser.new_context(
        viewport={"width": 375, "height": 667}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(field_url + "?project_id=p1&inspection_id=ovk-001")
    page.wait_for_function("typeof state === 'object' && state.units.length === 3", timeout=20000)
    page.wait_for_function("document.querySelector('.view.on').id === 'viewRond'")

    # Kontorets trapphus är portar; lägenheterna har kvar sina fyrsiffriga nummer.
    assert page.evaluate("() => state.units.map(unit => [unit.port, unit.number])") == [
        ["54", "1001"],
        ["54", "1101"],
        ["56", "1001"],
    ]
    assert page.eval_on_selector_all("#unitPort option", "o => o.map(x => x.textContent)") == [
        "Port 52 (0)",
        "Port 54 (2)",
        "Port 56 (1)",
        "+ Ny port…",
    ]
    # Den tomma porten möter en inte först: första porten med lägenheter är vald.
    assert page.evaluate("() => activePort()") == "54"
    # På en smal telefon får porten en egen rad och inget sticker ut i sidled.
    assert page.evaluate(
        "() => [document.documentElement.scrollWidth <= window.innerWidth,"
        " document.getElementById('unitPort').getBoundingClientRect().width > 250]"
    ) == [True, True]
    assert page.eval_on_selector_all(
        "#unitList .unitrow .nr", "items => items.map(n => n.textContent)"
    ) == ["1001", "1101"]
    assert page.text_content("#rondMeta").endswith("· Port 54")
    assert not page.evaluate("() => document.getElementById('unitFloor').closest('div').hidden")
    data = _validated_payload(page.evaluate("() => payload()"))
    assert [unit.display_number for unit in data.units] == ["54-1001", "54-1101", "56-1001"]
    assert errors == []
    context.close()
    api.close()
