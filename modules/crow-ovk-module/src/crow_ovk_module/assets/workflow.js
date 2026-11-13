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
    review,
    coverage: loadedRecord?.coverage || null
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
  $('planningSummary').textContent = record.planning ? 'Planerat: '+record.planning.planned_date+' · '+(record.planning.inspection_type==='forstagang'?'Första besiktning':'Återkommande')+' · Kontrollant: '+record.planning.inspector_id : '';
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
  $('planningSummary').textContent = '';
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

let draftProperties = [];
let draftRevision = 0;
let draftId = null;
let draftStructure = null;
let draftStructureRevision = 0;
function resetDraftSystems(){
  ++draftStructureRevision;draftStructure=null;
  $('draftRegisteredSystems').replaceChildren();$('draftRegisteredSystems').hidden=true;
  $('draftSystems').replaceChildren();$('draftSystems').hidden=true;$('draftAddSystem').hidden=true;
  $('draftCreate').disabled=true;$('draftSystemStatus').textContent='Välj byggnad.';
}
async function loadDraftStructure(){
  resetDraftSystems();
  const revision=draftStructureRevision;
  const project=$('draftProject').value,property=$('draftProperty').value,building=$('draftBuilding').value;
  if(!project||!property||!building)return;
  $('draftSystemStatus').textContent='Laddar registrerade system…';
  try{
    const structure=await api('/api/ovk/projects/'+enc(project)+'/fastighet/'+enc(property)+'/byggnad/'+enc(building)+'/struktur',{cache:'no-store'});
    if(revision!==draftStructureRevision)return;
    if(!Array.isArray(structure.systems)||!Array.isArray(structure.technical_spaces))throw new Error('Ogiltig byggnadsstruktur.');
    draftStructure=structure;
    if(structure.systems.length){
      const container=$('draftRegisteredSystems');container.hidden=false;
      for(const system of structure.systems){
        const row=document.createElement('div');row.className='draft-system';
        const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.className='draft-registered-system';check.style.width='auto';check.value=system.system_id;
        label.append(check,document.createTextNode(' '+system.label+' · '+system.system_type));row.append(label);
        const details=document.createElement('p');details.className='muted';details.textContent=structure.technical_spaces.filter(s=>s.system_id===system.system_id).map(s=>s.label+(s.location?' – '+s.location:'')).join('; ')||'Inga registrerade installationer';row.append(details);container.append(row);
        check.onchange=()=>{$('draftCreate').disabled=!container.querySelector('input:checked')};
      }
      $('draftSystemStatus').textContent='Markera de registrerade system som ska besiktigas.';
    }else{
      $('draftSystems').hidden=false;$('draftAddSystem').hidden=false;draftAddSystem();$('draftCreate').disabled=false;
      $('draftSystemStatus').textContent='Inga registrerade system. Ange system manuellt.';
    }
  }catch(error){if(revision===draftStructureRevision)$('draftSystemStatus').textContent='Kunde inte läsa byggnadsstrukturen: '+error.message;}
}
function draftOptions(select, items, value, label, placeholder) {
  select.replaceChildren(new Option(placeholder, ''));
  for (const item of items) select.add(new Option(label(item), value(item)));
}
function draftBuildingOptions() {
  resetDraftSystems();
  const property = draftProperties.find(p => p.fastighet_id === $('draftProperty').value);
  draftOptions($('draftBuilding'), property?.byggnader || [], b => b.byggnad_id, b => b.internt_namn, 'Välj byggnad');
  $('draftOwner').textContent = property ? [property.byggnadsagare_namn, property.byggnadens_adress?.gata].filter(Boolean).join(' · ') : '';
}
async function draftLoadProperties() {
  const revision = ++draftRevision;
  draftProperties = [];
  draftBuildingOptions();
  draftOptions($('draftProperty'), [], p => p.fastighet_id, p => p.fastighetsbeteckning, 'Välj fastighet');
  $('draftCreate').disabled = true;
  const project = $('draftProject').value;
  if (!project) { $('draftStatus').textContent = 'Välj projekt.'; return; }
  $('draftStatus').textContent = 'Laddar fastigheter…';
  try {
    const data = await api('/api/ovk/projects/' + enc(project) + '/fastighet');
    if (revision !== draftRevision) return;
    draftProperties = data.fastigheter || [];
    draftOptions($('draftProperty'), draftProperties, p => p.fastighet_id, p => p.fastighetsbeteckning, 'Välj fastighet');
    $('draftStatus').textContent = draftProperties.length ? 'Välj fastighet och byggnad.' : 'Inga fastigheter. Registrera en fastighet först.';
    $('draftCreate').disabled = true;
  } catch (error) {
    if (revision === draftRevision) $('draftStatus').textContent = 'Kunde inte läsa fastigheter: ' + error.message;
  }
}
function draftAddSystem() {
  const row = document.createElement('div');
  row.className = 'draft-system';
  row.innerHTML = '<label>Systembeteckning<input class="draft-system-id" required maxlength="80" placeholder="LB01"></label><label>Systemtyp<select class="draft-system-type" required><option value="">Välj typ</option><option>S</option><option>F</option><option>FT</option><option>FTX</option><option>FX</option></select></label><label>Benämning<input class="draft-system-name" maxlength="160" placeholder="Huvudsystem"></label><button type="button" class="button secondary">Ta bort system</button>';
  row.querySelector('button').onclick = () => { if ($('draftSystems').children.length > 1) row.remove(); };
  $('draftSystems').append(row);
}
async function createDraft(event) {
  event.preventDefault();
  const project = $('draftProject').value;
  const property = draftProperties.find(p => p.fastighet_id === $('draftProperty').value);
  const building = property?.byggnader?.find(b => b.byggnad_id === $('draftBuilding').value);
  if (!project || !property || !building) { $('draftStatus').textContent = 'Välj fastighet och byggnad.'; return; }
  if(!draftStructure){$('draftStatus').textContent='Ladda byggnadens system först.';return;}
  const selected=new Set([...$('draftRegisteredSystems').querySelectorAll('input:checked')].map(input=>input.value));
  const systems = draftStructure.systems.length ? draftStructure.systems.filter(s=>selected.has(s.system_id)).map(s=>({system_id:s.system_id,system_type:s.system_type,label:s.label,source_ref:null})) : [...$('draftSystems').children].map(row => {
    const id = row.querySelector('.draft-system-id').value.trim();
    return {system_id:id, system_type:row.querySelector('.draft-system-type').value, label:row.querySelector('.draft-system-name').value.trim() || id, source_ref:null};
  });
  if (!systems.length || systems.some(s => !s.system_id || !s.system_type || /[|\\r\\n]/.test(s.system_id+s.label)) || new Set(systems.map(s=>s.system_id.toLowerCase())).size !== systems.length) {
    $('draftStatus').textContent = 'Ange unika systembeteckningar och systemtyper utan lodstreck.'; return;
  }
  // Keep the same identifier for retries; never reuse a date-based draft ID.
  draftId ||= 'ovk-' + Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2,'0')).join('');
  const address = property.byggnadens_adress || {};
  const payload = {inspection:{inspection_id:draftId,object:{object_id:property.fastighet_id,project_id:project,building_id:building.byggnad_id,name:property.fastighetsbeteckning+' · '+building.internt_namn,address:[address.gata,address.postnr,address.ort].filter(Boolean).join(' ')||null},systems,checkpoints:[],measurements:[],findings:[],actions:[]},review:[],planning:{inspector_id:$('draftInspector').value,planned_date:$('draftDate').value,inspection_type:$('draftType').value}};
  $('draftFields').disabled = true;
  $('draftStatus').textContent = 'Sparar utkast…';
  try {
    await api('/api/ovk/projects/'+enc(project)+'/inspections/'+enc(draftId),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
    location.assign('/ovk/besiktning?'+contextUrl(project,draftId));
  } catch(error) {
    $('draftStatus').textContent = 'Kunde inte spara utkast: '+error.message;
    $('draftFields').disabled = false;
  }
}
async function initDraft(projects, requestedProject) {
  $('guidedDraft').hidden = false;
  document.querySelectorAll('[data-workflow-editor]').forEach(node=>node.hidden=true);
  draftOptions($('draftProject'),projects,p=>p.project_id,p=>p.project_name||p.name||p.project_id,'Välj projekt');
  if(projects.some(p=>p.project_id===requestedProject)) $('draftProject').value=requestedProject;
  $('draftProject').onchange=draftLoadProperties;
  $('draftProperty').onchange=draftBuildingOptions;
  $('draftBuilding').onchange=loadDraftStructure;
  $('draftAddSystem').onclick=draftAddSystem;
  $('draftForm').onsubmit=createDraft;
  const registry = await api('/api/ovk/registry/besiktningsman');
  draftOptions($('draftInspector'),registry.besiktningsman||[],p=>p.besiktningsman_id,p=>p.namn+' · '+p.behorighet+' · '+p.certnummer,'Välj besiktningsman');
  $('draftFields').disabled=false;
  await draftLoadProperties();
}
async function init() {
  try {
    const modules = await api('/api/me/modules');
    if (!(modules.modules || []).some(item => item.id === 'ovk')) throw new Error('OVK ingår inte i licensen.');
    const projects = await api('/api/projects');
    $('project').innerHTML = projects.length ? '' : '<option value="">Inga projekt</option>';
    for (const project of projects) ensureProject(project.project_id, project.project_name || project.name || project.project_id);
    const requestedProject = new URLSearchParams(location.search).get('project_id');
    if (requestedProject && projects.some(project => project.project_id === requestedProject)) $('project').value = requestedProject;
    if (new URLSearchParams(location.search).get('new') === '1') { await initDraft(projects, requestedProject); return; }
    if (projects.length) await loadProject();
    else { $('status').textContent = 'Skapa ett projekt i Workbench först.'; $('save').disabled = true; }
  } catch (error) {
    $('status').className = 'status warn';
    $('status').textContent = 'OVK-besiktning kunde inte starta: ' + error.message;
  }
}
init();
