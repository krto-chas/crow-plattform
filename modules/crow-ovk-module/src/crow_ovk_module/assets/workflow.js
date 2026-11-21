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
let historyRevision=0;
async function loadDraftHistory(){
  const revision=++historyRevision,select=$('draftPrevious');
  select.replaceChildren(new Option('Ingen historisk referens',''));select.disabled=true;
  $('draftHistoryPanel').hidden=$('draftType').value!=='aterkommande';
  $('draftHistoryStatus').textContent='';
  const project=$('draftProject').value,property=$('draftProperty').value,building=$('draftBuilding').value;
  if(!project||!property||!building||$('draftHistoryPanel').hidden)return;
  try{
    const data=await api('/api/ovk/projects/'+enc(project)+'/inspections',{cache:'no-store'});
    if(revision!==historyRevision)return;
    const rows=(data.inspections||[]).filter(r=>r.object_id===property&&r.building_id===building&&r.protocol_ready&&(!r.planning?.planned_date||!$('draftDate').value||r.planning.planned_date<$('draftDate').value));
    rows.sort((a,b)=>(b.planning?.planned_date||b.updated_at||'').localeCompare(a.planning?.planned_date||a.updated_at||''));
    for(const r of rows)select.add(new Option((r.planning?.planned_date||'Datum saknas')+' · '+r.inspection_id,r.inspection_id));
    select.disabled=!rows.length;$('draftHistoryStatus').textContent=rows.length?'Välj tidigare besiktning som referens.':'Ingen tidigare protokollklar besiktning hittades.';
  }catch(error){if(revision===historyRevision)$('draftHistoryStatus').textContent='Historik kunde inte hämtas: '+error.message;}
}
function resetDraftSystems(){
  ++draftStructureRevision;draftStructure=null;
  $('draftRegisteredSystems').replaceChildren();$('draftRegisteredSystems').hidden=true;
  $('draftSystems').replaceChildren();$('draftSystems').hidden=true;$('draftAddSystem').hidden=true;
  $('draftCreate').disabled=true;$('draftSystemStatus').textContent='Välj byggnad.';
}
async function loadDraftStructure(){
  resetDraftSystems();
  void loadDraftHistory();
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
  void loadDraftHistory();
  $('draftOwner').textContent = property ? [property.byggnadsagare_namn, property.byggnadens_adress?.gata].filter(Boolean).join(' · ') : '';
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
  if (!systems.length) { $('draftStatus').textContent = 'Välj minst ett ventilationssystem.'; return; }
  const seenSystemIds = new Set();
  for (const [index, system] of systems.entries()) {
    const identifier = String(system.system_id || '').trim();
    const systemType = String(system.system_type || '').trim();
    const label = String(system.label || '');
    const systemName = identifier || 'System ' + (index + 1);
    if (!identifier) { $('draftStatus').textContent = 'System ' + (index + 1) + ' saknar systembeteckning.'; return; }
    if (!systemType) { $('draftStatus').textContent = systemName + ': välj systemtyp.'; return; }
    if (/[|\r\n]/.test(identifier + label)) { $('draftStatus').textContent = systemName + ': beteckning och benämning får inte innehålla lodstreck eller radbrytningar.'; return; }
    if (seenSystemIds.has(identifier.toLowerCase())) { $('draftStatus').textContent = systemName + ': systembeteckningen används redan.'; return; }
    seenSystemIds.add(identifier.toLowerCase());
  }
  // Keep the same identifier for retries; never reuse a date-based draft ID.
  draftId ||= 'ovk-' + Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2,'0')).join('');
  const address = property.byggnadens_adress || {};
  const payload = {inspection:{inspection_id:draftId,object:{object_id:property.fastighet_id,project_id:project,building_id:building.byggnad_id,name:property.fastighetsbeteckning+' · '+building.internt_namn,address:[address.gata,address.postnr,address.ort].filter(Boolean).join(' ')||null},systems,checkpoints:[],measurements:[],findings:[],actions:[]},review:[],planning:{inspector_id:$('draftInspector').value,planned_date:$('draftDate').value,inspection_type:$('draftType').value,previous_inspection_id:$('draftType').value==='aterkommande'?$('draftPrevious').value||null:null}};
  $('draftFields').disabled = true;
  $('draftStatus').textContent = 'Sparar utkast…';
  try {
    await api('/api/ovk/projects/'+enc(project)+'/inspections/'+enc(draftId),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
    location.assign((matchMedia('(max-width:900px)').matches?'/ovk/falt?':'/ovk/besiktning?')+contextUrl(project,draftId));
  } catch(error) {
    $('draftStatus').textContent = 'Kunde inte spara utkast: '+error.message;
    $('draftFields').disabled = false;
  }
}
// Sök endast i projekt som den befintliga projekt-API:n returnerar för sessionen.
let propertyProjects = [];
let propertySearchRevision = 0;
let searchedDesignation = '';
let searchMatches = [];
let pendingProperty = null;

