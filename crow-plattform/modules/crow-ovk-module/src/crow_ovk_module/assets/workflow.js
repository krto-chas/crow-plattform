const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
let loadedRecord = null;
let requestedInspection = new URLSearchParams(location.search).get('inspection_id') || '';

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(JSON.stringify(data.detail || data));
  return data;
}

function split(line) { return line.split('|').map(value => value.trim()); }
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
}
function ensureProject(id, label = id) {
  if (!id) return;
  let option = [...$('project').options].find(item => item.value === id);
  if (!option) {
    option = document.createElement('option');
    option.value = id;
    $('project').appendChild(option);
  }
  option.textContent = label || id;
}
function savedInspectionOptions(inspections) {
  return '<option value="">Ny besiktning</option>' + inspections.map(item => {
    const id = String(item.inspection_id || '');
    const label = String(item.object_name || id);
    return '<option value="' + esc(id) + '">' + esc(label) + ' · ' + esc(id) + '</option>';
  }).join('');
}

function reviewMetadata(observationId) {
  return (loadedRecord && loadedRecord.review || []).find(item => item.observation_id === observationId) || null;
}

function build() {
  const systems = $('systems').value.split(/\r?\n/).map(value => value.trim()).filter(Boolean).map(line => {
    const [id, type, label] = split(line);
    return {system_id: id, system_type: type || 'unknown', label: label || id, source_ref: null};
  });
  const checkpoints = $('checkpoints').value.split(/\r?\n/).map(value => value.trim()).filter(Boolean).map(line => {
    const [id, status, system, label, note] = split(line);
    return {checkpoint_id: id, status: status || 'not_checked', system_id: system || null, label: label || id, note: note || '', origin: 'observed', evidence_ref: null};
  });
  const review = $('review').value.split(/\r?\n/).map(value => value.trim()).filter(Boolean).map(line => {
    const [id, status, reviewer, note] = split(line);
    const previous = reviewMetadata(id);
    return {
      observation_id: id,
      source_text: previous ? previous.source_text : 'Workbench review ' + id,
      evidence_ref: previous ? previous.evidence_ref : 'workbench:' + id,
      reason: previous ? previous.reason : 'manual_review',
      status: status || 'pending',
      reviewer: reviewer || null,
      note: note || ''
    };
  });
  const previousInspection = loadedRecord && loadedRecord.inspection || {};
  return {
    inspection: {
      inspection_id: $('inspection').value.trim(),
      object: {
        object_id: $('object').value.trim(),
        project_id: $('project').value,
        building_id: $('building').value.trim(),
        name: $('name').value.trim(),
        address: $('address').value.trim() || null
      },
      systems,
      checkpoints,
      measurements: previousInspection.measurements || [],
      findings: previousInspection.findings || [],
      actions: previousInspection.actions || []
    },
    review
  };
}

function lines(items, mapper) { return (items || []).map(mapper).join('\n'); }
function contextUrl(projectId, inspectionId) {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (inspectionId) params.set('inspection_id', inspectionId);
  return params.toString();
}
function updateLinks(projectId, inspectionId) {
  const query = contextUrl(projectId, inspectionId);
  $('fieldLink').href = '/ovk/falt' + (query ? '?' + query : '');
  history.replaceState(null, '', '/ovk/besiktning' + (query ? '?' + query : ''));
}

function render(record) {
  const inspection = record.inspection || {};
  const object = inspection.object || {};
  const projectId = object.project_id || $('project').value;
  ensureProject(projectId);
  $('project').value = projectId;
  $('inspection').value = inspection.inspection_id || '';
  $('building').value = object.building_id || '';
  $('object').value = object.object_id || '';
  $('name').value = object.name || '';
  $('address').value = object.address || '';
  $('systems').value = lines(inspection.systems, item => [item.system_id, item.system_type, item.label].join(' | '));
  $('checkpoints').value = lines(inspection.checkpoints, item => [item.checkpoint_id, item.status, item.system_id || '', item.label, item.note || ''].join(' | '));
  $('review').value = lines(record.review, item => [item.observation_id, item.status, item.reviewer || '', item.note || ''].join(' | '));
  loadedRecord = record;
  $('summary').innerHTML = [
    ['Slutsats', inspection.conclusion || 'pending'],
    ['Kontroller', (inspection.checkpoints || []).length],
    ['Findings', (inspection.findings || []).length],
    ['Review kvar', record.unresolved_review_count || 0],
    ['Protokoll', record.protocol_ready ? 'KLART' : 'BLOCKERAT']
  ].map(item => '<div class="metric"><span>' + item[0] + '</span><strong>' + item[1] + '</strong></div>').join('');
  $('status').className = 'status ' + (record.protocol_ready ? 'pass' : 'warn');
  $('status').textContent = record.protocol_ready ? 'Besiktningen är sparad och protokollklar.' : 'Besiktningen är sparad som utkast.';
  updateLinks(projectId, inspection.inspection_id || '');
}

