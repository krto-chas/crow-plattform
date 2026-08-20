const state = {projectId: null, projects: [], project: null, imports: [], modules: []};
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

function projectQuery(extra = {}) {
  const params = new URLSearchParams();
  if (state.projectId) params.set('project_id', state.projectId);
  Object.entries(extra).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const query = params.toString();
  return query ? `?${query}` : '';
}

function updateLinks() {
  const advanced = `/workbench/advanced${projectQuery()}`;
  $('advanced').href = advanced;
  $('advancedNav').href = advanced;
  document.querySelectorAll('.advanced-view').forEach(link => {
    link.href = `/workbench/advanced${projectQuery({view: link.dataset.view})}`;
  });
}

function renderModules() {
  $('moduleCount').textContent = String(state.modules.length);
  $('modules').innerHTML = state.modules.length ? state.modules.map(module => {
    const query = state.projectId ? `?project_id=${enc(state.projectId)}` : '';
    return `<article class="card">
      <div class="eyebrow">PRODUKTMODUL</div>
      <h3>${esc(module.name)}</h3>
      <p class="muted">${esc(module.id)}</p>
      <a class="button" href="${esc(module.route)}${query}">Öppna modul</a>
    </article>`;
  }).join('') : '<article class="card"><h3>Inga aktiva produktmoduler</h3><p class="muted">Administratören har inte aktiverat någon produktmodul för organisationen.</p></article>';
}

function renderImports() {
  const imports = state.imports || [];
  $('importCount').textContent = String(imports.length);
  $('cadCount').textContent = String(imports.filter(item => ['dxf', 'dwg', 'ifc'].includes(String(item.format_id || '').toLowerCase())).length);
  $('imports').className = imports.length ? '' : 'empty';
  $('imports').innerHTML = imports.length ? imports.map(asset => {
    const checksum = String(asset.checksum_sha256 || '');
    return `<div class="item">
      <div class="item-head">
        <div><strong>${esc(asset.filename || 'fil')}</strong><div class="item-meta">${esc(String(asset.format_id || asset.media_type || 'okänd').toUpperCase())} · ${esc(String(asset.size_bytes ?? ''))} byte</div></div>
        <span class="pill">${esc(String((asset.capabilities || []).join(', ') || 'underlag'))}</span>
      </div>
      ${checksum ? `<div class="actions"><a class="button secondary" target="_blank" href="/api/projects/${enc(state.projectId)}/imports/${enc(checksum)}/file">Öppna fil</a></div>` : ''}
    </div>`;
  }).join('') : 'Projektet har inga importerade filer ännu.';
}

async function loadProject() {
  state.projectId = $('project').value;
  updateLinks();
  renderModules();
  if (!state.projectId) return;
  setStatus('Laddar projektdata…');
  try {
    const [project, imports] = await Promise.all([
      api(`/api/projects/${enc(state.projectId)}`),
      api(`/api/projects/${enc(state.projectId)}/imports`)
    ]);
    state.project = project;
    state.imports = imports;
    $('documentCount').textContent = String((project.documents || []).length);
    renderImports();
    setStatus('Projektdata är laddad.', 'ok');
  } catch (error) {
    state.project = null;
    state.imports = [];
    $('documentCount').textContent = '—';
    renderImports();
    setStatus(`Kunde inte läsa projektdata: ${error.message}`, 'warn');
  }
}

async function createProject() {
  const name = window.prompt('Projektnamn');
  if (!name || !name.trim()) return;
  setStatus('Skapar projekt…');
  try {
    const created = await api('/api/projects', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({name: name.trim()})
    });
    await loadProjects(created.project_id);
    setStatus('Projektet är skapat.', 'ok');
  } catch (error) {
    setStatus(`Projektet kunde inte skapas: ${error.message}`, 'warn');
  }
}

async function uploadFiles(files) {
  if (!state.projectId || !files.length) return;
  const form = new FormData();
  Array.from(files).forEach(file => form.append('files', file));
  setStatus(`Importerar ${files.length} fil${files.length === 1 ? '' : 'er'}…`);
  try {
    await api(`/api/projects/${enc(state.projectId)}/documents`, {method: 'POST', body: form});
    await loadProject();
    setStatus('Filerna är importerade.', 'ok');
  } catch (error) {
    setStatus(`Importen misslyckades: ${error.message}`, 'warn');
  } finally {
    $('fileInput').value = '';
  }
}

async function loadProjects(preferred = null) {
  state.projects = await api('/api/projects');
  const requested = preferred || new URLSearchParams(location.search).get('project_id');
  $('project').innerHTML = state.projects.length ? state.projects.map(project => `<option value="${esc(project.project_id)}">${esc(project.project_name || project.name || project.project_id)}</option>`).join('') : '<option value="">Inga projekt</option>';
  if (requested && state.projects.some(project => project.project_id === requested)) $('project').value = requested;
  if (state.projects.length) await loadProject();
  else {
    state.projectId = null;
    state.project = null;
    state.imports = [];
    $('documentCount').textContent = '0';
    $('importCount').textContent = '0';
    $('cadCount').textContent = '0';
    $('imports').textContent = 'Skapa ett projekt för att börja.';
    updateLinks();
    renderModules();
    setStatus('Skapa ett projekt för att börja.', 'warn');
  }
}

async function init() {
  try {
    const modules = await api('/api/me/modules');
    state.modules = modules.modules || [];
    renderModules();
    $('project').addEventListener('change', loadProject);
    $('newProject').addEventListener('click', createProject);
    $('fileInput').addEventListener('change', event => uploadFiles(event.target.files || []));
    await loadProjects();
  } catch (error) {
    setStatus(`Workbench kunde inte starta: ${error.message}`, 'warn');
    $('fileInput').disabled = true;
  }
}

init();
