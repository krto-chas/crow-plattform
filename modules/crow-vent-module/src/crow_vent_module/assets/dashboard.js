const state = {projectId: null, imports: [], lastModel: null, lastCalculation: null};
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

function setStatus(id, message, kind = '') {
  const element = $(id);
  element.className = `status${kind ? ` ${kind}` : ''}`;
  element.textContent = message;
}

function cadAssets() {
  return (state.imports || []).filter(asset => ['dxf', 'dwg', 'ifc'].includes(String(asset.format_id || '').toLowerCase()));
}

function dxfAssets() {
  return cadAssets().filter(asset => String(asset.format_id || '').toLowerCase() === 'dxf');
}

function sourceRows() {
  return dxfAssets().map(asset => `
    <label class="source-row">
      <input class="calc-source" type="checkbox" value="${esc(asset.checksum_sha256)}" checked>
      <span><strong>${esc(asset.filename)}</strong><span class="item-meta">DXF · ${esc(String((asset.observations || []).length))} observationer</span></span>
      <span class="pill">geometri</span>
    </label>`).join('') || '<div class="empty">Inga DXF-ritningar finns i projektet.</div>';
}

function renderDrawings() {
  const items = cadAssets();
  $('drawingCount').textContent = String(items.length);
  $('drawings').className = items.length ? '' : 'empty';
  $('drawings').innerHTML = items.length ? items.map(asset => {
    const format = String(asset.format_id || '').toLowerCase();
    const analyzable = format === 'dxf';
    const checksum = String(asset.checksum_sha256 || '');
    return `<div class="item">
      <div class="item-head">
        <div><strong>${esc(asset.filename)}</strong><div class="item-meta">${esc(format.toUpperCase())} · ${esc(String(asset.size_bytes ?? ''))} byte</div></div>
        <span class="pill">${analyzable ? 'analysbar' : 'registrerad'}</span>
      </div>
      <div class="actions">
        ${analyzable ? `<button type="button" data-analyze="${esc(checksum)}">Analysera</button>` : '<span class="muted">Automatisk Vent-analys kräver DXF-geometri.</span>'}
        ${checksum ? `<a class="button secondary" target="_blank" href="/api/projects/${enc(state.projectId)}/imports/${enc(checksum)}/file">Öppna fil</a>` : ''}
      </div>
    </div>`;
  }).join('') : 'Projektet har inga CAD-underlag ännu.';
  $('calcSources').className = dxfAssets().length ? '' : 'empty';
  $('calcSources').innerHTML = sourceRows();
  document.querySelectorAll('[data-analyze]').forEach(button => {
    button.addEventListener('click', () => analyzeDrawing(button.dataset.analyze));
  });
}

function resetAnalysis() {
  state.lastModel = null;
  $('systemCount').textContent = '—';
  $('componentCount').textContent = '—';
  $('reviewCount').textContent = '—';
  $('analysisMeta').textContent = 'Ingen ritning analyserad.';
  $('analysis').className = 'empty';
  $('analysis').textContent = 'Välj en DXF-ritning och kör analys.';
}

