const $ = id => document.getElementById(id);
const DB_NAME = 'crow-ovk-field';
const DB_VERSION = 3;
const scopedField = (projectId,inspectionId) => '/api/ovk/projects/'+encodeURIComponent(projectId)+'/field/'+encodeURIComponent(inspectionId);
const fieldEndpoint = (kind,projectId,inspectionId) => scopedField(projectId,inspectionId)+'/'+kind;
const DRAFT_STORE = 'drafts_v3';
const MEDIA_STORE = 'media_v3';
const draftKey = (projectId,inspectionId) => [projectId,inspectionId];
const mediaKey = (projectId,inspectionId,photoId) => [projectId,inspectionId,photoId];
const uid = prefix => prefix + '-' + crypto.randomUUID();
const now = () => new Date().toISOString();
const ROOMS = ['Kök', 'Badrum', 'WC', 'Klädkammare', 'Sovrum', 'Vardagsrum', 'Hall'];
const ROOMS_COMMERCIAL = ['Kontor', 'Vilorum', 'HWC', 'WC', 'Kök', 'Korridor'];
function isCommercial(){const unit=activeUnit();return unit ? unit.kind==='premises' : (state.object_type==='kontorsbyggnad'||state.object_type==='industrifastighet')}
function roomPresets(){return isCommercial()?ROOMS_COMMERCIAL:ROOMS}
const DEFAULT_STATE = () => ({project_id: 'adhoc', inspection_id: '', inspector: '', system_type: 'F', object_type: 'flerbostadshus', assignment_name: '',
  previous_inspection_id: null, historical_findings: [], historical_measurements: [], historical_checkpoints: [], historical_space_photos: [], history_unavailable:false, units: [], rooms: [], findings: [], finding_followups: [], photos: [],
  measurements: [], window_vents: [], technical_spaces: [], checkpoints: [], dirty: false, last_sync: null,
  activeUnitId: null, activeRoomId: null, activeFindingId: null, activeSpaceId: null, defects: [], checklists: {}});
let state = DEFAULT_STATE();

function openDb(){return new Promise((resolve,reject)=>{const req=indexedDB.open(DB_NAME,DB_VERSION);req.onupgradeneeded=()=>{const db=req.result;if(!db.objectStoreNames.contains('drafts'))db.createObjectStore('drafts',{keyPath:'inspection_id'});if(!db.objectStoreNames.contains('media'))db.createObjectStore('media',{keyPath:'photo_id'});if(!db.objectStoreNames.contains('meta'))db.createObjectStore('meta',{keyPath:'key'});if(!db.objectStoreNames.contains(DRAFT_STORE)){const drafts=db.createObjectStore(DRAFT_STORE,{keyPath:['project_id','inspection_id']});const media=db.createObjectStore(MEDIA_STORE,{keyPath:['project_id','inspection_id','photo_id']});const tx=req.transaction;const oldDrafts=tx.objectStore('drafts');const oldMedia=tx.objectStore('media');const cursor=oldDrafts.openCursor();cursor.onsuccess=()=>{const row=cursor.result;if(!row)return;const draft=row.value;if(typeof draft.project_id==='string'&&draft.project_id&&typeof draft.inspection_id==='string'&&draft.inspection_id){drafts.add(draft);for(const photo of draft.photos||[]){const lookup=oldMedia.get(photo.photo_id);lookup.onsuccess=()=>{const blob=lookup.result;if(blob&&blob.inspection_id===draft.inspection_id&&blob.sha256===photo.sha256&&(!blob.project_id||blob.project_id===draft.project_id))media.add({...blob,project_id:draft.project_id})}}}row.continue()}}};req.onsuccess=()=>{req.result.onversionchange=()=>req.result.close();resolve(req.result)};req.onblocked=()=>reject(new Error('Stäng andra OVK-flikar och ladda om.'));req.onerror=()=>reject(req.error)})}
async function dbPut(store,value){const db=await openDb();await new Promise((resolve,reject)=>{const tx=db.transaction(store,'readwrite');tx.objectStore(store).put(value);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error)});db.close()}
async function dbGet(store,key){const db=await openDb();const value=await new Promise((resolve,reject)=>{const req=db.transaction(store,'readonly').objectStore(store).get(key);req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});db.close();return value}
async function dbGetAll(store){const db=await openDb();const values=await new Promise((resolve,reject)=>{const req=db.transaction(store,'readonly').objectStore(store).getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)});db.close();return values}

function payload(){return {inspection_id:state.inspection_id,object_type:state.object_type,
  units:state.units.map(({unit_id,number,kind,label,status,checked_at,bom_at,bom_note,key,system_type})=>({unit_id,number,kind,label,status,checked_at,bom_at,bom_note,key,system_type:system_type||null})),
  rooms:state.rooms,
  findings:state.findings.map(({unit_number,room_name,...item})=>item),
  finding_followups:state.finding_followups,
  photos:state.photos,
  measurements:state.measurements,
  window_vents:state.window_vents,
  technical_spaces:state.technical_spaces,
  checkpoints:state.checkpoints}}
async function writeDraft(dirty){if(!state.inspection_id||!state.project_id)return;state.dirty=dirty;await dbPut(DRAFT_STORE,{...payload(),project_id:state.project_id,inspector:state.inspector,system_type:state.system_type,assignment_name:state.assignment_name,previous_inspection_id:state.previous_inspection_id,historical_findings:state.historical_findings,historical_measurements:state.historical_measurements,history_unavailable:state.history_unavailable||false,historical_checkpoints:state.historical_checkpoints,historical_space_photos:state.historical_space_photos,findings:state.findings,dirty:state.dirty,last_sync:state.last_sync,updated_at:now()})}
async function persist(){await writeDraft(true);$('draftStatus').textContent='Lokalt sparad · '+new Date().toLocaleTimeString()}

function ensureProject(id){if(!id)return;if(![...$('project').options].some(o=>o.value===id)){const option=document.createElement('option');option.value=id;option.textContent=id;$('project').appendChild(option)}}
function esc(value){const div=document.createElement('div');div.textContent=value||'';return div.innerHTML}
function crowErrorText(error){const text=error&&error.message?error.message:String(error);try{const data=JSON.parse(text);const detail=data.detail||data;const code=detail.code||'';const message=detail.message||'';if(code||message)return (code?code+' · ':'')+(message||'Servern avvisade anropet.')}catch(_){/* inte JSON */}return text}
function view(name){for(const el of document.querySelectorAll('.view'))el.classList.remove('on');$(name).classList.add('on');$('syncCard').classList.toggle('hidden',name==='viewStart');updateFooter(name)}
function activeUnit(){return state.units.find(item=>item.unit_id===state.activeUnitId)||null}
function activeRoom(){return state.rooms.find(item=>item.room_id===state.activeRoomId)||null}
function unitRemarks(unitId){return state.findings.filter(item=>item.unit_id===unitId&&(item.severity==='minor'||item.severity==='major'))}
function unitSystem(unit){return (unit&&unit.system_type)||state.system_type}
function isFtx(){const sys=unitSystem(activeUnit());return sys==='FT'||sys==='FTX'}

/* ---------- serie & lista ---------- */
function parseSeries(text){const numbers=[];for(const part of text.split(',').map(item=>item.trim()).filter(Boolean)){const range=part.match(/^(\d{1,6})\s*-\s*(\d{1,6})$/);if(range){const start=parseInt(range[1],10),end=parseInt(range[2],10);if(end<start||end-start>500)throw new Error('Ogiltigt intervall: '+part);for(let value=start;value<=end;value++)numbers.push(String(value).padStart(range[1].length,'0'))}else if(/^\d{1,6}$/.test(part)){numbers.push(part)}else{throw new Error('Ogiltigt nummer: '+part)}}return [...new Set(numbers)]}
function generateUnits(){const text=$('unitSeries').value.trim();if(!text){$('draftStatus').textContent='Ange en nummerserie först.';return}let numbers;try{numbers=parseSeries(text)}catch(error){$('draftStatus').className='status warn';$('draftStatus').textContent=String(error.message||error);return}const existing=new Set(state.units.map(item=>item.number));let added=0;for(const number of numbers){if(existing.has(number))continue;state.units.push({unit_id:uid('unit'),inspection_id:state.inspection_id||$('inspection').value.trim(),number,kind:'apartment',label:'',status:'ej_paborjad',checked_at:null,bom_at:null,bom_note:'',key:null,system_type:null});added+=1}$('draftStatus').className='status pass';$('draftStatus').textContent=added+' enheter tillagda · totalt '+state.units.length}

function validFlowValue(value){
  if(value==null)return false;
  const text=String(value).trim().replace(',','.');
  return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text)&&Number.isFinite(Number(text));
}
function measuredPoint(point){return point.measurable!==false&&validFlowValue(point.measured_value)}
function pendingPoint(point){return point.measurable!==false&&!measuredPoint(point)}
function checkedUnit(unit){return unit.status==='ua'||unit.status==='anmarkning'}
function roundCounts(){
  return {total:state.units.length,checked:state.units.filter(checkedUnit).length,pending:state.units.filter(u=>u.status==='ej_paborjad').length,bom:state.units.filter(u=>u.status==='bom').length,measured:state.measurements.filter(measuredPoint).length,pendingMeasurements:state.measurements.filter(pendingPoint).length};
}
function nextPendingUnit(afterId=null){
  const index=state.units.findIndex(u=>u.unit_id===afterId);
  const ordered=index<0?state.units:[...state.units.slice(index+1),...state.units.slice(0,index)];
  return ordered.find(u=>u.status==='ej_paborjad')||null;
}
function visibleRoundUnits(search='',filter='all'){
  const query=search.trim().toLocaleLowerCase('sv');
  return state.units.filter(unit=>{
    const match=filter==='all'||(filter==='pending'&&unit.status==='ej_paborjad')||(filter==='checked'&&checkedUnit(unit))||(filter==='bom'&&unit.status==='bom');
    return match&&[unit.number,unit.label,unit.kind==='premises'?'Lokal':'Lägenhet'].some(v=>String(v||'').toLocaleLowerCase('sv').includes(query));
  });
}
function renderRoundUnits(){
  const rows=visibleRoundUnits($('unitSearch')?.value||'',$('unitFilter')?.value||'all');
  const list=$('unitList');list.replaceChildren();
  for(const unit of rows){
    const remarks=unitRemarks(unit.unit_id).length;
    const points=state.measurements.filter(m=>m.unit_id===unit.unit_id);
    const button=document.createElement('button');button.type='button';button.className='unitrow '+unit.status;button.dataset.unit=unit.unit_id;
    const number=document.createElement('span');number.className='nr';number.textContent=unit.number;
    const meta=document.createElement('span');meta.className='sub';
    meta.textContent=(unit.kind==='premises'?'Lokal':'Lgh')+(points.length?' · '+points.filter(measuredPoint).length+'/'+points.length+' uppmätta':'')+(unit.key?.received&&!unit.key.returned?' · Nyckel ute':'');
    const status=document.createElement('span');status.className='tag '+unit.status;
    status.textContent={ej_paborjad:'Ej klar',ua:'UA',anmarkning:remarks+' anm.',bom:'BOM'}[unit.status]||'Okänd status';
    button.append(number,meta,status);button.onclick=()=>openUnit(unit.unit_id);list.append(button);
  }
  if($('unitEmpty')){
    $('unitEmpty').hidden=rows.length>0;
    $('unitEmpty').textContent=state.units.length?'Inga enheter matchar sökningen eller filtret.':'Inga enheter ännu. Lägg till lägenheter eller lokaler.';
  }
}
function renderRond(){
  const counts=roundCounts();
  $('rondMeta').textContent=(state.assignment_name||state.inspection_id)+' · '+state.system_type;
  $('cDone').textContent=counts.checked;$('cTotal').textContent=counts.total;
  $('cAnm').textContent=state.units.filter(u=>u.status==='anmarkning').length;
  $('cBom').textContent=counts.bom;$('cMeas').textContent=counts.measured;
  $('rondbar').replaceChildren(...state.units.map(unit=>{const segment=document.createElement('i');segment.className=unit.status;return segment}));
  if($('roundSummary'))$('roundSummary').textContent=counts.pending+' ej färdiga · '+counts.bom+' BOM · '+counts.pendingMeasurements+' mätpunkter utan giltigt värde';
  if($('continueUnit')){
    const next=nextPendingUnit();
    $('continueUnit').hidden=!next;
    $('continueUnit').textContent=next?'Fortsätt med '+(next.kind==='premises'?'lokal ':'lgh ')+next.number:'Fortsätt med nästa enhet';
    $('continueUnit').onclick=()=>{const target=nextPendingUnit();if(target)openUnit(target.unit_id)};
  }
  renderRoundUnits();renderSpaces();
}
if($('unitSearch'))$('unitSearch').oninput=renderRoundUnits;
if($('unitFilter'))$('unitFilter').onchange=renderRoundUnits;

