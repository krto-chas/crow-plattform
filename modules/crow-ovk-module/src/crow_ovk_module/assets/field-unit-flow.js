const originalRenderRondForUnits = renderRond;
const originalGenerateUnitsForPreview = generateUnits;

function ensureUnitPreview() {
  let preview = document.getElementById('unitPreview');
  if (preview) return preview;
  preview = document.createElement('div');
  preview.id = 'unitPreview';
  preview.className = 'status';
  const status = document.getElementById('draftStatus');
  status.parentNode.insertBefore(preview, status);
  return preview;
}

function renderUnitPreview() {
  const preview = ensureUnitPreview();
  if (!state.units.length) {
    preview.className = 'status';
    preview.textContent = 'Ingen enhetslista skapad ännu.';
    return;
  }
  preview.className = 'status pass';
  const apartments = state.units.filter(item => item.kind === 'apartment').map(unitNumberText);
  const premises = state.units.filter(item => item.kind === 'premises').map(item => item.label || item.number);
  const parts = [];
  if (apartments.length) parts.push('Lägenheter: ' + apartments.join(', '));
  if (premises.length) parts.push('Lokaler: ' + premises.join(', '));
  preview.textContent = state.units.length + ' enheter klara · ' + parts.join(' · ');
}

generateUnits = function () {
  originalGenerateUnitsForPreview();
  renderUnitPreview();
};

renderRond = function () {
  originalRenderRondForUnits();
  renderUnitPreview();
};

function unitAddStatus(message, warning = false) {
  let target = document.getElementById('unitAddStatus');
  if (!target) {
    target = document.createElement('div');
    target.id = 'unitAddStatus';
    target.className = 'status';
    document.getElementById('addUnit').parentNode.insertBefore(target, document.getElementById('addUnit').nextSibling);
  }
  target.className = 'status' + (warning ? ' warn' : ' pass');
  target.textContent = message;
}

function nextPremisesNumber() {
  // Random numeric identifier avoids allocating the same sequential number in offline drafts.
  // The UUID remains the authoritative identity; the number is retained across name changes.
  const existing = new Set(state.units.map(item => item.number));
  let number;
  do {
    const bytes = new Uint32Array(2);
    crypto.getRandomValues(bytes);
    number = String((BigInt(bytes[0]) << 21n) | BigInt(bytes[1] & 0x1fffff)).padStart(16, '0');
  } while (existing.has(number));
  return number;
}

async function addNamedPremises() {
  const answer = await askSheet({
    title: 'Lägg till lokal',
    fields: [{ id: 'name', label: 'Hyresgästens namn eller lokalnamn', required: true, placeholder: 'T.ex. Frisör Anna' }],
    submitLabel: 'Lägg till lokal'
  });
  if (!answer) return;
  const name = answer.name;
  const number = nextPremisesNumber();
  const unit = {
    unit_id: uid('unit'),
    inspection_id: state.inspection_id || document.getElementById('inspection').value.trim(),
    number,
    kind: 'premises',
    label: name,
    status: 'ej_paborjad',
    checked_at: null,
    bom_at: null,
    bom_note: '',
    key: null,
    system_type: null,
    ...(activePort() ? { port: activePort() } : {})
  };
  state.units.push(unit);
  await persist();
  renderRond();
  unitAddStatus('Lokal tillagd: ' + name + ' · internt nr ' + number);
  openUnit(unit.unit_id);
}

async function addFieldUnit(kind) {
  const label = kind === 'premises' ? 'lokal(er)' : 'lägenhet(er)';
  const answer = await askSheet({
    title: 'Lägg till ' + label,
    note: 'En eller flera, t.ex. 1101-1104, 1201.',
    fields: [{ id: 'numbers', label: 'Nummer', required: true, placeholder: '1101-1104, 1201' }],
    submitLabel: 'Lägg till'
  });
  if (!answer) return;
  const text = answer.numbers;
  let numbers;
  try { numbers = parseSeries(text); } catch (error) { unitAddStatus(String(error.message || error), true); return; }
  // Numret ska vara unikt i sin port; samma nummer får finnas i en annan.
  const port = activePort();
  const existing = new Set(portUnits(port).map(item => item.number));
  const added = [];
  let firstUnit = null;
  for (const number of numbers) {
    if (existing.has(number)) continue;
    const unit = {
      unit_id: uid('unit'),
      inspection_id: state.inspection_id || document.getElementById('inspection').value.trim(),
      number,
      kind,
      label: '',
      status: 'ej_paborjad',
      checked_at: null,
      bom_at: null,
      bom_note: '',
      key: null,
      system_type: null,
      ...(port ? { port } : {})
    };
    state.units.push(unit);
    existing.add(number);
    added.push(number);
    if (!firstUnit) firstUnit = unit;
  }
  if (!added.length) {
    unitAddStatus('Alla angivna enheter finns redan.', true);
    return;
  }
  await persist();
  renderRond();
  unitAddStatus(added.length + ' enhet(er) tillagda' + (port ? ' i port ' + port : '') + ': ' + added.join(', '));
  if (added.length === 1 && firstUnit) openUnit(firstUnit.unit_id);
}

const addApartmentButton = document.getElementById('addUnit');
addApartmentButton.textContent = '+ Lägg till lägenhet';
addApartmentButton.onclick = () => addFieldUnit('apartment');

if (!document.getElementById('addPremises')) {
  const addPremisesButton = document.createElement('button');
  addPremisesButton.className = 'btn ghost';
  addPremisesButton.id = 'addPremises';
  addPremisesButton.textContent = '+ Lägg till lokal';
  addPremisesButton.onclick = addNamedPremises;
  addApartmentButton.insertAdjacentElement('afterend', addPremisesButton);
}

renderUnitPreview();
