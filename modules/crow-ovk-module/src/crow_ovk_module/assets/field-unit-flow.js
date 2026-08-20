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
  const apartments = state.units.filter(item => item.kind === 'apartment').map(item => item.number);
  const premises = state.units.filter(item => item.kind === 'premises').map(item => item.number);
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

async function addFieldUnit(kind) {
  const label = kind === 'premises' ? 'lokal(er)' : 'lägenhet(er)';
  const text = (prompt('Nummer för ' + label + ' – en eller flera (t.ex. 1101-1104, 1201):') || '').trim();
  if (!text) return;
  let numbers;
  try { numbers = parseSeries(text); } catch (error) { unitAddStatus(String(error.message || error), true); return; }
  const existing = new Set(state.units.map(item => item.number));
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
      system_type: null
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
  unitAddStatus(added.length + ' enhet(er) tillagda: ' + added.join(', '));
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
  addPremisesButton.onclick = () => addFieldUnit('premises');
  addApartmentButton.insertAdjacentElement('afterend', addPremisesButton);
}

renderUnitPreview();