/* ---------- enhetsvyn ---------- */
function openUnit(unitId){
  const unit=state.units.find(item=>item.unit_id===unitId);if(!unit)return;
  state.activeUnitId=unitId;state.activeFindingId=null;
  $('fieldTemplateStatus').textContent='';
  const rooms=unitRooms();
  const pending=rooms.find(room=>state.measurements.some(point=>point.unit_id===unitId&&point.room_id===room.room_id&&pendingPoint(point)));
  state.activeRoomId=(pending||rooms[0])?.room_id||null;
  $('unitNr').textContent=unit.number;$('unitKindLabel').textContent=unit.kind==='premises'?'Lokal':'Lägenhet';
  $('photoStatus').className='status';$('photoStatus').textContent='Välj eller registrera en anmärkning innan du tar foto.';
  renderUnit();view('viewUnit');window.scrollTo(0,0);$('unitNr').focus({preventScroll:true});
}
function unitRooms(){return state.rooms.filter(item=>item.unit_id===state.activeUnitId)}

/* ---------- lägenhetsmallar i samma fältutkast ---------- */
let fieldTemplateBusy=false;
function apartmentSuffix(unit){
  const number=String(unit?.number||'').trim();
  return unit?.kind==='apartment'&&/^\d{4}$/.test(number)&&number.slice(-2)!=='00'?number.slice(-2):null;
}
function fieldTemplateEligible(target){
  if(!state.project_id||!state.inspection_id||!apartmentSuffix(target)||target.status!=='ej_paborjad')return false;
  return ![state.rooms,state.measurements,state.findings,state.finding_followups,state.photos,state.window_vents].some(rows=>rows.some(row=>row.unit_id===target.unit_id));
}
function fieldTemplatePlan(sourceId,targetId){
  const source=state.units.find(u=>u.unit_id===sourceId);
  const target=state.units.find(u=>u.unit_id===targetId);
  if(!fieldTemplateEligible(target)||!source||source===target||source.status==='bom'||apartmentSuffix(source)!==apartmentSuffix(target)||unitSystem(source)!==unitSystem(target))throw new Error('Lägenheterna är inte lämpliga för denna mall.');
  for(const unit of [source,target]){
    if(state.units.filter(u=>String(u.number).trim()===String(unit.number).trim()).length!==1)throw new Error('Lägenhetsnumret är inte entydigt.');
  }
  const sourceRooms=state.rooms.filter(r=>r.unit_id===sourceId);
  const sourcePoints=state.measurements.filter(p=>p.unit_id===sourceId);
  const roomIds=new Set(),pointIds=new Set();
  if(!sourceRooms.length)throw new Error('Referenslägenheten saknar rum.');
  const rooms=sourceRooms.map(room=>{
    if(!room.room_id||roomIds.has(room.room_id)||typeof room.name!=='string'||!room.name.trim())throw new Error('Ogiltig rumsstruktur i referenslägenheten.');
    roomIds.add(room.room_id);
    const points=sourcePoints.filter(p=>p.room_id===room.room_id).map(point=>{
      if(!point.measurement_id||pointIds.has(point.measurement_id)||!['franluftsdon','tilluftsdon','overluftsdon'].includes(point.point_type)||typeof point.point_label!=='string'||!point.point_label.trim()||point.unit_of_measure!=='l/s')throw new Error('Ogiltig mätpunkt i referenslägenheten.');
      if(point.point_type==='tilluftsdon'&&!['FT','FTX'].includes(unitSystem(target)))throw new Error('Referenslägenhetens tilluft stämmer inte med systemtypen.');
      const design=point.designed_value==null?null:String(point.designed_value);
      if(design!==null&&(!/^\d+(?:\.\d+)?$/.test(design)||!Number.isFinite(Number(design))))throw new Error('Ogiltigt projekterat flöde i referenslägenheten.');
      if(point.system_id!=null&&(typeof point.system_id!=='string'||!point.system_id.trim()))throw new Error('Ogiltig systemkoppling i referenslägenheten.');
      pointIds.add(point.measurement_id);
      return {source_id:point.measurement_id,point_type:point.point_type,point_label:point.point_label,system_id:point.system_id??null,designed_value:design,unit_of_measure:'l/s'};
    });
    return {source_id:room.room_id,name:room.name,points};
  });
  if(pointIds.size!==sourcePoints.length)throw new Error('Referenslägenheten har don utan säker rumskoppling.');
  return {project_id:state.project_id,inspection_id:state.inspection_id,source_id:sourceId,target_id:targetId,source_number:source.number,target_number:target.number,system_type:unitSystem(target),rooms};
}
function fieldTemplateCandidates(target){
  if(!fieldTemplateEligible(target))return [];
  return state.units.filter(source=>{
    try{fieldTemplatePlan(source.unit_id,target.unit_id);return true}catch(_){return false}
  }).sort((a,b)=>Math.abs(Number(a.number)-Number(target.number))-Math.abs(Number(b.number)-Number(target.number))||String(a.number).localeCompare(String(b.number)));
}
function fieldTemplateCopy(plan,roomIds,pointIds){
  const rooms=[],measurements=[];
  for(const room of plan.rooms){
    if(!roomIds.has(room.source_id))continue;
    const roomId=uid('room');
    rooms.push({room_id:roomId,unit_id:plan.target_id,name:room.name});
    for(const point of room.points){
      if(!pointIds.has(point.source_id))continue;
      measurements.push({measurement_id:uid('meas'),unit_id:plan.target_id,room_id:roomId,point_type:point.point_type,point_label:point.point_label,system_id:point.system_id,designed_value:point.designed_value,unit_of_measure:'l/s',measurable:true,measured_value:null,not_measurable_reason:'',finding_id:null});
    }
  }
  return {rooms,measurements};
}
function renderFieldTemplate(){
  const panel=$('fieldTemplatePanel'),source=$('fieldTemplateSource'),preview=$('fieldTemplatePreview'),confirmation=$('fieldTemplateConfirm'),apply=$('fieldTemplateApply');
  const target=activeUnit(),candidates=fieldTemplateCandidates(target);
  panel.classList.toggle('hidden',!candidates.length);
  preview.replaceChildren();source.replaceChildren();confirmation.checked=false;apply.disabled=true;
  apply.onclick=null;source.onchange=null;confirmation.onchange=null;
  if(!candidates.length)return;
  for(const candidate of candidates)source.add(new Option(candidate.number+' · '+unitSystem(candidate),candidate.unit_id));
  source.value=candidates[0].unit_id;
  function renderPreview(){
    confirmation.checked=false;apply.disabled=true;preview.replaceChildren();
    const plan=fieldTemplatePlan(source.value,target.unit_id);
    const roomIds=new Set(plan.rooms.map(room=>room.source_id)),pointIds=new Set(plan.rooms.flatMap(room=>room.points.map(point=>point.source_id)));
    const summary=document.createElement('p');summary.className='template-summary';summary.setAttribute('role','status');
    const refresh=()=>{
      const count=plan.rooms.filter(r=>roomIds.has(r.source_id)).reduce((total,r)=>total+r.points.filter(p=>pointIds.has(p.source_id)).length,0);
      summary.textContent=roomIds.size+' rum · '+count+' don · inga tidigare kontrollresultat';
      apply.disabled=fieldTemplateBusy||!confirmation.checked||!roomIds.size;
    };
    const change=()=>{confirmation.checked=false;refresh()};
    for(const room of plan.rooms){
      const card=document.createElement('div');card.className='template-room';
      const label=document.createElement('label');label.className='template-check';
      const check=document.createElement('input');check.type='checkbox';check.checked=true;
      const name=document.createElement('strong');name.textContent=room.name;label.append(check,name);card.append(label);
      const pointChecks=[];
      for(const point of room.points){
        const line=document.createElement('label');line.className='template-check template-point';
        const input=document.createElement('input');input.type='checkbox';input.checked=true;pointChecks.push(input);
        const detail=document.createElement('span');detail.textContent=point.point_label+' · '+({franluftsdon:'Frånluft',tilluftsdon:'Tilluft',overluftsdon:'Överluft'}[point.point_type]);
        const sub=document.createElement('small');sub.textContent=(point.system_id?'System '+point.system_id:'Systemkoppling saknas')+' · '+(point.designed_value==null?'Projekterat värde saknas':point.designed_value+' l/s projekterat');
        detail.append(sub);line.append(input,detail);card.append(line);
        input.onchange=()=>{if(input.checked)pointIds.add(point.source_id);else pointIds.delete(point.source_id);change()};
      }
      check.onchange=()=>{if(check.checked)roomIds.add(room.source_id);else roomIds.delete(room.source_id);for(const input of pointChecks)input.disabled=!check.checked;change()};
      preview.append(card);
    }
    preview.append(summary);confirmation.onchange=refresh;
    apply.onclick=async()=>{
      if(fieldTemplateBusy||!confirmation.checked||!roomIds.size)return;
      let current;
      try{current=fieldTemplatePlan(source.value,target.unit_id);if(state.activeUnitId!==target.unit_id||JSON.stringify(current)!==JSON.stringify(plan))throw new Error('Underlaget har ändrats. Granska mallen igen.')}
      catch(error){renderFieldTemplate();$('fieldTemplateStatus').textContent=crowErrorText(error);return}
      const copy=fieldTemplateCopy(current,roomIds,pointIds);
      await applyFieldTemplate(current,copy);
    };
    refresh();
  }
  source.onchange=renderPreview;
  renderPreview();
}
async function applyFieldTemplate(plan,copy){
  if(fieldTemplateBusy||state.activeUnitId!==plan.target_id||!fieldTemplateEligible(activeUnit())||state.project_id!==plan.project_id||state.inspection_id!==plan.inspection_id||!copy.rooms.length)return;
  fieldTemplateBusy=true;
  const controls=[...document.querySelectorAll('#viewUnit button,#viewUnit input,#viewUnit select,#viewUnit textarea,#syncCard button,#footBack,#footDone')].map(element=>({element,disabled:element.disabled}));
  for(const {element} of controls)element.disabled=true;
  const previousRoom=state.activeRoomId;
  const roomIds=new Set(copy.rooms.map(room=>room.room_id)),pointIds=new Set(copy.measurements.map(point=>point.measurement_id));
  const sameContext=()=>state.project_id===plan.project_id&&state.inspection_id===plan.inspection_id;
  let message='';
  try{
    state.rooms.push(...copy.rooms);state.measurements.push(...copy.measurements);
    state.activeRoomId=(copy.rooms.find(room=>copy.measurements.some(point=>point.room_id===room.room_id))||copy.rooms[0]).room_id;
    clearFindingSelection();
    try{await persist();message=copy.rooms.length+' rum och '+copy.measurements.length+' don sparade lokalt. Kontrollera strukturen och börja mäta.'}
    catch(error){
      if(sameContext()){
        state.rooms=state.rooms.filter(room=>!roomIds.has(room.room_id));
        state.measurements=state.measurements.filter(point=>!pointIds.has(point.measurement_id));
        if(state.activeUnitId===plan.target_id)state.activeRoomId=previousRoom;
      }
      message='Mallen kunde inte sparas lokalt. Försök igen: '+crowErrorText(error);
    }
  }finally{
    fieldTemplateBusy=false;
    for(const {element,disabled} of controls)element.disabled=disabled;
    if(sameContext()&&state.activeUnitId===plan.target_id&&document.querySelector('.view.on')?.id==='viewUnit'){
      renderUnit();$('fieldTemplateStatus').textContent=message;
    }
  }
}