function normalizeDesignation(value) {
  return value.normalize('NFKC').trim().replace(/\s+/g, ' ').replace(/\s*:\s*/g, ':').toLocaleLowerCase('sv');
}
function randomId(prefix) {
  return prefix + Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
}
function projectLabel(project) {
  return project.project_name || project.name || project.project_id;
}
function resetPropertySearch() {
  ++propertySearchRevision;
  searchedDesignation = '';
  searchMatches = [];
  $('propertyMatches').replaceChildren();
  $('propertyNew').hidden = true;
  $('newPropertyForm').hidden = true;
  $('propertySearchStatus').textContent = '';
}
function chooseProperty(project, property) {
  // En bekräftad befintlig fastighet behåller sitt projekt och sin historik.
  ++propertySearchRevision;
  $('propertySearchFields').disabled = true;
  $('propertyMatches').replaceChildren();
  $('propertyNew').hidden = true;
  $('newPropertyForm').hidden = true;
  $('draftForm').hidden = false;
  $('propertySearchForm').hidden = true;
  $('propertySearchStatus').textContent = '';
  $('selectedPropertyTitle').textContent = property.fastighetsbeteckning;
  const address = property.byggnadens_adress || {};
  $('selectedPropertyContext').textContent = [address.gata, address.ort].filter(Boolean).join(' · ');
  draftOptions($('draftProject'), [project], p=>p.project_id, projectLabel, 'Projekt');
  $('draftProject').value = project.project_id;
  draftProperties = [property];
  draftOptions($('draftProperty'), draftProperties, p=>p.fastighet_id, p=>p.fastighetsbeteckning, 'Fastighet');
  $('draftProperty').value = property.fastighet_id;
  draftBuildingOptions();
  if (property.byggnader?.length === 1) {
    $('draftBuilding').value = property.byggnader[0].byggnad_id;
    void loadDraftStructure();
  }
  $('draftStatus').textContent = !$('draftInspector').options[1] ? 'Ingen besiktningsman registrerad. Registrera en besiktningsman innan besiktningen kan sparas.' : property.byggnader?.length ? 'Komplettera besiktningsuppgifterna.' : 'Fastigheten saknar byggnad. Komplettera fastigheten innan besiktning.';
  $('draftBuilding').focus();
}
async function searchProperties(event) {
  event.preventDefault();
  resetPropertySearch();
  const designation = $('propertyDesignation').value.trim();
  if (!designation) return;
  const revision = propertySearchRevision;
  searchedDesignation = designation;
  $('propertySearchStatus').textContent = 'Söker fastighet…';
  const rows = [];
  let failures = 0;
  for (let i=0; i<propertyProjects.length; i+=5) {
    const batch = propertyProjects.slice(i, i+5);
    const results = await Promise.allSettled(batch.map(async project => {
      const data = await api('/api/ovk/projects/'+enc(project.project_id)+'/fastighet', {cache:'no-store'});
      if (!Array.isArray(data.fastigheter) || data.fastigheter.some(p=>p.project_id!==project.project_id || typeof p.fastighetsbeteckning!=='string' || !p.fastighet_id)) throw new Error('Ogiltigt fastighetsregister.');
      return data.fastigheter.filter(p=>normalizeDesignation(p.fastighetsbeteckning)===normalizeDesignation(designation)).map(property=>({project,property}));
    }));
    if (revision !== propertySearchRevision) return;
    for (const result of results) {
      if (result.status === 'fulfilled') rows.push(...result.value);
      else failures++;
    }
  }
  if (revision !== propertySearchRevision) return;
  searchMatches = rows;
  for (const {project,property} of rows) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'result-card';
    const title = document.createElement('strong');
    title.textContent = property.fastighetsbeteckning;
    const meta = document.createElement('span');
    const address = property.byggnadens_adress || {};
    meta.textContent = [address.gata, address.ort, projectLabel(project)].filter(Boolean).join(' · ');
    const action = document.createElement('span');
    action.textContent = 'Ny besiktning på denna fastighet';
    button.append(title, meta, action);
    button.onclick = ()=>chooseProperty(project,property);
    $('propertyMatches').append(button);
  }
  if (failures) {
    $('propertySearchStatus').textContent = 'Sökningen är ofullständig. Välj en verifierad träff eller sök igen. Ny fastighet kan inte registreras innan alla register har lästs.';
    return;
  }
  $('propertySearchStatus').textContent = rows.length ? 'Vi hittade tidigare registrerad fastighet. Bekräfta rätt fastighet eller registrera en annan.' : 'Ingen registrerad fastighet med den beteckningen hittades.';
  $('propertyNew').textContent = rows.length ? 'Registrera annan fastighet' : 'Registrera ny fastighet';
  $('propertyNew').hidden = false;
}
function showNewProperty() {
  if (!searchedDesignation) return;
  $('newPropertyNote').textContent = searchMatches.length ? 'Kontrollera att det verkligen är en annan fastighet. Befintliga fastigheter ska återanvändas.' : searchedDesignation;
  $('newPropertyForm').hidden = false;
  $('newPropertyOrt').focus();
}
async function getOrCreateProject(request) {
  if (request.existingProject) {
    const data = await api('/api/projects/'+enc(request.existingProject.project_id), {cache:'no-store'});
    if (!data.summary || data.summary.project_id!==request.existingProject.project_id) throw new Error('Valt projekt kunde inte verifieras.');
    return data.summary;
  }
  const id = request.projectId;
  try {
    const created = await api('/api/projects', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:request.designation,project_id:id})});
    if (created.project_id!==id || projectLabel(created)!==request.designation) throw new Error('Projektidentiteten stämmer inte.');
    return created;
  } catch (error) {
    // Samma slumpade ID vid omförsök i samma sidflöde. Bekräfta att en eventuell tidigare
    // lyckad skrivning verkligen avser vårt projekt, annars stoppa.
    const data = await api('/api/projects/'+enc(id), {cache:'no-store'});
    const summary = data.summary;
    if (!summary || summary.project_id!==id || projectLabel(summary)!==request.designation) throw error;
    return summary;
  }
}
async function saveNewProperty(event) {
  event.preventDefault();
  if (!pendingProperty) {
    const designation = searchedDesignation;
    const ort = $('newPropertyOrt').value.trim();
    const gata = $('newPropertyAddress').value.trim();
    const type = $('newPropertyType').value;
    const buildingName = $('newPropertyBuilding').value.trim();
    const existingProject = propertyProjects.find(p=>p.project_id===$('newPropertyProject').value);
    if (!designation || !ort || !type) return;
    if (searchMatches.length && !confirm('Registrera en annan fastighet med samma beteckning? Kontrollera tidigare träffar och ort.')) return;
    pendingProperty = {designation,ort,gata,type,buildingName:buildingName || 'Byggnad',existingProject,projectId:existingProject?.project_id||randomId('project-'),propertyId:randomId('property-'),buildingId:randomId('building-')};
  }
  const request = pendingProperty;
  $('propertySearchFields').disabled = true;
  $('newPropertyFields').disabled = true;
  $('newPropertySave').disabled = true;
  $('propertyNew').hidden = true;
  $('propertyMatches').replaceChildren();
  $('propertySearchStatus').textContent = 'Sparar fastighet…';
  try {
    const project = await getOrCreateProject(request);
    const url = '/api/ovk/projects/'+enc(project.project_id)+'/fastighet/'+enc(request.propertyId);
    const response = await fetch(url,{cache:'no-store'});
    let property;
    if (response.ok) {
      property = await response.json();
    } else if (response.status === 404) {
      const missing = await response.json();
      if (missing.detail?.code !== 'FASTIGHET_NOT_FOUND') throw new Error('Fastigheten kunde inte verifieras.');
      const result = await api(url,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({fastighetsbeteckning:request.designation,byggnadens_adress:{gata:request.gata,ort:request.ort},fastighetstyp:request.type,byggnader:[{byggnad_id:request.buildingId,internt_namn:request.buildingName}]})});
      property = result.fastighet;
    } else {
      throw new Error('Fastighetsregistret kunde inte läsas.');
    }
    if (!property || property.project_id!==project.project_id || property.fastighet_id!==request.propertyId || property.fastighetsbeteckning!==request.designation || !property.byggnader?.some(b=>b.byggnad_id===request.buildingId)) throw new Error('Fastighetsidentiteten stämmer inte.');
    if (!propertyProjects.some(p=>p.project_id===project.project_id)) propertyProjects.push(project);
    pendingProperty = null;
    chooseProperty(project,property);
  } catch(error) {
    $('propertySearchStatus').textContent = 'Kunde inte slutföra registreringen. Försök igen med samma uppgifter. Ett projekt kan redan ha skapats. '+error.message;
  } finally {
    $('newPropertySave').disabled = false;
  }
}
async function initDraft(projects, requestedProject) {
  $('guidedDraft').hidden = false;
  document.querySelectorAll('[data-workflow-editor]').forEach(node=>node.hidden=true);
  propertyProjects = projects;
  draftOptions($('newPropertyProject'),projects,p=>p.project_id,projectLabel,'Skapa automatiskt');
  // Projektet förväljs inte från översiktens projektväljare: utan aktivt val skapas ett
  // projekt med fastighetsbeteckningen som namn.
  $('propertySearchForm').onsubmit=searchProperties;
  $('propertyDesignation').oninput=resetPropertySearch;
  $('propertyNew').onclick=showNewProperty;
  $('newPropertyForm').onsubmit=saveNewProperty;
  $('draftBuilding').onchange=loadDraftStructure;
  $('draftType').onchange=loadDraftHistory;
  $('draftDate').onchange=loadDraftHistory;
  $('draftAddSystem').onclick=draftAddSystem;
  $('draftForm').onsubmit=createDraft;
  const today=new Date();
  if(matchMedia('(max-width:900px)').matches) $('draftCreate').textContent='Starta besiktning';
  $('draftDate').value=[today.getFullYear(),String(today.getMonth()+1).padStart(2,'0'),String(today.getDate()).padStart(2,'0')].join('-');
  const registry = await api('/api/ovk/registry/besiktningsman');
  draftOptions($('draftInspector'),registry.besiktningsman||[],p=>p.besiktningsman_id,p=>p.namn+' · '+p.behorighet+' · '+p.certnummer,'Välj besiktningsman');
  $('draftFields').disabled=false;
  $('propertySearchFields').disabled=false;
  $('draftStatus').textContent = registry.besiktningsman?.length ? 'Sök fastigheten för att börja.' : 'Ingen besiktningsman registrerad. Registrera en besiktningsman innan besiktningen kan sparas.';
  await openRequestedProperty(projects, requestedProject);
}
// Fastighetsregistret länkar hit med en utpekad fastighet. Den väljs då direkt,
// på samma sätt som när användaren bekräftar en sökträff.
async function openRequestedProperty(projects, requestedProject) {
  const propertyId = new URLSearchParams(location.search).get('fastighet_id');
  const project = projects.find(item => item.project_id === requestedProject);
  if (!propertyId || !project) return;
  try {
    const property = await api('/api/ovk/projects/'+enc(project.project_id)+'/fastighet/'+enc(propertyId), {cache:'no-store'});
    if (property.project_id !== project.project_id || property.fastighet_id !== propertyId || typeof property.fastighetsbeteckning !== 'string') throw new Error('Ogiltig fastighet.');
    chooseProperty(project, property);
  } catch (error) {
    $('propertySearchStatus').textContent = 'Fastigheten kunde inte öppnas. Sök den i stället.';
  }
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
    $('draftStatus').textContent = 'Kunde inte starta ny besiktning: ' + error.message;
  }
}
init();
