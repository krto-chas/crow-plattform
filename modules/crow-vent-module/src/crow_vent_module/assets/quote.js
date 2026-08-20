const state = {projectId: null, imports: [], lastQuote: null};
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const enc = encodeURIComponent;

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail || payload);
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return payload;
}

function setStatus(message, kind = '') {
  $('status').className = `status${kind ? ` ${kind}` : ''}`;
  $('status').textContent = message;
}

function dxfAssets() {
  return (state.imports || []).filter(asset => String(asset.format_id || '').toLowerCase() === 'dxf');
}

function renderDrawingSources() {
  const assets = dxfAssets();
  $('drawingSources').className = assets.length ? '' : 'empty';
  $('drawingSources').innerHTML = assets.length ? assets.map(asset => `
    <label class="source-row">
      <input class="quote-source" type="checkbox" value="${esc(asset.checksum_sha256)}" checked>
      <span><strong>${esc(asset.filename)}</strong><span class="item-meta">DXF · ${esc(String((asset.observations || []).length))} observationer</span></span>
      <span class="pill">geometri</span>
    </label>`).join('') : 'Projektet har inga DXF-ritningar. Du kan fortfarande använda mängdförteckning eller beskrivning.';
}

function selectedGeometry() {
  return Array.from(document.querySelectorAll('.quote-source:checked')).map(input => input.value);
}

function tableRows() {
  return $('table').value.split(/\n/).map(line => line.trim()).filter(Boolean).map(line => line.split(';').map(value => value.trim()));
}

function textSegments() {
  const value = $('text').value.trim();
  return value ? [value] : [];
}

function lines(id) {
  return $(id).value.split(/\n/).map(line => line.trim()).filter(Boolean);
}

function updateLinks() {
  const query = state.projectId ? `?project_id=${enc(state.projectId)}` : '';
  $('dashboardNav').href = `/vent${query}`;
  $('calculationNav').href = `/vent${query}#kalkyl`;
  $('backVent').href = `/vent${query}`;
  $('workbenchNav').href = `/workbench${query}`;
}

async function loadProject() {
  state.projectId = $('project').value;
  updateLinks();
  if (!state.projectId) return;
  setStatus('Laddar projektets ritningsunderlag…');
  try {
    state.imports = await api(`/api/projects/${enc(state.projectId)}/imports`);
    renderDrawingSources();
    setStatus('Projektunderlaget är laddat.', 'ok');
  } catch (error) {
    state.imports = [];
    renderDrawingSources();
    setStatus(`Kunde inte läsa projektets underlag: ${error.message}`, 'warn');
  }
}