const PRESET_EXTRACT_ROOMS=['badrum','wc','kök','hwc','vilorum'];
function ensureRoom(name){const existing=unitRooms().find(item=>item.name===name);if(existing)return existing;const room={room_id:uid('room'),unit_id:state.activeUnitId,name};state.rooms.push(room);if(PRESET_EXTRACT_ROOMS.includes(name.trim().toLowerCase().split(/\s+/)[0])){state.measurements.push({measurement_id:uid('meas'),unit_id:state.activeUnitId,point_type:'franluftsdon',point_label:name+' 1',room_id:room.room_id,measurable:true,measured_value:null,designed_value:null,unit_of_measure:'l/s',not_measurable_reason:'',finding_id:null})}return room}
function roomStats(roomId){
  const points=state.measurements.filter(item=>item.unit_id===state.activeUnitId&&item.room_id===roomId);
  return {meas:points.length,measured:points.filter(measuredPoint).length,marks:state.findings.filter(item=>item.unit_id===state.activeUnitId&&item.room_id===roomId&&(item.severity==='minor'||item.severity==='major')).length};
}
function updateUnitProgress(){
  const unit=activeUnit();const target=$('unitProgress');if(!unit||!target)return;
  const points=state.measurements.filter(item=>item.unit_id===unit.unit_id);
  const pending=points.filter(pendingPoint).length;
  const position=state.units.findIndex(item=>item.unit_id===unit.unit_id)+1;
  target.textContent='Enhet '+position+' av '+state.units.length+' · '+unitRooms().length+' registrerade rum · '+pending+' mätpunkter utan giltigt värde';
}
const REPEATABLE_ROOMS = new Set(['Sovrum', 'Badrum', 'WC']);
function nextPresetRoomName(base, rooms){
  const names=new Set(rooms.map(room=>room.name));
  if(!names.has(base))return base;
  let index=2;
  while(names.has(base+' '+index))index++;
  return base+' '+index;
}
function renderRooms(){
  const registered=unitRooms();
  const entries=[...registered.map(room=>({name:room.name,id:room.room_id})),...roomPresets().filter(name=>REPEATABLE_ROOMS.has(name)||!registered.some(room=>room.name===name)).map(name=>({name,id:''}))];
  $('roomChips').replaceChildren();
  const presets=$('roomPresetChips')||$('roomChips');
  if(presets!==$('roomChips'))presets.replaceChildren();
  if($('roomPresetLabel'))$('roomPresetLabel').textContent='Lägg till rum';
  for(const entry of entries){
    const button=document.createElement('button');button.type='button';button.className='chip'+(entry.id&&entry.id===state.activeRoomId?' on':'');
    const stats=entry.id?roomStats(entry.id):null;
    button.textContent=entry.name+(stats&&(stats.meas||stats.marks)?' · '+stats.measured+'/'+stats.meas+' uppm. · '+stats.marks+' anm.':'');
    if(entry.id)button.setAttribute('aria-pressed',String(entry.id===state.activeRoomId));
    else button.textContent='+ '+entry.name;
    button.onclick=async()=>{
      let name=entry.id?entry.name:(REPEATABLE_ROOMS.has(entry.name)?nextPresetRoomName(entry.name,unitRooms()):entry.name);
      if(!entry.id&&isCommercial()){const nr=(prompt('Rumsnr för '+name+' (valfritt):')||'').trim();if(nr)name+=' '+nr}
      state.activeRoomId=entry.id||ensureRoom(name).room_id;clearFindingSelection();renderUnit();await persist();
    };
    (entry.id?$('roomChips'):presets).append(button);
  }
  const add=document.createElement('button');add.type='button';add.className='chip';add.textContent='+ Rum/rumsnr';
  add.onclick=async()=>{const name=(prompt('Rumsnamn eller rumsnr:')||'').trim();if(!name)return;state.activeRoomId=ensureRoom(name).room_id;clearFindingSelection();renderUnit();await persist()};
  presets.append(add);
  if(isCommercial()&&activeRoom()){const done=document.createElement('button');done.type='button';done.id='roomDone';done.className='chip quick';done.textContent='Rum klart → nästa';$('roomChips').append(done)}
  const roomDone=document.getElementById('roomDone');if(roomDone)roomDone.onclick=async()=>{const closed=activeRoom();state.activeRoomId=null;clearFindingSelection();$('photoStatus').className='status pass';$('photoStatus').textContent=(closed?closed.name+' klart. ':'')+'Välj nästa rum.';renderUnit();await persist()}}