function renderAnalysis(model, asset) {
  const quantity = model.quantity_takeoff || {};
  const systems = model.systems || [];
  const review = [
    ...(model.findings || []),
    ...(model.classifications || []).filter(item => item.status === 'needs_review')
  ];
  $('systemCount').textContent = String(model.system_count ?? systems.length ?? 0);
  $('componentCount').textContent = String(quantity.total_component_count ?? 0);
  $('reviewCount').textContent = String(review.length);
  $('analysisMeta').textContent = `${asset?.filename || 'Ritning'} · ${quantity.line_count || 0} mängdrader · ${quantity.total_length_m || 0} m uppmätt`;
  $('analysis').className = '';
  const quantityRows = (quantity.lines || []).slice(0, 60).map(row => `
    <div class="result-row">
      <span><strong>${esc(row.component_name || row.code || 'Post')}</strong><br><span class="muted">${esc(row.dimension || row.category || '')}</span></span>
      <span>${esc(row.quantity ?? '—')} st</span>
      <span>${row.length_m != null ? `${esc(row.length_m)} m` : ''}</span>
    </div>`).join('');
  const systemRows = systems.map(system => `
    <section class="system-card">
      <h3>${esc(system.vent_system_id || system.system_id || 'Ventilationssystem')}</h3>
      <p class="muted">${esc(system.system_kind || 'Ej fastställd')} · confidence ${Math.round(Number(system.system_confidence || 0) * 100)}% · ${esc(system.status || '')}</p>
      <p>${esc(String((system.components || []).length))} komponenter · ${esc(String(system.relation_count || 0))} relationer · ${esc(String(system.finding_count || 0))} avvikelser</p>
    </section>`).join('');
  const reviewRows = review.slice(0, 30).map(item => `
    <div class="review-item"><strong>${esc(item.title || item.source_value || 'Granskningspunkt')}</strong><div class="item-meta">${esc(item.code || item.component_name || item.detail || '')}</div></div>`).join('');
  $('analysis').innerHTML = `
    <h3>Mängdsammanställning</h3>
    ${quantityRows || '<div class="empty">Inga mängdrader identifierades.</div>'}
    <h3 style="margin-top:20px">System</h3>
    ${systemRows || '<div class="empty">Inga ventilationssystem identifierades.</div>'}
    ${reviewRows ? `<h3 style="margin-top:20px">Behöver granskas</h3>${reviewRows}` : ''}`;
}

async function analyzeDrawing(checksum) {
  if (!state.projectId) return;
  const asset = state.imports.find(item => item.checksum_sha256 === checksum);
  setStatus('status', `Analyserar ${asset?.filename || 'ritning'}…`);
  try {
    const model = await api(`/api/projects/${enc(state.projectId)}/vent/${enc(checksum)}`);
    state.lastModel = model;
    renderAnalysis(model, asset);
    setStatus('status', 'Vent-analysen är laddad.', 'ok');
  } catch (error) {
    setStatus('status', `Vent-analysen misslyckades: ${error.message}`, 'warn');
  }
}

function tableRows() {
  return $('table').value.split(/\n/).map(line => line.trim()).filter(Boolean).map(line => line.split(';').map(value => value.trim()));
}

function textSegments() {
  const value = $('text').value.trim();
  return value ? [value] : [];
}

function selectedGeometry() {
  return Array.from(document.querySelectorAll('.calc-source:checked')).map(input => input.value);
}

function renderCalculation(data) {
  const priced = data.priced || {};
  const consolidated = data.consolidated || {};
  $('calcRows').textContent = String(consolidated.line_count || 0);
  $('calcPriced').textContent = String(priced.priced_line_count || 0);
  $('calcHours').textContent = priced.labour_hours_total ?? '—';
  $('calcTotal').textContent = priced.grand_total != null ? `${priced.grand_total} ${priced.currency || 'SEK'}` : '—';
  const lines = consolidated.lines || [];
  $('resultRows').innerHTML = lines.length ? lines.map(line => `<tr><td>${esc(line.designation || line.code || line.key || '—')}</td><td>${esc(line.quantity ?? '—')}</td><td>${esc(line.unit || '—')}</td><td>${esc(line.status || '—')}</td></tr>`).join('') : '<tr><td colspan="4" class="muted">Kalkylen gav inga mängdrader.</td></tr>';
}