function clearInspection() {
  loadedRecord = null;
  requestedInspection = '';
  $('saved').value = '';
  $('inspection').value = 'ovk-' + new Date().toISOString().slice(0, 10);
  $('building').value = 'building-1';
  $('object').value = 'object-1';
  $('name').value = 'OVK-objekt';
  $('address').value = '';
  $('systems').value = '';
  $('checkpoints').value = '';
  $('review').value = '';
  $('summary').innerHTML = '';
  $('status').className = 'status';
  $('status').textContent = 'Nytt utkast. Fyll i underlaget och spara eller fortsätt i fältläge.';
  updateLinks($('project').value, $('inspection').value.trim());
}

async function loadInspection(projectId, inspectionId) {
  $('status').className = 'status';
  $('status').textContent = 'Laddar sparad besiktning…';
  const record = await api('/api/ovk/projects/' + enc(projectId) + '/inspections/' + enc(inspectionId));
  render(record);
  $('saved').value = inspectionId;
}

async function loadProject() {
  const projectId = $('project').value;
  if (!projectId) return;
  $('status').className = 'status';
  $('status').textContent = 'Laddar projektets besiktningar…';
  try {
    const data = await api('/api/ovk/projects/' + enc(projectId) + '/inspections');
    const inspections = data.inspections || [];
    $('saved').innerHTML = savedInspectionOptions(inspections);
    if (requestedInspection && inspections.some(item => item.inspection_id === requestedInspection)) {
      await loadInspection(projectId, requestedInspection);
      requestedInspection = '';
      return;
    }
    clearInspection();
  } catch (error) {
    $('status').className = 'status warn';
    $('status').textContent = 'Kunde inte läsa projektet: ' + error.message;
  }
}

$('project').onchange = () => { requestedInspection = ''; loadProject(); };
$('saved').onchange = async () => {
  const inspectionId = $('saved').value;
  if (!inspectionId) { clearInspection(); return; }
  try { await loadInspection($('project').value, inspectionId); }
  catch (error) { $('status').className = 'status warn'; $('status').textContent = 'Kunde inte ladda besiktningen: ' + error.message; }
};
$('reload').onclick = () => $('saved').dispatchEvent(new Event('change'));
$('newInspection').onclick = clearInspection;
$('inspection').onchange = () => updateLinks($('project').value, $('inspection').value.trim());
$('save').onclick = async () => {
  const projectId = $('project').value;
  const inspectionId = $('inspection').value.trim();
  if (!projectId || !inspectionId) { $('status').className = 'status warn'; $('status').textContent = 'Projekt och besiktnings-ID krävs.'; return; }
  try {
    const record = await api('/api/ovk/projects/' + enc(projectId) + '/inspections/' + enc(inspectionId), {
      method: 'PUT', headers: {'content-type': 'application/json'}, body: JSON.stringify(build())
    });
    render(record);
    const data = await api('/api/ovk/projects/' + enc(projectId) + '/inspections');
    $('saved').innerHTML = savedInspectionOptions(data.inspections || []);
    $('saved').value = inspectionId;
  } catch (error) {
    $('status').className = 'status warn';
    $('status').textContent = 'Kunde inte spara: ' + error.message;
  }
};
$('protocol').onclick = () => {
  const projectId = $('project').value, inspectionId = $('inspection').value.trim();
  if (projectId && inspectionId) window.open('/api/ovk/projects/' + enc(projectId) + '/inspections/' + enc(inspectionId) + '/protocol', '_blank');
};

async function init() {
  try {
    const modules = await api('/api/me/modules');
    if (!(modules.modules || []).some(item => item.id === 'ovk')) throw new Error('OVK ingår inte i licensen.');
    const projects = await api('/api/projects');
    $('project').innerHTML = projects.length ? '' : '<option value="">Inga projekt</option>';
    for (const project of projects) ensureProject(project.project_id, project.project_name || project.name || project.project_id);
    const requestedProject = new URLSearchParams(location.search).get('project_id');
    if (requestedProject && projects.some(project => project.project_id === requestedProject)) $('project').value = requestedProject;
    if (projects.length) await loadProject();
    else { $('status').textContent = 'Skapa ett projekt i Workbench först.'; $('save').disabled = true; }
  } catch (error) {
    $('status').className = 'status warn';
    $('status').textContent = 'OVK-besiktning kunde inte starta: ' + error.message;
  }
}
init();