function keyStamp(){const unit=activeUnit();unit.key=unit.key||{received:false,received_at:null,returned:false,returned_at:null,master_key_used:false,master_key_note:''};return unit.key}
function renderKeys(){const key=activeUnit().key;$('keyIn').classList.toggle('set',Boolean(key&&key.received));$('keyOut').classList.toggle('set',Boolean(key&&key.returned));$('keyMaster').classList.toggle('set',Boolean(key&&key.master_key_used));const parts=[];if(key&&key.received)parts.push('Mottagen '+key.received_at.slice(11,16));if(key&&key.master_key_used)parts.push('Huvudnyckel: '+key.master_key_note);if(key&&key.returned)parts.push('Återlämnad '+key.returned_at.slice(11,16));$('keyInfo').textContent=parts.join(' · ')}
function historicalMeasurementText(item){
  const unit=item.unit_of_measure||'l/s';
  const value=v=>v===null||v===undefined||v===''?'–':String(v)+' '+unit;
  return (item.point_label||item.point_type||'Mätpunkt')+' · '+(item.measurable===false?'Ej mätbar: '+(item.not_measurable_reason||'Orsak saknas'):'Uppmätt '+value(item.measured_value))+' · Projekterat '+value(item.designed_value);
}
function renderMeasurementHistory(){
  let panel=$('measurementHistory');
  if(!panel){panel=document.createElement('div');panel.id='measurementHistory';$('mrows').after(panel)}
  const key=JSON.stringify([state.project_id,state.inspection_id,state.activeUnitId,state.activeRoomId]);
  const wasOpen=panel.dataset.historyKey===key&&Boolean(panel.querySelector('details')?.open);
  panel.dataset.historyKey=key;panel.replaceChildren();
  const previous=(state.historical_measurements||[]).filter(m=>m.unit_id===state.activeUnitId&&m.room_id===state.activeRoomId);
  if(!state.activeRoomId||!previous.length)return;
  const details=document.createElement('details');details.open=wasOpen;
  const summary=document.createElement('summary');summary.textContent='Visa tidigare mätvärden ('+previous.length+')';summary.style.cursor='pointer';details.append(summary);
  const note=document.createElement('p');note.textContent='Referens: '+(state.previous_inspection_id||'tidigare OVK')+'. Kontrollera att mätpunkterna avser samma don.';details.append(note);
  for(const old of previous){
    const row=document.createElement('p');row.textContent=historicalMeasurementText(old);
    const matches=state.measurements.filter(m=>m.measurement_id===old.measurement_id&&m.unit_id===old.unit_id&&m.room_id===old.room_id&&m.point_type===old.point_type&&m.unit_of_measure===old.unit_of_measure&&(m.system_id||null)===(old.system_id||null));
    if(matches.length===1){
      const current=matches[0];const numeric=v=>v!==null&&v!==undefined&&String(v).trim()!==''&&Number.isFinite(Number(v));
      if(current.measurable!==false&&old.measurable!==false&&numeric(current.measured_value)&&numeric(old.measured_value)){
        const delta=Number(current.measured_value)-Number(old.measured_value);
        row.textContent+=' · Förändring '+(delta>0?'+':'')+delta.toLocaleString('sv-SE',{maximumFractionDigits:3})+' '+(old.unit_of_measure||'l/s');
      }
    }else{row.textContent+=' · Ingen säker donmatchning'}
    details.append(row);
  }
  panel.append(details);
}
function renderMeasurements(){
  const rows=state.measurements.filter(item=>item.unit_id===state.activeUnitId&&item.room_id===state.activeRoomId);
  const container=$('mrows');container.replaceChildren();
  if(!rows.length){const empty=document.createElement('p');empty.className='room-progress';empty.textContent=state.activeRoomId?'Inga mätpunkter i rummet. Lägg till don vid behov.':'Välj ett rum för att se eller lägga till mätpunkter.';container.append(empty)}
  for(const item of rows){
    const label={franluftsdon:'Frånluft',tilluftsdon:'Tilluft',overluftsdon:'Överluft'}[item.point_type]||'Mätpunkt';
    const row=document.createElement('div');row.className='mrow'+(item.measurable?'':' nm');
    const info=document.createElement('div');info.className='lbl';info.textContent=label;
    const detail=document.createElement('small');detail.textContent=[item.point_label,item.system_id,item.designed_value!=null?'Projekterat '+item.designed_value+' l/s':'Projekterat värde saknas'].filter(Boolean).join(' · ');
    const status=document.createElement('span');status.className='measurement-state';
    const input=document.createElement('input');input.inputMode='decimal';input.placeholder='l/s';input.value=item.measured_value??'';input.dataset.meas=item.measurement_id;input.disabled=!item.measurable;input.setAttribute('aria-label',item.point_label+' – uppmätt luftflöde i liter per sekund');
    const renderStatus=()=>{
      const invalid=item.measurable!==false&&item.measured_value!=null&&String(item.measured_value).trim()!==''&&!validFlowValue(item.measured_value);
      status.textContent=item.measurable?(invalid?'Ogiltigt mätvärde':measuredPoint(item)?'Uppmätt':'Ej mätt'):'Ej mätbar: '+item.not_measurable_reason;
      input.setAttribute('aria-invalid',String(invalid));
    };
    renderStatus();info.append(detail,status);
    input.onchange=async()=>{item.measured_value=input.value.trim().replace(',','.')||null;renderStatus();updateUnitProgress();renderMeasurementHistory();await persist()};
    const button=document.createElement('button');button.type='button';button.className='x';button.dataset.nm=item.measurement_id;button.textContent='×';button.title='Ej mätbar';button.setAttribute('aria-label','Markera '+item.point_label+' som ej mätbar');button.onclick=()=>markNotMeasurable(item.measurement_id);
    row.append(info,input,button);container.append(row);
  }
  renderMeasurementHistory();
}
function clearFindingSelection(){
  state.activeFindingId=null;
  $('photoStatus').className='status';$('photoStatus').textContent='Välj eller registrera en anmärkning innan du tar foto.';
}
function renderFindings(){
  const items=state.findings.filter(item=>item.unit_id===state.activeUnitId);
  const container=$('unitFindings');container.replaceChildren();
  if(!items.length){const empty=document.createElement('p');empty.className='room-progress';empty.textContent='Inga anmärkningar registrerade.';container.append(empty)}
  for(const item of items){
    const selected=item.finding_id===state.activeFindingId;
    const button=document.createElement('button');button.type='button';button.className='item finding-choice'+(selected?' selected':'');button.setAttribute('aria-pressed',String(selected));
    const meta=document.createElement('span');meta.className='sub';meta.textContent=[item.room_name||'Utan rum',item.classification!=null?'Klass '+item.classification:item.severity,state.photos.filter(photo=>photo.finding_id===item.finding_id).length+' bilder'].join(' · ');
    const description=document.createElement('strong');description.textContent=item.description;
    button.append(meta,description);button.onclick=()=>{
      state.activeFindingId=item.finding_id;
      state.activeRoomId=unitRooms().some(room=>room.room_id===item.room_id)?item.room_id:null;
      $('photoStatus').className='status';$('photoStatus').textContent='Vald anmärkning · foto och kommentar binds hit: '+item.description;
      renderUnit();
    };container.append(button);
  }
}
function historyDisclosure(panel,key,count,photoCount=0){
  const wasOpen=panel.dataset.historyKey===key&&Boolean(panel.querySelector('details')?.open);
  panel.dataset.historyKey=key;panel.replaceChildren();
  panel.classList.toggle('hidden',!count&&!photoCount&&!state.history_unavailable);
  if(!count&&!photoCount){
    if(state.history_unavailable)panel.textContent='Historiskt fältunderlag saknas.';
    return null;
  }
  const details=document.createElement('details');details.open=wasOpen;
  const summary=document.createElement('summary');summary.style.cursor='pointer';
  summary.style.fontWeight='700';
  if(count)summary.style.color='#b91c1c';
  summary.textContent=count?count+' anmärkning(ar) från föregående OVK': 'Historiska installationsfotografier ('+photoCount+')';
  details.append(summary);
  const body=document.createElement('div');const title=document.createElement('p');
  title.textContent='Historik – '+(state.previous_inspection_id||'tidigare besiktning');body.append(title);
  details.append(body);panel.append(details);return body;
}
const FOLLOWUP_LABELS={not_checked:'Ej återkontrollerad',resolved:'Åtgärdad',remaining:'Kvarstår',changed:'Förändrad anmärkning',not_applicable:'Ej längre tillämplig'};
function renderFindingFollowup(body,item,unit){
  const source=item.source_inspection_id;
  if(!source||source!==state.previous_inspection_id||!item.finding_id)return;
  const inspectionId=state.inspection_id;
  const projectId=state.project_id;
  const existing=state.finding_followups.find(f=>f.source_inspection_id===source&&f.source_finding_id===item.finding_id);
  const form=document.createElement('div');form.className='item';
  const status=document.createElement('select');status.setAttribute('aria-label','Resultat av återkontroll');
  for(const [value,label] of Object.entries(FOLLOWUP_LABELS))status.add(new Option(label,value));
  status.value=existing?.status||'not_checked';
  const note=document.createElement('textarea');note.placeholder='Kommentar till återkontrollen';note.setAttribute('aria-label','Kommentar till återkontrollen');note.value=existing?.note||'';
  const link=document.createElement('select');link.setAttribute('aria-label','Aktuell anmärkning');
  link.add(new Option('Välj aktuell anmärkning',''));
  for(const finding of state.findings.filter(f=>f.unit_id===unit.unit_id&&f.room_id===(item.room_id||null))){
    link.add(new Option(finding.description||finding.defect_type,finding.finding_id));
  }
  link.add(new Option('Skapa ny aktuell anmärkning','__new__'));
  link.value=existing?.current_finding_id||'';
  const description=document.createElement('textarea');description.setAttribute('aria-label','Beskrivning av aktuell anmärkning');description.value=item.description||'';
  const severity=document.createElement('select');severity.setAttribute('aria-label','Klass för aktuell anmärkning');
  severity.add(new Option('Klass 1','minor'));severity.add(new Option('Klass 2','major'));
  severity.value=item.severity==='major'?'major':'minor';
  const message=document.createElement('p');message.setAttribute('role','status');
  message.textContent=existing?'Sparad: '+FOLLOWUP_LABELS[existing.status]:'Ingen återkontroll registrerad.';
  const save=document.createElement('button');save.type='button';save.textContent='Spara återkontroll';
  const needsFinding=()=>status.value==='remaining'||status.value==='changed';
  const refresh=()=>{
    link.hidden=!needsFinding();
    description.hidden=severity.hidden=!needsFinding()||link.value!=='__new__';
  };
  status.onchange=link.onchange=refresh;refresh();
  save.onclick=async()=>{
    if((state.inspection_id!==inspectionId||state.project_id!==projectId)||state.activeUnitId!==unit.unit_id)return;
    const result=status.value;const comment=note.value.trim();
    if((result==='changed'||result==='not_applicable')&&!comment){message.textContent='Ange en kommentar.';return}
    let current=null;let created=null;
    if(needsFinding()){
      if(link.value==='__new__'){
        const room=item.room_id?state.rooms.find(r=>r.room_id===item.room_id&&r.unit_id===unit.unit_id):null;
        if(item.room_id&&!room){message.textContent='Det historiska rummet saknas i aktuell besiktning.';return}
        if(!description.value.trim()){message.textContent='Ange en aktuell beskrivning.';return}
        created={finding_id:uid('finding'),inspection_id:inspectionId,unit_id:unit.unit_id,unit_number:unit.number,room_id:room?.room_id||null,room_name:room?.name||null,defect_type:item.defect_type,description:description.value.trim(),severity:severity.value,classification:severity.value==='major'?2:1,system_id:item.system_id||null,rule_refs:item.rule_refs||[],origin:'observed'};
        current=created.finding_id;
      }else{
        const selected=state.findings.find(f=>f.finding_id===link.value&&f.unit_id===unit.unit_id&&f.room_id===(item.room_id||null));
        if(!selected){message.textContent='Välj eller skapa en aktuell anmärkning.';return}
        current=selected.finding_id;
      }
    }
    if(existing?.current_finding_id&&existing.current_finding_id!==current&&!confirm('Den tidigare kopplade aktuella anmärkningen behålls. Vill du ändra återkontrollen?'))return;
    const oldFollowups=state.finding_followups;
    const oldFindings=state.findings;
    const oldDirty=state.dirty;
    const next={source_inspection_id:source,source_finding_id:item.finding_id,unit_id:unit.unit_id,status:result,note:comment,current_finding_id:current,photo_ids:result==='not_checked'?[]:(existing?.photo_ids||[])};
    state.finding_followups=[...oldFollowups.filter(f=>f.source_inspection_id!==source||f.source_finding_id!==item.finding_id),next];
    if(created)state.findings=[...oldFindings,created];
    save.disabled=true;
    try{await persist()}catch(error){
      state.finding_followups=oldFollowups;state.findings=oldFindings;state.dirty=oldDirty;
      message.textContent='Kunde inte spara lokalt: '+crowErrorText(error);save.disabled=false;return;
    }
    if((state.inspection_id!==inspectionId||state.project_id!==projectId))return;
    if(created){state.activeFindingId=created.finding_id;$('photoStatus').textContent='Anmärkning registrerad · foto binds hit: '+created.description}
    renderUnit();
  };
  form.append(status,note,link,description,severity,save,message);
  if(existing&&existing.status!=='not_checked'){
    const photos=document.createElement('p');photos.textContent='Återkontrollfoton: '+(existing.photo_ids||[]).length;
    const input=document.createElement('input');input.type='file';input.accept='image/*';input.setAttribute('capture','environment');input.setAttribute('aria-label','Fotografera återkontroll');
    input.onchange=async()=>{
      const file=input.files[0];if(!file)return;
      if(!file.type.startsWith('image/')||!file.size||file.size>25*1024*1024){message.textContent='Välj en bild på högst 25 MB.';return}
      input.disabled=true;
      try{
        const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))].map(v=>v.toString(16).padStart(2,'0')).join('');
        const photo={photo_id:uid('photo'),inspection_id:inspectionId,unit_id:unit.unit_id,unit_number:unit.number,defect_type:item.defect_type,captured_at:now(),captured_by:state.inspector,local_uri:'indexeddb:'+file.name,sha256:digest,mime_type:file.type,room_id:item.room_id||null,finding_id:existing.current_finding_id||null,checkpoint_id:null,system_id:item.system_id||null,description:'Återkontroll: '+(item.description||item.defect_type),rule_refs:item.rule_refs||[],sync_status:'local'};
        if((state.inspection_id!==inspectionId||state.project_id!==projectId)||!state.finding_followups.includes(existing))throw new Error('Återkontrollen har ändrats.');
        await dbPut(MEDIA_STORE,{project_id:projectId,photo_id:photo.photo_id,inspection_id:inspectionId,name:file.name,mime_type:photo.mime_type,sha256:digest,blob:file});
        if((state.inspection_id!==inspectionId||state.project_id!==projectId)||!state.finding_followups.includes(existing))throw new Error('Återkontrollen har ändrats.');
        const oldPhotos=state.photos;const oldFollowups=state.finding_followups;const oldDirty=state.dirty;
        state.photos=[...oldPhotos,photo];state.finding_followups=oldFollowups.map(f=>f===existing?{...f,photo_ids:[...(f.photo_ids||[]),photo.photo_id]}:f);
        try{await persist()}catch(error){state.photos=oldPhotos;state.finding_followups=oldFollowups;state.dirty=oldDirty;throw error}
        if(state.inspection_id===inspectionId&&state.activeUnitId===unit.unit_id)renderUnit();
      }catch(error){message.textContent='Foto kunde inte sparas: '+crowErrorText(error);input.disabled=false}
    };
    form.append(photos,input);
  }
  body.append(form);
}
function renderPreviousFindings(unit){
  const panel=$('prevFindings');
  const previous=(state.historical_findings||[]).filter(item=>item.unit_id===unit.unit_id&&(!state.activeRoomId||!item.room_id||item.room_id===state.activeRoomId));
  const body=historyDisclosure(panel,state.inspection_id+'|'+unit.unit_id+'|'+(state.activeRoomId||''),previous.length);
  if(!body)return;
  for(const item of previous){
    const row=document.createElement('p');row.textContent=[item.room_name,item.description].filter(Boolean).join(': ');body.append(row);
    for(const photo of item.photos||[]){
      if(!photo.verified||!photo.content_url)continue;
      const link=document.createElement('a');link.href=fieldEndpoint('media',state.project_id,item.source_inspection_id)+'/'+encodeURIComponent(photo.photo_id)+'/content';link.target='_blank';link.rel='noopener noreferrer';link.textContent='Visa historiskt foto';body.append(link,document.createElement('br'));
    }
    renderFindingFollowup(body,item,unit);
  }
}
async function plannedHistory(record,projectId,inspectionId){
  const source=record.planning?.previous_inspection_id||null;
  if(!source)return {previous_inspection_id:null,historical_findings:[]};
  const response=await fetch(fieldEndpoint('history',projectId,inspectionId),{cache:'no-store'});
  if(response.status===404)return {previous_inspection_id:source,historical_findings:[],history_unavailable:true};
  if(!response.ok)throw new Error('Historiskt underlag kunde inte verifieras.');
  const data=await response.json();
  if(data.source_inspection_id!==source||data.project_id!==projectId||!Array.isArray(data.historical_findings))throw new Error('Historikens identitet stämmer inte.');
  return {previous_inspection_id:source,historical_findings:data.historical_findings,historical_measurements:data.historical_measurements||[],historical_checkpoints:data.historical_checkpoints||[],historical_space_photos:data.historical_space_photos||[]};
}
function renderUnit(){const unit=activeUnit();if(!unit)return;renderKeys();renderRooms();renderFieldTemplate();const roomName=activeRoom()?activeRoom().name:'välj rum';$('visRoom').textContent=roomName;$('measRoom').textContent=roomName;const ftx=isFtx();$('wvMissing').classList.toggle('hidden',ftx);$('wvRow').classList.toggle('hidden',ftx||!activeRoom());$('addSupply').classList.toggle('hidden',!ftx);$('unitSystemBtn').textContent='System: '+(unit.system_type?unit.system_type+' · avvikande':state.system_type+' · fastighet');$('unitSystemBtn').classList.toggle('quick',Boolean(unit.system_type));renderPreviousFindings(unit);renderMeasurements();renderFindings();updateUnitProgress();updateFooter('viewUnit')}
function updateFooter(name){if(name==='viewSpace'){const fails=activeSpace()?spaceCheckpoints(state.activeSpaceId).filter(item=>item.status==='fail').length:0;$('footDone').textContent=spacePending(state.activeSpaceId)?'Till listan – ej klar':fails?'Klar – med anmärkning ('+fails+')':'Klar – UA';$('footDone').className='btn '+(fails?'anm':'ua');$('footBack').textContent='Till listan';return}if(name==='viewUnit'){const remarks=unitRemarks(state.activeUnitId).length;const next=nextPendingUnit(state.activeUnitId);$('footDone').textContent=(remarks?'Klar – ANM ('+remarks+')':'Klar – UA')+(next?' · nästa':'');$('footDone').className='btn '+(remarks?'anm':'ua');$('footBack').textContent='Till listan'}else if(name==='viewRond'){$('footDone').textContent='Synka';$('footDone').className='btn';$('footBack').textContent='Till start'}else{$('footDone').textContent='Starta rondering';$('footDone').className='btn';$('footBack').textContent='–'}}