function renderQuote(quote) {
  $('title').textContent = `Offert – ${quote.project_name}`;
  $('recipient').textContent = quote.customer_name ? `Till: ${quote.customer_name}` : '';
  $('total').textContent = `${quote.offer_total} ${quote.currency}`;
  $('ready').innerHTML = quote.ready_to_send
    ? '<div class="status ok">Sändklar: inga oprissatta eller olösta poster.</div>'
    : `<div class="status warn">UTKAST: ${esc(quote.unpriced_line_count)} oprissatta och ${esc(quote.reservation_count)} reserverade poster måste hanteras.</div>`;
  $('breakdown').innerHTML = `
    <div class="item"><strong>Självkostnad</strong><div class="item-meta">${esc(quote.base_cost)} ${esc(quote.currency)}</div></div>
    <div class="item"><strong>Omkostnad ${esc(quote.overhead_percent)} %</strong><div class="item-meta">${esc(quote.overhead_amount)} ${esc(quote.currency)}</div></div>
    <div class="item"><strong>Risk ${esc(quote.risk_percent)} %</strong><div class="item-meta">${esc(quote.risk_amount)} ${esc(quote.currency)}</div></div>
    <div class="item"><strong>Vinst ${esc(quote.profit_percent)} %</strong><div class="item-meta">${esc(quote.profit_amount)} ${esc(quote.currency)}</div></div>`;
  $('meta').textContent = `Datum ${quote.quote_date} · giltig ${quote.validity_days} dagar · prisbok ${quote.source_price_book_id}`;
  $('scopeOut').textContent = quote.scope_note ? `Omfattning: ${quote.scope_note}` : '';
  $('exclusionsOut').innerHTML = quote.exclusions.length ? `<h3>Undantag</h3><ul>${quote.exclusions.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : '';
}

async function runQuote() {
  if (!state.projectId) {
    setStatus('Välj ett projekt först.', 'warn');
    return;
  }
  let priceBook = null;
  try {
    priceBook = $('prices').value.trim() ? JSON.parse($('prices').value) : null;
  } catch (error) {
    setStatus('Ogiltig prisbok-JSON.', 'warn');
    return;
  }
  const geometryChecksums = selectedGeometry();
  const rows = tableRows();
  const segments = textSegments();
  if (!geometryChecksums.length && !rows.length && !segments.length) {
    setStatus('Välj minst en ritning eller ange mängdförteckning/beskrivning.', 'warn');
    return;
  }
  const takeoff = {geometry_checksums: geometryChecksums, table_rows: rows, text_segments: segments};
  if (priceBook) takeoff.price_book = priceBook;
  const selectedProject = $('project').selectedOptions[0];
  const quote = {
    project_name: selectedProject?.textContent || state.projectId,
    customer_name: $('customer').value,
    quote_date: $('date').value,
    validity_days: Number($('validity').value),
    overhead_percent: $('overhead').value,
    risk_percent: $('risk').value,
    profit_percent: $('profit').value,
    scope_note: $('scope').value,
    exclusions: lines('exclusions')
  };
  setStatus('Bygger offert…');
  try {
    const result = await api(`/api/vent/projects/${enc(state.projectId)}/quote`, {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({takeoff, quote})
    });
    state.lastQuote = result;
    renderQuote(result);
    $('print').disabled = false;
    $('csv').disabled = false;
    setStatus('Offertutkastet är skapat.', 'ok');
  } catch (error) {
    setStatus(`Offerten kunde inte skapas: ${error.message}`, 'warn');
  }
}

function exportCsv() {
  const quote = state.lastQuote;
  if (!quote) return;
  const rows = [
    ['fält', 'värde'],
    ['projekt', quote.project_name],
    ['kund', quote.customer_name],
    ['självkostnad', quote.base_cost],
    ['omkostnad', quote.overhead_amount],
    ['risk', quote.risk_amount],
    ['vinst', quote.profit_amount],
    ['offertpris', quote.offer_total],
    ['valuta', quote.currency],
    ['sändklar', quote.ready_to_send]
  ];
  const output = rows.map(row => row.join(';')).join('\n');
  const url = URL.createObjectURL(new Blob(['\ufeff' + output], {type: 'text/csv;charset=utf-8'}));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'crow-vent-offert.csv';
  anchor.click();
  URL.revokeObjectURL(url);
}

async function init() {
  $('date').value = new Date().toISOString().slice(0, 10);
  try {
    const modules = await api('/api/me/modules');
    if (!(modules.modules || []).some(module => module.id === 'vent')) throw new Error('Vent ingår inte i licensen.');
    const projects = await api('/api/projects');
    const requested = new URLSearchParams(location.search).get('project_id');
    $('project').innerHTML = projects.length ? projects.map(project => `<option value="${esc(project.project_id)}">${esc(project.project_name || project.name || project.project_id)}</option>`).join('') : '<option value="">Inga projekt</option>';
    if (requested && projects.some(project => project.project_id === requested)) $('project').value = requested;
    $('project').addEventListener('change', loadProject);
    $('run').addEventListener('click', runQuote);
    $('print').addEventListener('click', () => window.print());
    $('csv').addEventListener('click', exportCsv);
    if (projects.length) await loadProject();
    else {
      renderDrawingSources();
      setStatus('Skapa ett projekt i Workbench först.', 'warn');
      $('run').disabled = true;
    }
  } catch (error) {
    setStatus(`Offertytan kunde inte starta: ${error.message}`, 'warn');
    $('run').disabled = true;
  }
}

init();