async function runCalculation() {
  if (!state.projectId) {
    setStatus('calcStatus', 'Välj ett projekt först.', 'warn');
    return;
  }
  let priceBook = null;
  try {
    priceBook = $('prices').value.trim() ? JSON.parse($('prices').value) : null;
  } catch (error) {
    setStatus('calcStatus', 'Ogiltig prisbok-JSON.', 'warn');
    return;
  }
  const geometryChecksums = selectedGeometry();
  const rows = tableRows();
  const segments = textSegments();
  if (!geometryChecksums.length && !rows.length && !segments.length) {
    setStatus('calcStatus', 'Välj minst en ritning eller ange mängdförteckning/beskrivning.', 'warn');
    return;
  }
  const body = {geometry_checksums: geometryChecksums, table_rows: rows, text_segments: segments};
  if (priceBook) body.price_book = priceBook;
  setStatus('calcStatus', 'Kör mängdning och kalkyl…');
  try {
    const data = await api(`/api/vent/projects/${enc(state.projectId)}/takeoff`, {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(body)
    });
    state.lastCalculation = data;
    renderCalculation(data);
    $('csv').disabled = false;
    setStatus('calcStatus', 'Kalkylen är klar.', 'ok');
  } catch (error) {
    setStatus('calcStatus', `Kalkylen misslyckades: ${error.message}`, 'warn');
  }
}

function exportCsv() {
  if (!state.lastCalculation) return;
  const lines = (state.lastCalculation.consolidated || {}).lines || [];
  const output = ['post;mängd;enhet;status', ...lines.map(line => [line.designation || line.code || line.key || '', line.quantity ?? '', line.unit || '', line.status || ''].join(';'))].join('\n');
  const url = URL.createObjectURL(new Blob(['\ufeff' + output], {type: 'text/csv;charset=utf-8'}));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'crow-vent-kalkyl.csv';
  anchor.click();
  URL.revokeObjectURL(url);
}

function updateLinks() {
  const query = state.projectId ? `?project_id=${enc(state.projectId)}` : '';
  ['openWorkbench', 'workbenchNav'].forEach(id => $(id).href = `/workbench${query}`);
  ['openQuote', 'quoteNav', 'actionQuote'].forEach(id => $(id).href = `/vent/offert${query}`);
}

async function loadProject() {
  state.projectId = $('project').value;
  updateLinks();
  resetAnalysis();
  state.lastCalculation = null;
  $('csv').disabled = true;
  if (!state.projectId) return;
  setStatus('status', 'Laddar projektets Vent-underlag…');
  try {
    state.imports = await api(`/api/projects/${enc(state.projectId)}/imports`);
    renderDrawings();
    setStatus('status', dxfAssets().length ? 'Projektunderlaget är laddat. Välj en DXF-ritning för analys.' : 'Projektet är laddat men saknar DXF-underlag.', dxfAssets().length ? 'ok' : 'warn');
  } catch (error) {
    state.imports = [];
    renderDrawings();
    setStatus('status', `Kunde inte läsa projektets underlag: ${error.message}`, 'warn');
  }
}

async function init() {
  try {
    const modules = await api('/api/me/modules');
    if (!(modules.modules || []).some(module => module.id === 'vent')) throw new Error('Vent ingår inte i licensen.');
    const projects = await api('/api/projects');
    const requested = new URLSearchParams(location.search).get('project_id');
    $('project').innerHTML = projects.length ? projects.map(project => `<option value="${esc(project.project_id)}">${esc(project.project_name || project.name || project.project_id)}</option>`).join('') : '<option value="">Inga projekt</option>';
    if (requested && projects.some(project => project.project_id === requested)) $('project').value = requested;
    $('project').addEventListener('change', loadProject);
    $('run').addEventListener('click', runCalculation);
    $('csv').addEventListener('click', exportCsv);
    if (projects.length) await loadProject();
    else {
      $('drawingCount').textContent = '0';
      $('systemCount').textContent = '0';
      $('componentCount').textContent = '0';
      $('reviewCount').textContent = '0';
      $('drawings').textContent = 'Skapa ett projekt i Workbench först.';
      $('calcSources').textContent = 'Skapa ett projekt i Workbench först.';
      setStatus('status', 'Skapa ett projekt i Workbench först.', 'warn');
    }
  } catch (error) {
    setStatus('status', `Vent kunde inte starta: ${error.message}`, 'warn');
    $('run').disabled = true;
  }
}

init();