function addFinding(defectType,severity,description){const unit=activeUnit();const room=activeRoom();const defect=state.defects.find(item=>item.id===defectType);const classification=severity==='major'?2:severity==='minor'?1:0;const finding={finding_id:uid('finding'),inspection_id:state.inspection_id,unit_id:unit.unit_id,unit_number:unit.number,room_id:room?room.room_id:null,room_name:room?room.name:null,defect_type:defectType,description,severity,classification,system_id:null,rule_refs:defect?defect.default_rule_refs||[]:[],origin:'observed'};state.findings.push(finding);state.activeFindingId=finding.finding_id;$('photoStatus').className='status';$('photoStatus').textContent='Anmärkning registrerad · foto binds hit: '+description;return finding}
function markNotMeasurable(measurementId){const item=state.measurements.find(m=>m.measurement_id===measurementId);if(!item)return;const reason=(prompt('Varför är donet ej mätbart? (obligatoriskt, ta foto efteråt)')||'').trim();if(!reason)return;item.measurable=false;item.measured_value=null;item.not_measurable_reason=reason;const room=state.rooms.find(r=>r.room_id===item.room_id);const finding=addFinding('terminal_not_measurable','minor',(room?room.name+': ':'')+item.point_label+' ej mätbart – '+reason);item.finding_id=finding.finding_id;renderUnit();persist()}

/* ---------- allmänna delar ---------- */
function activeSpace(){return state.technical_spaces.find(item=>item.space_id===state.activeSpaceId)||null}
function spaceCheckpoints(spaceId){return state.checkpoints.filter(item=>item.space_id===spaceId)}
function spaceHasNameplate(spaceId){return state.photos.some(photo=>photo.space_id===spaceId&&photo.defect_type==='equipment_nameplate')}
function addSpace(kind){const label=(prompt(kind==='flaktrum'?'Benämning på fläktrummet (t.ex. "Fläktrum plan 10, LB01"):':'Benämning på fläkten (t.ex. "Takfläkt hus A, FF01"):')||'').trim();if(!label)return;const location=(prompt(kind==='takflakt'?'Placering (tak eller vind):':'Placering (valfri):')||'').trim();const space={space_id:uid('space'),inspection_id:state.inspection_id,kind,label,location,system_id:null};state.technical_spaces.push(space);for(const item of (state.checklists[kind]||[])){state.checkpoints.push({checkpoint_id:uid('cp'),inspection_id:state.inspection_id,space_id:space.space_id,label:item.label,status:'not_checked',note:''})}openSpace(space.space_id);persist()}
function spacePending(id){const points=spaceCheckpoints(id);return !points.length||points.some(p=>p.status==='not_checked')}
function renderSpaces(){$('spaceMeta').textContent=state.technical_spaces.length+' utrymmen';$('spaceList').innerHTML=state.technical_spaces.map(space=>{const fails=spaceCheckpoints(space.space_id).filter(item=>item.status==='fail').length;const plate=spaceHasNameplate(space.space_id);const pending=spacePending(space.space_id);const cls=pending?'ej_paborjad':fails?'anmarkning':'ua';return '<button class="unitrow '+cls+'" data-space="'+space.space_id+'"><span class="nr" style="font-size:18px;min-width:0">'+esc(space.label)+'</span><span class="sub">'+(space.kind==='flaktrum'?'Fläktrum':'Takfläkt')+(space.system_id?' · '+esc(space.system_id):'')+(space.location?' · '+esc(space.location):'')+(plate?' · skylt ✓':' · skylt saknas')+'</span><span class="spacer"></span><span class="tag '+cls+'">'+(pending?'Ej klar':fails?fails+' anm.':'UA')+'</span></button>'}).join('');for(const button of $('spaceList').querySelectorAll('[data-space]'))button.onclick=()=>openSpace(button.dataset.space)}
function openSpace(spaceId){state.activeSpaceId=spaceId;const space=activeSpace();$('spaceKindLabel').textContent=space.kind==='flaktrum'?'Fläktrum (aggregat)':'Frånluftsfläkt tak/vind';$('spaceName').textContent=space.label;$('spaceLoc').textContent=[space.system_id,space.location].filter(Boolean).join(' · ');renderSpace();view('viewSpace')}
function renderSpaceHistory(space){
  let panel=$('spaceHistory');
  if(!panel){panel=document.createElement('div');panel.id='spaceHistory';panel.className='status';$('cplist').before(panel)}
  const checks=state.historical_checkpoints.filter(c=>c.space_id===space.space_id);
  const photos=state.historical_space_photos.filter(p=>p.space_id===space.space_id&&p.verified);
  const body=historyDisclosure(panel,state.inspection_id+'|'+space.space_id,checks.length,photos.length);
  if(!body)return;
  for(const check of checks){const row=document.createElement('p');row.textContent=check.label+': '+(check.note||'Anmärkning');body.append(row)}
  for(const photo of photos){const link=document.createElement('a');link.href=fieldEndpoint('media',state.project_id,state.previous_inspection_id)+'/'+encodeURIComponent(photo.photo_id)+'/content';link.target='_blank';link.rel='noopener noreferrer';link.textContent='Visa historiskt installationsfoto';body.append(link,document.createElement('br'))}
}
function renderSpace(){const space=activeSpace();if(!space)return;renderSpaceHistory(space);const plate=spaceHasNameplate(space.space_id);$('nameplateStatus').className='status '+(plate?'pass':'warn');$('nameplateStatus').textContent=plate?'Märkskylt dokumenterad ✓':'Märkskylt ej dokumenterad – fota den.';
  $('cplist').innerHTML=spaceCheckpoints(space.space_id).map(item=>'<button class="unitrow '+(item.status==='not_checked'?'ej_paborjad':item.status==='fail'?'anmarkning':'ua')+'" data-cp="'+item.checkpoint_id+'" style="padding:11px 14px"><span class="nr" style="font-size:15px;min-width:0;font-weight:700">'+esc(item.label)+'</span><span class="spacer"></span><span class="tag '+(item.status==='not_checked'?'ej_paborjad':item.status==='fail'?'anmarkning':'ua')+'">'+(item.status==='not_checked'?'Ej kontrollerad':item.status==='not_applicable'?'Ej tillämplig':item.status==='fail'?'ANM':'UA')+'</span></button>'+(item.note?'<div class="sub" style="margin:2px 0 0 6px">'+esc(item.note)+'</div>':'')).join('');
  for(const button of $('cplist').querySelectorAll('[data-cp]'))button.onclick=()=>toggleCheckpoint(button.dataset.cp);updateFooter('viewSpace')}
function toggleCheckpoint(checkpointId){const item=state.checkpoints.find(cp=>cp.checkpoint_id===checkpointId);if(!item)return;const choice=prompt('Kontrollresultat: 1 = UA, 2 = anmärkning, 3 = ej tillämplig, 4 = ej kontrollerad',({pass:'1',fail:'2',not_applicable:'3',not_checked:'4'})[item.status]||'4');if(!['1','2','3','4'].includes(choice))return;let note='';if(choice==='2'||choice==='3'){note=(prompt('Motivering (obligatorisk): '+item.label,item.note||'')||'').trim();if(!note)return}item.status=({1:'pass',2:'fail',3:'not_applicable',4:'not_checked'})[choice];item.note=note;renderSpace();persist()}

/* ---------- händelser ---------- */
$('generate').onclick=async()=>{generateUnits();await persist()};
$('addFlaktrum').onclick=()=>addSpace('flaktrum');
$('addTakflakt').onclick=()=>addSpace('takflakt');
$('nameplate').onclick=()=>$('spacePhoto').click();
$('spacePhoto').onchange=async()=>{const file=$('spacePhoto').files[0];const projectId=state.project_id,inspectionId=state.inspection_id;const space=activeSpace();if(!file||!space)return;const buffer=await file.arrayBuffer();const hash=await crypto.subtle.digest('SHA-256',buffer);const digest=[...new Uint8Array(hash)].map(value=>value.toString(16).padStart(2,'0')).join('');if(state.project_id!==projectId||state.inspection_id!==inspectionId)return;const photo={photo_id:uid('photo'),inspection_id:inspectionId,unit_id:'',unit_number:'',defect_type:'equipment_nameplate',captured_at:now(),captured_by:state.inspector,local_uri:'indexeddb:'+file.name,sha256:digest,mime_type:file.type||'image/jpeg',room_id:null,finding_id:null,checkpoint_id:null,system_id:space.system_id,space_id:space.space_id,description:'Märkskylt · '+space.label,rule_refs:[],sync_status:'local'};state.photos.push(photo);await dbPut(MEDIA_STORE,{project_id:state.project_id,photo_id:photo.photo_id,inspection_id:state.inspection_id,name:file.name,mime_type:photo.mime_type,sha256:digest,blob:file});$('spacePhoto').value='';renderSpace();await persist()};
$('addUnit').onclick=async()=>{const number=(prompt('Lägenhets-/lokalnummer:')||'').trim();if(!number)return;const kind=confirm('Är detta en lokal? (Avbryt = lägenhet)')?'premises':'apartment';state.units.push({unit_id:uid('unit'),inspection_id:state.inspection_id,number,kind,label:'',status:'ej_paborjad',checked_at:null,bom_at:null,bom_note:'',key:null,system_type:null});renderRond();await persist()};
$('start').onclick=async()=>{const newId=$('inspection').value.trim();const inspector=$('inspector').value.trim();if(!newId||!inspector||!$('systemType').value){$('draftStatus').className='status warn';$('draftStatus').textContent='Ange besiktnings-ID, besiktningsman och systemtyp.';return}const projectId=$('project').value;if(!projectId)return;const switching=state.inspection_id&&(newId!==state.inspection_id||projectId!==state.project_id);if(switching&&await dbGet(DRAFT_STORE,draftKey(projectId,newId))){await restoreLatest({project_id:projectId,inspection_id:newId});return}if(switching){if(!confirm('Starta ny tom besiktning '+newId+'? Pågående session '+state.inspection_id+' ligger kvar sparad lokalt.'))return;Object.assign(state,DEFAULT_STATE(),{defects:state.defects,checklists:state.checklists})}state.project_id=$('project').value;state.inspection_id=newId;state.inspector=inspector;state.system_type=$('systemType').value;state.object_type=$('objectType').value;for(const unit of state.units)unit.inspection_id=state.inspection_id;
  if(state.object_type==='flerbostadshus'&&!state.units.length&&$('unitSeries').value.trim()){generateUnits()}
  if(state.object_type!=='flerbostadshus'&&!state.units.length&&!state.assignment_name){const unit={unit_id:uid('unit'),inspection_id:state.inspection_id,number:'Objekt 1',kind:'premises',label:'',status:'ej_paborjad',checked_at:null,bom_at:null,bom_note:'',key:null,system_type:null};state.units.push(unit);renderRond();openUnit(unit.unit_id);await persist();return}
  renderRond();view('viewRond');await persist()};
$('keyIn').onclick=async()=>{const key=keyStamp();key.received=!key.received;key.received_at=key.received?now():null;if(!key.received){key.returned=false;key.returned_at=null}renderKeys();await persist()};
$('keyOut').onclick=async()=>{const key=keyStamp();if(!key.received&&!key.master_key_used){$('keyInfo').textContent='Markera först nyckel mottagen eller huvudnyckel.';return}if(!key.received){key.received=true;key.received_at=key.received_at||now()}key.returned=!key.returned;key.returned_at=key.returned?now():null;renderKeys();await persist()};
$('keyMaster').onclick=async()=>{const key=keyStamp();if(key.master_key_used){key.master_key_used=false;key.master_key_note=''}else{const note=(prompt('Kommentar om huvudnyckel (obligatorisk för spårbarhet):')||'').trim();if(!note)return;key.master_key_used=true;key.master_key_note=note;if(!key.received){key.received=true;key.received_at=now()}}renderKeys();await persist()};
$('unitSystemBtn').onclick=async()=>{const unit=activeUnit();if(!unit)return;const raw=(prompt('Systemtyp för denna enhet (F, S, FX, FT, FTX).\nLämna tomt för fastighetens ('+state.system_type+') – vanligt avvikande i vinds-/källarlägenheter.',unit.system_type||'')||'').trim().toUpperCase();if(raw&&!['F','S','FX','FT','FTX'].includes(raw)){alert('Ogiltig systemtyp: '+raw);return}unit.system_type=raw||null;renderUnit();await persist()};
$('bom').onclick=async()=>{const unit=activeUnit();const meas=state.measurements.filter(item=>item.unit_id===unit.unit_id);const marks=state.findings.filter(item=>item.unit_id===unit.unit_id);const followups=state.finding_followups.filter(item=>item.unit_id===unit.unit_id);if((meas.length||marks.length||followups.length)&&!confirm('BOM: '+meas.length+' mätningar och '+marks.length+' anmärkningar för enheten tas bort och återkontroller återställs till ej återkontrollerad (foton behålls men kopplas loss). Fortsätt?'))return;const removedFindings=new Set(marks.map(item=>item.finding_id));state.measurements=state.measurements.filter(item=>item.unit_id!==unit.unit_id);state.findings=state.findings.filter(item=>item.unit_id!==unit.unit_id);state.finding_followups=state.finding_followups.map(item=>item.unit_id===unit.unit_id?{...item,status:'not_checked',note:'',current_finding_id:null,photo_ids:[]}:item);for(const photo of state.photos)if(photo.finding_id&&removedFindings.has(photo.finding_id))photo.finding_id=null;if(state.activeFindingId&&removedFindings.has(state.activeFindingId))state.activeFindingId=null;const note=(prompt('BOM – valfri notering (tid och datum stämplas automatiskt):')||'').trim();unit.status='bom';unit.bom_at=now();unit.bom_note=note;unit.checked_at=null;renderRond();view('viewRond');await persist()};
for(const chip of document.querySelectorAll('[data-defect]'))chip.onclick=async()=>{if(!activeUnit())return;const map={missing_terminal:['minor','Don saknas'],kitchen_fan_central_system:['minor','Köksfläkt installerad mot centralt system'],window_vent_missing:['minor','Fönsterventil saknas'],general_damage_observation:['info','Skada/observation']};const [severity,base]=map[chip.dataset.defect];const room=activeRoom();if(chip.dataset.defect==='window_vent_missing'&&room){setWindowVent(room.room_id,false)}addFinding(chip.dataset.defect,severity,(room?room.name+': ':'')+base);renderUnit();await persist()};
function setWindowVent(roomId,present){const existing=state.window_vents.find(item=>item.unit_id===state.activeUnitId&&item.room_id===roomId);if(existing){existing.present=present;return existing}const check={check_id:uid('wv'),inspection_id:state.inspection_id,unit_id:state.activeUnitId,room_id:roomId,present,note:''};state.window_vents.push(check);return check}
$('wvPresent').onclick=async()=>{const room=activeRoom();if(!room)return;setWindowVent(room.room_id,true);$('photoStatus').textContent='Fönsterventil finns · '+room.name+' registrerad.';await persist()};
for(const chip of document.querySelectorAll('[data-point]'))chip.onclick=async()=>{const room=activeRoom();if(!room){$('measRoom').textContent='välj rum först';return}const type=chip.dataset.point;const count=state.measurements.filter(item=>item.unit_id===state.activeUnitId&&item.room_id===room.room_id&&item.point_type===type).length;state.measurements.push({measurement_id:uid('meas'),unit_id:state.activeUnitId,point_type:type,point_label:room.name+' '+(count+1),room_id:room.room_id,measurable:true,measured_value:null,designed_value:null,unit_of_measure:'l/s',not_measurable_reason:'',finding_id:null});renderUnit();await persist()};
for(const chip of document.querySelectorAll('[data-class]'))chip.onclick=async()=>{const finding=state.findings.find(item=>item.finding_id===state.activeFindingId);if(!finding){$('photoStatus').className='status warn';$('photoStatus').textContent='Registrera en anmärkning först.';return}const cls=Number(chip.dataset.class);finding.classification=cls;finding.severity=cls===2?'major':cls===1?'minor':'info';$('photoStatus').className='status';$('photoStatus').textContent='Klass '+cls+' satt på: '+finding.description;renderUnit();await persist()};
$('note').onchange=async()=>{const finding=state.findings.find(item=>item.finding_id===state.activeFindingId);if(finding&&$('note').value.trim()){finding.description=finding.description+' – '+$('note').value.trim();$('note').value='';renderFindings();await persist()}};
$('photo').onchange=async()=>{const file=$('photo').files[0];const projectId=state.project_id,inspectionId=state.inspection_id;if(!file)return;const unit=activeUnit();const finding=state.findings.find(item=>item.finding_id===state.activeFindingId);if(!unit||!finding){$('photoStatus').className='status warn';$('photoStatus').textContent='Registrera en anmärkning först – fotot binds till den.';$('photo').value='';return}const buffer=await file.arrayBuffer();const hash=await crypto.subtle.digest('SHA-256',buffer);const digest=[...new Uint8Array(hash)].map(value=>value.toString(16).padStart(2,'0')).join('');if(state.project_id!==projectId||state.inspection_id!==inspectionId)return;const photo={photo_id:uid('photo'),inspection_id:inspectionId,unit_id:unit.unit_id,unit_number:unit.number,defect_type:finding.defect_type,captured_at:now(),captured_by:state.inspector,local_uri:'indexeddb:'+file.name,sha256:digest,mime_type:file.type||'image/jpeg',room_id:finding.room_id,finding_id:finding.finding_id,checkpoint_id:null,system_id:finding.system_id,description:finding.description,rule_refs:finding.rule_refs,sync_status:'local'};state.photos.push(photo);await dbPut(MEDIA_STORE,{project_id:state.project_id,photo_id:photo.photo_id,inspection_id:state.inspection_id,name:file.name,mime_type:photo.mime_type,sha256:digest,blob:file});$('photo').value='';$('photoStatus').className='status pass';$('photoStatus').textContent='Foto bundet till anmärkningen · '+digest.slice(0,10)+'…';renderFindings();await persist()};
$('footBack').onclick=()=>{const current=document.querySelector('.view.on').id;if(current==='viewUnit'||current==='viewSpace'){renderRond();view('viewRond')}else if(current==='viewRond'){view('viewStart')}};
let finishingUnit=false;
async function finishCurrentUnit(){
  if(finishingUnit)return;
  const unit=activeUnit();if(!unit)return;
  const points=state.measurements.filter(p=>p.unit_id===unit.unit_id);
  if(points.some(p=>pendingPoint(p)&&p.measured_value!=null&&String(p.measured_value).trim()!=='')){
    if($('unitProgress'))$('unitProgress').textContent='Rätta ogiltiga mätvärden innan enheten markeras som besiktigad.';
    return;
  }
  const pending=points.filter(pendingPoint).length;
  if(pending&&!confirm(pending+' mätpunkter saknar värde. Markera enheten som besiktigad ändå? Mätpunkterna blir kvar som ofullständiga.'))return;
  const context=[state.project_id,state.inspection_id,unit.unit_id];
  const previous={status:unit.status,checked_at:unit.checked_at,bom_at:unit.bom_at,bom_note:unit.bom_note};
  finishingUnit=true;$('footDone').disabled=true;$('footBack').disabled=true;
  try{
    const remarks=unitRemarks(unit.unit_id).length;
    unit.status=remarks?'anmarkning':'ua';unit.checked_at=now();unit.bom_at=null;unit.bom_note='';
    try{await persist()}catch(error){Object.assign(unit,previous);if($('unitProgress'))$('unitProgress').textContent='Kunde inte spara enhetens status. Försök igen: '+crowErrorText(error);return}
    if(state.project_id!==context[0]||state.inspection_id!==context[1]||state.activeUnitId!==context[2]||document.querySelector('.view.on').id!=='viewUnit')return;
    const next=nextPendingUnit(unit.unit_id);
    if(next){openUnit(next.unit_id);return}
    renderRond();view('viewRond');
    $('syncStatus').className='status';
    $('syncStatus').textContent='Inga ej färdigmarkerade enheter kvar. Kontrollera BOM, mätpunkter och teknikutrymmen innan protokollet färdigställs. Synka när du har nät.';
  }finally{finishingUnit=false;$('footDone').disabled=false;$('footBack').disabled=false}
}
$('footDone').onclick=async()=>{
  const current=document.querySelector('.view.on').id;
  if(current==='viewStart'){$('start').click();return}
  if(current==='viewRond'){syncDraft();return}
  if(current==='viewSpace'){renderRond();view('viewRond');await persist();return}
  if(current==='viewUnit')await finishCurrentUnit();
};

/* ---------- server ---------- */
function updateNetwork(){$('network').textContent=navigator.onLine?'Online':'Offline';$('network').className='net'+(navigator.onLine?'':' off')}
async function loadRemoteOptions(){try{const modules=await fetch('/api/me/modules');if(modules.ok){const data=await modules.json();if(!(data.modules||[]).some(item=>item.id==='ovk')){$('draftStatus').textContent='OVK ingår inte i licensen.';$('start').disabled=true;return}}}catch(_){/* offline */}
try{const response=await fetch('/api/ovk/field/defect-types');if(response.ok){const data=await response.json();state.defects=data.defect_types||[];await dbPut('meta',{key:'defects',value:state.defects})}}catch(_){const meta=await dbGetAll('meta');const cached=meta.find(item=>item.key==='defects');state.defects=cached?cached.value:[]}
try{const response=await fetch('/api/ovk/field/checklists');if(response.ok){const data=await response.json();state.checklists=data.checklists||{};await dbPut('meta',{key:'checklists',value:state.checklists})}}catch(_){const meta=await dbGetAll('meta');const cached=meta.find(item=>item.key==='checklists');state.checklists=cached?cached.value:{}}
try{const me=await fetch('/api/auth/me');if(me.ok){const info=await me.json();const name=(info.user&&(info.user.username||info.user.name))||info.username||'inloggad';$('authStatus').className='status pass';$('authStatus').textContent='Inloggad: '+name}else{$('authStatus').className='status warn';$('authStatus').innerHTML='Ej inloggad – synk kommer att nekas. <a href="/login">Logga in</a> och ladda om.'}}catch(_){$('authStatus').className='status';$('authStatus').textContent='Offline – synka när du har nät.'}
try{const response=await fetch('/api/ovk/registry/besiktningsman');if(response.ok){const data=await response.json();const persons=data.besiktningsman||[];await dbPut('meta',{key:'inspectors',value:persons});fillInspectors(persons)}else{throw new Error('offline')}}catch(_){const meta=await dbGetAll('meta');const cached=meta.find(item=>item.key==='inspectors');if(cached)fillInspectors(cached.value)}
try{const response=await fetch('/api/projects');if(response.ok){for(const item of await response.json()){ensureProject(item.project_id);const option=[...$('project').options].find(o=>o.value===item.project_id);if(option)option.textContent=item.project_name||item.name||item.project_id}}}catch(_){/* draft project id is enough offline */}await loadHistory()}
function fillInspectors(persons){if(!persons||!persons.length)return;$('inspectorSelect').classList.remove('hidden');$('inspectorSelect').innerHTML='<option value="">— Välj ur registret —</option>'+persons.map(item=>'<option value="'+esc(item.namn)+'">'+esc(item.namn)+' ('+esc(item.behorighet)+')</option>').join('');$('inspectorSelect').onchange=()=>{if($('inspectorSelect').value)$('inspector').value=$('inspectorSelect').value}}
async function prefillObjectType(){if(state.inspection_id||state.units.length)return;const projectId=$('project').value;if(!projectId||!navigator.onLine)return;try{const response=await fetch('/api/ovk/projects/'+encodeURIComponent(projectId)+'/fastighet');if(!response.ok)return;const data=await response.json();const first=(data.fastigheter||[])[0];if(first&&first.fastighetstyp){$('objectType').value=first.fastighetstyp;state.object_type=first.fastighetstyp}}catch(_){/* offline */}}
async function loadHistory(){$('history').innerHTML='<option value="">Välj via uppdragsplaneringen</option>';$('history').disabled=true;$('restore').disabled=true;$('historyStatus').textContent='Tidigare besiktning väljs i uppdragsplaneringen. Historik hämtas automatiskt för planerade uppdrag.'}
async function restoreFromServer(){$('historyStatus').textContent='Öppna ett planerat uppdrag för att återställa projektbundet underlag.'}
async function restoreLatest(requested=null){const drafts=await dbGetAll(DRAFT_STORE);if(!drafts.length)return false;drafts.sort((a,b)=>String(b.updated_at).localeCompare(String(a.updated_at)));const draft=requested?drafts.find(item=>item.inspection_id===requested.inspection_id&&item.project_id===requested.project_id):drafts[0];if(!draft)return false;Object.assign(state,DEFAULT_STATE(),{project_id:draft.project_id||'adhoc',inspection_id:draft.inspection_id||'',inspector:draft.inspector||'',system_type:draft.system_type||'F',object_type:draft.object_type||'flerbostadshus',assignment_name:draft.assignment_name||'',previous_inspection_id:draft.previous_inspection_id||null,historical_findings:draft.historical_findings||[],historical_measurements:draft.historical_measurements||[],history_unavailable:Boolean(draft.history_unavailable),historical_checkpoints:draft.historical_checkpoints||[],historical_space_photos:draft.historical_space_photos||[],units:draft.units||[],rooms:draft.rooms||[],findings:draft.findings||[],finding_followups:draft.finding_followups||[],photos:draft.photos||[],measurements:draft.measurements||[],window_vents:draft.window_vents||[],technical_spaces:draft.technical_spaces||[],checkpoints:draft.checkpoints||[],dirty:Boolean(draft.dirty),last_sync:draft.last_sync||null,defects:state.defects,checklists:state.checklists});$('inspection').value=state.inspection_id;$('inspector').value=state.inspector;$('systemType').value=state.system_type;$('objectType').value=state.object_type;ensureProject(state.project_id);$('project').value=state.project_id;$('draftStatus').textContent='Återställd lokal session · '+(state.assignment_name||state.inspection_id);if(state.assignment_name||state.units.length||state.technical_spaces.length){renderRond();view('viewRond')}return true}
async function syncContext(){const response=await fetch(fieldEndpoint('context',state.project_id,state.inspection_id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({project_id:state.project_id,inspector:state.inspector,previous_inspection_id:state.previous_inspection_id,system_type:state.system_type})});const data=await response.json();if(!response.ok)throw new Error(JSON.stringify(data));return data}
async function syncSnapshot(){const response=await fetch(fieldEndpoint('sync',state.project_id,state.inspection_id),{method:'PUT',headers:{'content-type':'application/json','X-OVK-Base-Revision':state.last_sync||'new'},body:JSON.stringify(payload())});const data=await response.json();if(!response.ok)throw new Error(JSON.stringify(data));state.last_sync=data.snapshot_sha256;return data}
async function syncPendingMedia(){let uploaded=0;for(const photo of state.photos.filter(item=>item.sync_status!=='synced')){const media=await dbGet(MEDIA_STORE,mediaKey(state.project_id,state.inspection_id,photo.photo_id));if(!media||!media.blob||media.sha256!==photo.sha256)throw new Error('Saknar matchande lokal mediablob för '+photo.photo_id);const response=await fetch(fieldEndpoint('media',state.project_id,state.inspection_id)+'/'+encodeURIComponent(photo.photo_id),{method:'PUT',headers:{'content-type':photo.mime_type,'X-OVK-Base-Revision':state.last_sync},body:media.blob});const receipt=await response.json();if(!response.ok)throw new Error(JSON.stringify(receipt));photo.sync_status='synced';state.last_sync=receipt.snapshot_sha256;media.media_id=receipt.media_id;media.evidence_id=receipt.evidence_id;media.synced_at=now();await dbPut(MEDIA_STORE,media);uploaded+=1}return uploaded}
async function syncDraft(){if(!state.inspection_id){$('syncStatus').textContent='Starta en rondering först.';return}if(!navigator.onLine){$('syncStatus').textContent='Offline · allt ligger kvar säkert lokalt.';return}try{$('syncStatus').className='status';$('syncStatus').textContent='Synkar kontext…';await syncContext();$('syncStatus').textContent='Synkar snapshot…';const summary=await syncSnapshot();const uploaded=await syncPendingMedia();if(uploaded){$('syncStatus').textContent='Media verifierad · uppdaterar snapshot…';await syncSnapshot()}state.dirty=false;await writeDraft(false);$('syncStatus').className='status pass';$('syncStatus').textContent='Synkad · '+state.last_sync.slice(0,12)+'… · '+uploaded+' bilder · täckning '+(summary.coverage_complete?'komplett':'ofullständig')}catch(error){state.dirty=true;await writeDraft(true);$('syncStatus').className='status warn';$('syncStatus').textContent='Synkfel: '+crowErrorText(error)}}
$('validate').onclick=async()=>{try{const response=await fetch('/api/ovk/field/validate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload())});const data=await response.json();if(!response.ok)throw new Error(JSON.stringify(data));$('syncStatus').className='status pass';$('syncStatus').textContent='Giltig · '+data.units+' enheter · '+data.measurements+' mätningar · '+data.findings+' anm. · täckning '+(data.coverage_complete?'komplett':'ofullständig')}catch(error){$('syncStatus').className='status warn';$('syncStatus').textContent='Validering: '+crowErrorText(error)}};
$('sync').onclick=syncDraft;
$('restore').onclick=restoreFromServer;
$('project').addEventListener('change',prefillObjectType);$('project').onchange=loadHistory;
window.addEventListener('online',updateNetwork);window.addEventListener('offline',updateNetwork);

async function restoreVerifiedMedia(projectId,inspectionId,photos,verified){
  if(photos.length&&!globalThis.crypto?.subtle)throw new Error('Bildverifiering kräver HTTPS.');
  for(const photo of photos){
    const receipt=verified.find(v=>v.photo_id===photo.photo_id&&v.verified&&v.sha256===photo.sha256);
    if(!receipt)throw new Error('Verifierat bildkvitto saknas.');
    const existing=await dbGet(MEDIA_STORE,mediaKey(projectId,inspectionId,photo.photo_id));
    if(existing&&(existing.inspection_id!==inspectionId||existing.project_id!==projectId||existing.sha256!==photo.sha256))throw new Error('Foto-ID finns i en annan lokal besiktning.');
    const url=fieldEndpoint('media',projectId,inspectionId)+'/'+encodeURIComponent(photo.photo_id)+'/content';
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store'});
    if(!response.ok)throw new Error('Bildhämtning misslyckades: '+photo.photo_id);
    const mime=(response.headers.get('content-type')||'').split(';')[0].toLowerCase();
    if(mime!==photo.mime_type.toLowerCase()||!mime.startsWith('image/'))throw new Error('Bildtyp stämmer inte.');
    const blob=await response.blob();
    if(!blob.size||blob.size>25*1024*1024||blob.size!==receipt.size_bytes)throw new Error('Bildstorlek stämmer inte.');
    const hash=await crypto.subtle.digest('SHA-256',await blob.arrayBuffer());
    const digest=[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('');
    if(digest!==photo.sha256.toLowerCase())throw new Error('Bildens kontrollsumma stämmer inte: '+photo.photo_id);
    await dbPut(MEDIA_STORE,{project_id:projectId,photo_id:photo.photo_id,inspection_id:inspectionId,name:photo.local_uri.replace(/^indexeddb:/,''),mime_type:photo.mime_type,sha256:digest,blob,media_id:receipt.media_id,evidence_id:receipt.evidence_id,synced_at:now()});
  }
}
async function resumeServerInspection(projectId,inspectionId,snapshot,workbench,person,property,types,record){
  const data=snapshot.payload;
  if(snapshot.project_id!==projectId||snapshot.inspection_id!==inspectionId||data?.inspection_id!==inspectionId||
     workbench.inspection_id!==inspectionId||workbench.project_id!==projectId||
     workbench.snapshot_sha256!==snapshot.snapshot_sha256)throw new Error('Serverunderlagets identitet eller revision stämmer inte.');
  const photos=[...workbench.units.flatMap(u=>u.findings.flatMap(f=>f.photos)),...workbench.orphan_photos];
  if(data.photos.some(p=>p.sync_status!=='synced'||!photos.some(v=>v.photo_id===p.photo_id&&v.verified&&v.sha256===p.sha256)))throw new Error('Serverunderlaget innehåller bilder som inte är verifierade. Synka klart på ursprungsenheten.');
  const history=await fetch(fieldEndpoint('context',projectId,inspectionId),{cache:'no-store'});
  if(!history.ok)throw new Error('Kunde inte läsa fältkontext.');
  const context=await history.json();
  if(context.project_id!==projectId||context.inspection_id!==inspectionId||!types.includes(context.system_type))throw new Error('Fältkontexten stämmer inte med uppdraget.');
  const draft={...data,project_id:projectId,inspector:person.namn,system_type:context.system_type,object_type:property.fastighetstyp,assignment_name:record.inspection.object.name,...await plannedHistory(record,projectId,inspectionId),photos:data.photos.map(p=>({...p,sync_status:'synced'})),dirty:false,last_sync:snapshot.snapshot_sha256,updated_at:now()};
  // The server snapshot omits display-only labels; reconstruct from stable IDs.
  draft.findings=data.findings.map(f=>({...f,unit_number:data.units.find(u=>u.unit_id===f.unit_id)?.number||'',room_name:data.rooms.find(r=>r.room_id===f.room_id)?.name||null}));
  if(await dbGet(DRAFT_STORE,draftKey(projectId,inspectionId)))throw new Error('Ett lokalt utkast finns redan. Ladda om för att öppna det.');
  await restoreVerifiedMedia(projectId,inspectionId,data.photos,photos);
  if(await dbGet(DRAFT_STORE,draftKey(projectId,inspectionId)))throw new Error('Ett lokalt utkast finns redan. Ladda om för att öppna det.');
  await dbPut(DRAFT_STORE,draft);
  await restoreLatest({project_id:projectId,inspection_id:inspectionId});
  $('draftStatus').textContent='Återställd serverbesiktning · '+inspectionId;
}
async function prefillPlannedUnits(record,projectId,inspectionId,person,property,systemType){
  const structure=record.building_structure??{units:[],systems:[],technical_spaces:[]};
  if(!Array.isArray(structure.units)||!Array.isArray(structure.systems)||!Array.isArray(structure.technical_spaces))throw new Error('Ogiltig byggnadsstruktur i uppdraget.');
  const draft={...DEFAULT_STATE(),...await plannedHistory(record,projectId,inspectionId),project_id:projectId,inspection_id:inspectionId,inspector:person.namn,object_type:property.fastighetstyp,assignment_name:record.inspection.object.name,system_type:systemType,dirty:true,updated_at:now()};
  const ids=new Set(),roomIds=new Set(),pointIds=new Set();
  const selectedSystems=new Set(record.inspection.systems.map(s=>s.system_id));
  for(const unit of structure.units){
    if(!/^[A-Za-z0-9_-]+$/.test(unit.unit_id)||ids.has(unit.unit_id)||!['apartment','premises'].includes(unit.kind)||!Array.isArray(unit.rooms))throw new Error('Ogiltig enhet i uppdragets struktur.');
    ids.add(unit.unit_id);
    draft.units.push({unit_id:unit.unit_id,inspection_id:inspectionId,number:unit.number,kind:unit.kind,label:'',status:'ej_paborjad',checked_at:null,bom_at:null,bom_note:'',key:null,system_type:null});
    for(const room of unit.rooms){
      if(!/^[A-Za-z0-9_-]+$/.test(room.room_id)||roomIds.has(room.room_id)||typeof room.name!=='string'||!room.name.trim())throw new Error('Ogiltigt rum i uppdragets struktur.');
      roomIds.add(room.room_id);
      draft.rooms.push({room_id:room.room_id,unit_id:unit.unit_id,name:room.name});
      for(const point of (room.measurement_points||[])){
        if(!selectedSystems.has(point.system_id))continue;
        if(!/^[A-Za-z0-9_-]+$/.test(point.point_id)||pointIds.has(point.point_id)||!['franluftsdon','tilluftsdon','overluftsdon'].includes(point.point_type)||point.unit_of_measure!=='l/s'||!point.label)throw new Error('Ogiltig mätpunkt i uppdragets struktur.');
        pointIds.add(point.point_id);
        draft.measurements.push({measurement_id:point.point_id,unit_id:unit.unit_id,room_id:room.room_id,point_type:point.point_type,point_label:point.label,system_id:point.system_id,measurable:true,measured_value:null,designed_value:point.designed_value??null,unit_of_measure:'l/s',not_measurable_reason:'',finding_id:null});
      }
    }
  }
  const registeredSystems=new Set((structure.systems||[]).map(s=>s.system_id));
  if((structure.technical_spaces||[]).length&&![...selectedSystems].some(id=>registeredSystems.has(id)))throw new Error('Uppdragets system-ID matchar inte byggnadsregistret.');
  const spaceIds=new Set();
  const skipped=[];
  for(const space of (structure.technical_spaces||[])){
    if(!selectedSystems.has(space.system_id))continue;
    if(!['flaktrum','takflakt'].includes(space.kind)){skipped.push(space.label+' (klassificering saknas eller stöds inte)');continue}
    if(!/^[A-Za-z0-9_-]+$/.test(space.space_id)||spaceIds.has(space.space_id)||typeof space.label!=='string'||!space.label.trim())throw new Error('Ogiltig installation i uppdragets struktur.');
    const checklist=state.checklists[space.kind];
    if(!Array.isArray(checklist)||!checklist.length)throw new Error('Kontrollista saknas för '+space.label+'. Ladda om med nätanslutning.');
    spaceIds.add(space.space_id);
    draft.technical_spaces.push({space_id:space.space_id,inspection_id:inspectionId,kind:space.kind,label:space.label,location:space.location||'',system_id:space.system_id});
    for(const item of checklist)draft.checkpoints.push({checkpoint_id:uid('cp'),inspection_id:inspectionId,space_id:space.space_id,label:item.label,status:'not_checked',note:''});
  }
  if(skipped.length)throw new Error('Installationer kan inte förberedas: '+skipped.join('; ')+'. Kontrollera uppdragets system och klassificering.');
  // Även ett tomt uppdrag behöver ett lokalt utkast med rätt historik och kontext.
  const db=await openDb();
  try{
    await new Promise((resolve,reject)=>{const tx=db.transaction(DRAFT_STORE,'readwrite');tx.objectStore(DRAFT_STORE).add(draft);tx.oncomplete=()=>resolve();tx.onabort=()=>reject(tx.error);tx.onerror=()=>reject(tx.error)});
  }finally{db.close()}
  await restoreLatest({project_id:projectId,inspection_id:inspectionId});
  $('draftStatus').textContent=draft.units.length||draft.technical_spaces.length?draft.units.length+' enheter och '+draft.rooms.length+' rum och '+draft.technical_spaces.length+' installationer förberedda från uppdraget.':'Uppdraget är öppnat. Lägg till enheter eller installationer i fält. Tidigare underlag är referens, inte nya kontrollresultat.';
  return true;
}
async function openRequestedInspection(projectId,inspectionId){
  const requested={project_id:projectId,inspection_id:inspectionId};
  const lock=()=>{for(const id of ['project','inspection','restore','inspector','inspectorSelect','objectType'])$(id).disabled=true;};
  lock();
  $('start').disabled=true;$('generate').disabled=true;
  try{
    
    if(await restoreLatest(requested)){
      $('start').disabled=false;$('generate').disabled=false;
      return;
    }
    const get=async path=>{const response=await fetch(path);if(!response.ok)throw new Error('HTTP '+response.status);return response.json()};
    const base='/api/ovk/projects/'+encodeURIComponent(projectId);
    const record=await get(base+'/inspections/'+encodeURIComponent(inspectionId));
    const inspection=record.inspection;
    const object=inspection.object;
    if(inspection.inspection_id!==inspectionId||object.project_id!==projectId)throw new Error('Besiktningsidentiteten stämmer inte.');
    if(!record.planning)throw new Error('Uppdraget saknar planeringsuppgifter.');
    const property=await get(base+'/fastighet/'+encodeURIComponent(object.object_id));
    if(property.project_id!==projectId||property.fastighet_id!==object.object_id||!property.byggnader.some(b=>b.byggnad_id===object.building_id))throw new Error('Byggnaden saknas i fastighetsregistret.');
    const person=await get('/api/ovk/registry/besiktningsman/'+encodeURIComponent(record.planning.inspector_id));
    if(person.besiktningsman_id!==record.planning.inspector_id)throw new Error('Besiktningsmannens identitet stämmer inte.');
    const snapshot=await fetch(fieldEndpoint('sync',projectId,inspectionId),{cache:'no-store'});
    if(!snapshot.ok){
      const missing=await snapshot.json();
      if(snapshot.status!==404||missing.detail?.code!=='OVK_FIELD_SNAPSHOT_NOT_FOUND')throw new Error('Serverunderlag kunde inte verifieras. Nytt tomt underlag skapas inte.');
    }

    ensureProject(projectId);
    $('project').value=projectId;
    $('inspection').value=inspectionId;
    $('inspector').value=person.namn;
    $('objectType').value=property.fastighetstyp;
    if(!$('objectType').value)throw new Error('Fastighetstypen stöds inte i fältläget.');
    const types=[...new Set(inspection.systems.map(s=>s.system_type))];
    const supported=[...$('systemType').options].map(o=>o.value);
    if(!types.length||types.some(t=>!supported.includes(t)))throw new Error('Uppdragets systemtyp stöds inte i fältläget.');
    for(const option of $('systemType').options)option.disabled=!types.includes(option.value);
    if(snapshot.ok){
      const workbench=await get(fieldEndpoint('workbench',projectId,inspectionId));
      await resumeServerInspection(projectId,inspectionId,await snapshot.json(),workbench,person,property,types,record);
      $('start').disabled=false;$('generate').disabled=false;
      return;
    }
    if(types.length===1&&await prefillPlannedUnits(record,projectId,inspectionId,person,property,types[0])){
      $('start').disabled=false;$('generate').disabled=false;return;
    }
    $('systemType').value=types.length===1?types[0]:'';
    if(types.length>1){
      $('systemType').onchange=async()=>{
        const selected=$('systemType').value;
        if(!types.includes(selected))return;
        $('systemType').disabled=true;
        try{await prefillPlannedUnits(record,projectId,inspectionId,person,property,selected);$('systemType').onchange=null;$('start').disabled=false;$('generate').disabled=false}
        catch(error){$('draftStatus').textContent=crowErrorText(error)}
        finally{$('systemType').disabled=false}
      };
      $('draftStatus').textContent='Välj systemtyp för ronderingen. Därefter öppnas uppdraget.';
      return;
    }
    throw new Error('Uppdraget kunde inte förberedas.');
  }catch(error){
    $('draftStatus').className='status warn';
    $('draftStatus').textContent='Kunde inte öppna uppdrag: '+crowErrorText(error);
  }
}
async function init(){updateNetwork();if('serviceWorker' in navigator){try{await navigator.serviceWorker.register('/ovk/falt/sw.js',{scope:'/ovk/',updateViaCache:'none'})}catch(_){/* offline funkar utan SW */}}await loadRemoteOptions();const params=new URLSearchParams(location.search);if(params.has('project_id')||params.has('inspection_id')){if(!params.get('project_id')||!params.get('inspection_id')){$('start').disabled=true;$('restore').disabled=true;$('draftStatus').textContent='Både projekt och besiktning krävs.';return}await openRequestedInspection(params.get('project_id'),params.get('inspection_id'));if(typeof updateFieldContextLinks==='function')updateFieldContextLinks();return}await restoreLatest();await prefillObjectType()}
init();
