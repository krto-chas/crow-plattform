const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const enc=encodeURIComponent;
let byggnader=[];

function errText(error){const text=error&&error.message?error.message:String(error);try{const data=JSON.parse(text);const detail=data.detail||data;return (detail.code?detail.code+' · ':'')+(detail.message||'Servern avvisade anropet.')}catch(_){return text}}
async function jsonFetch(url,options){const response=await fetch(url,options);const body=await response.text();if(!response.ok)throw new Error(body);return body?JSON.parse(body):{}}

function slugify(value){return String(value).toLowerCase().replace(/[åä]/g,'a').replace(/ö/g,'o').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')||'fastighet'}
function hasFormContent(){return Boolean($('beteckning').value.trim()||$('fastighetId').value.trim()||$('agare').value.trim()||$('bGata').value.trim()||byggnader.some(item=>String(item.internt_namn||'').trim()))}
async function ensureProject(){const selected=$('project').value;if(selected)return selected;const beteckning=$('beteckning').value.trim();if(!beteckning)return null;
  const name=beteckning;const slug=slugify(beteckning);
  try{const created=await jsonFetch('/api/projects',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name,project_id:slug})});
    await loadProjects();$('project').value=created.project_id||slug;return $('project').value}
  catch(error){const text=String(error&&error.message||error);if(text.includes('409')||text.includes('används redan')){await loadProjects();$('project').value=slug;if($('project').value===slug)return slug}
    throw error}}
function renderByggnader(){$('byggnader').innerHTML=byggnader.map((item,index)=>'<div class="bygg" data-index="'+index+'">'
  +'<div class="row">'
  +'<div><label>Internt namn *</label><input data-field="internt_namn" value="'+esc(item.internt_namn)+'"></div>'
  +'<div><label>Internt nr</label><input data-field="internt_nr" value="'+esc(item.internt_nr)+'"></div>'
  +'<div><label>Verksamhet</label><input data-field="verksamhet" value="'+esc(item.verksamhet)+'"></div>'
  +'</div><div class="row">'
  +'<div><label>BRA m²</label><input data-field="bra_m2" inputmode="decimal" value="'+esc(item.bra_m2??'')+'"></div>'
  +'<div><label>Antal lägenheter</label><input data-field="antal_lagenheter" inputmode="numeric" value="'+esc(item.antal_lagenheter??'')+'"></div>'
  +'<div><label>Antal lokaler</label><input data-field="antal_lokaler" inputmode="numeric" value="'+esc(item.antal_lokaler??'')+'"></div>'
  +'</div><button class="button secondary" data-remove="'+index+'">Ta bort byggnad</button></div>').join('')||'<p class="muted">Inga byggnader ännu.</p>';
  for(const input of $('byggnader').querySelectorAll('input')){input.onchange=()=>{const wrap=input.closest('.bygg');const item=byggnader[Number(wrap.dataset.index)];const field=input.dataset.field;item[field]=input.value.trim()===''?null:input.value.trim();if(field==='internt_namn'||field==='internt_nr'||field==='verksamhet')item[field]=input.value}}
  for(const button of $('byggnader').querySelectorAll('[data-remove]')){button.onclick=()=>{byggnader.splice(Number(button.dataset.remove),1);renderByggnader()}}}

$('addByggnad').onclick=()=>{byggnader.push({byggnad_id:'bygg-'+Date.now().toString(36),internt_namn:'',internt_nr:'',verksamhet:'',bra_m2:null,antal_lagenheter:null,antal_lokaler:null});renderByggnader()};

function fillFastighet(data){window.ovkKunder?.choose(data.kund_id||'');$('fastighetId').value=data.fastighet_id||'';$('referensnr').value=data.referensnr||'';$('beteckning').value=data.fastighetsbeteckning||'';$('fastighetstyp').value=data.fastighetstyp||'flerbostadshus';
  const b=data.byggnadens_adress||{};$('bGata').value=b.gata||'';$('bPostnr').value=b.postnr||'';$('bOrt').value=b.ort||'';
  $('agare').value=data.byggnadsagare_namn||'';const a=data.byggnadsagare_adress||{};$('aGata').value=a.gata||'';$('aPostnr').value=a.postnr||'';$('aOrt').value=a.ort||'';
  const f=data.faktureringsadress||{};$('fGata').value=f.gata||'';$('fPostnr').value=f.postnr||'';$('fOrt').value=f.ort||'';
  const fv=data.forvaltare||{};$('forvNamn').value=fv.namn||'';$('forvTel').value=fv.telefon||'';$('forvEpost').value=fv.epost||'';
  byggnader=(data.byggnader||[]).map(item=>({...item}));renderByggnader()}

function buildFastighet(){return{referensnr:$('referensnr').value,fastighetsbeteckning:$('beteckning').value,fastighetstyp:$('fastighetstyp').value,
  byggnadens_adress:{gata:$('bGata').value,postnr:$('bPostnr').value,ort:$('bOrt').value},
  byggnadsagare_namn:$('agare').value,
  // Kundkopplingen skickas bara när kundlistan är hämtad; annars lämnar servern den orörd.
  ...(window.ovkKunder?.loaded()?{kund_id:$('kund').value||null}:{}),
  byggnadsagare_adress:{gata:$('aGata').value,postnr:$('aPostnr').value,ort:$('aOrt').value},
  faktureringsadress:{gata:$('fGata').value,postnr:$('fPostnr').value,ort:$('fOrt').value},
  forvaltare:{namn:$('forvNamn').value,telefon:$('forvTel').value,epost:$('forvEpost').value},
  byggnader:byggnader.filter(item=>String(item.internt_namn||'').trim())}}

async function loadProjects(){try{const data=await jsonFetch('/api/projects');const projects=data.projects||data||[];$('project').innerHTML='<option value="">Välj projekt…</option>'+projects.map(item=>'<option value="'+esc(item.project_id||item.id)+'">'+esc(item.name||item.project_id||item.id)+'</option>').join('')}catch(error){$('status').className='status warn';$('status').textContent='Kunde inte ladda projekt: '+errText(error)}}

async function loadFastighetList(){const project=$('project').value;if(!project){$('fastighetList').innerHTML='<option value="">— Ny fastighet —</option>';return}
  try{const data=await jsonFetch('/api/ovk/projects/'+enc(project)+'/fastighet');const items=data.fastigheter||[];
  $('fastighetList').innerHTML='<option value="">— Ny fastighet —</option>'+items.map(item=>'<option value="'+esc(item.fastighet_id)+'">'+esc(item.fastighetsbeteckning)+'</option>').join('');
  $('status').className='status';$('status').textContent=items.length+' fastighet(er) i projektet.'}catch(error){$('status').className='status warn';$('status').textContent=errText(error)}}

$('project').onchange=()=>{if(!inventoryCanLeave()){$('project').value=inventoryContext?.project||'';return}inventoryReset();if(!hasFormContent())fillFastighet({});loadFastighetList()};
$('fastighetList').onchange=async()=>{const project=$('project').value;const id=$('fastighetList').value;if(!inventoryCanLeave()){$('fastighetList').value=inventoryContext?.property||'';return}inventoryReset();if(!id){if(!hasFormContent())fillFastighet({});return}
  if(hasFormContent()&&$('fastighetId').value.trim()!==id&&!confirm('Formuläret innehåller uppgifter. Ersätt med sparad fastighet '+id+'?')){$('fastighetList').value='';return}
  try{const data=await jsonFetch('/api/ovk/projects/'+enc(project)+'/fastighet/'+enc(id));if($('project').value!==project||$('fastighetList').value!==id)return;fillFastighet(data);inventoryReset(data)}catch(error){$('status').className='status warn';$('status').textContent=errText(error)}};

$('saveFastighet').onclick=async()=>{if(!inventoryCanLeave())return;if(!$('beteckning').value.trim()){$('status').className='status warn';$('status').textContent='Ange fastighetsbeteckning.';return}
  let project;try{project=await ensureProject()}catch(error){$('status').className='status warn';$('status').textContent='Kunde inte skapa projekt: '+errText(error);return}
  if(!project){$('status').className='status warn';$('status').textContent='Välj projekt eller ange fastighetsbeteckning.';return}
  let id=$('fastighetId').value.trim();if(!id){id=slugify($('beteckning').value);$('fastighetId').value=id}
  try{const saved=await jsonFetch('/api/ovk/projects/'+enc(project)+'/fastighet/'+enc(id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(buildFastighet())});
  $('status').className='status';$('status').textContent='Fastigheten sparad.';await loadFastighetList();window.ovkProperties?.load();window.ovkKunder?.load();if($('project').value===project){$('fastighetList').value=id;inventoryReset(saved.fastighet)}}catch(error){$('status').className='status warn';$('status').textContent='Kunde inte spara: '+errText(error)}};

async function loadPersons(){try{const data=await jsonFetch('/api/ovk/registry/besiktningsman');const items=data.besiktningsman||[];
  $('personList').innerHTML=items.length?items.map(item=>'<div class="item" data-id="'+esc(item.besiktningsman_id)+'">'+esc(item.namn)+' <span class="pill">'+esc(item.behorighet)+'</span> <span class="muted">'+esc(item.certifieringsorgan)+' · '+esc(item.certnummer)+(item.giltig_till?' · t.o.m. '+esc(item.giltig_till):'')+'</span></div>').join(''):'<p class="muted">Inga registrerade ännu.</p>';
  for(const row of $('personList').querySelectorAll('.item')){row.onclick=async()=>{const person=await jsonFetch('/api/ovk/registry/besiktningsman/'+enc(row.dataset.id));
    $('pId').value=person.besiktningsman_id;$('pNamn').value=person.namn;$('pBeh').value=person.behorighet;$('pOrgan').value=person.certifieringsorgan;$('pCert').value=person.certnummer;$('pGiltig').value=person.giltig_till||'';$('pTel').value=person.telefon||'';$('pEpost').value=person.epost||'';$('pForetag').value=person.foretag||''}}}
  catch(error){$('personList').textContent=errText(error)}}

$('savePerson').onclick=async()=>{const id=$('pId').value.trim();if(!id){$('personStatus').className='status warn';$('personStatus').textContent='Ange ID.';return}
  try{await jsonFetch('/api/ovk/registry/besiktningsman/'+enc(id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({namn:$('pNamn').value,behorighet:$('pBeh').value,certifieringsorgan:$('pOrgan').value,certnummer:$('pCert').value,giltig_till:$('pGiltig').value||null,telefon:$('pTel').value,epost:$('pEpost').value,foretag:$('pForetag').value})});
  $('personStatus').className='status';$('personStatus').textContent='Besiktningsmannen sparad.';loadPersons()}catch(error){$('personStatus').className='status warn';$('personStatus').textContent='Kunde inte spara: '+errText(error)}};

let inventoryContext=null,inventory=null,inventoryRevision=0,inventoryDirty=false,inventoryBusy=false;
let inventoryServerRevision=null;
let promotionRequest=0,promotionPreview=null,promotionAssignments=Object.create(null);
const inventoryId=prefix=>prefix+'-'+Array.from(crypto.getRandomValues(new Uint8Array(12)),v=>v.toString(16).padStart(2,'0')).join('');
function inventoryMessage(message,error=false){$('inventoryStatus').textContent=message;$('inventoryStatus').className='status'+(error?' warn':'')}
function inventoryCanLeave(){return !inventoryBusy&&(!inventoryDirty||confirm('Byggnadsstrukturen har osparade ändringar. Vill du lämna dem?'))}
function inventoryReset(property=null){
  clearBulkPreview();clearTemplatePreview();resetPromotionSources();inventoryServerRevision=null;inventoryRevision++;inventory=null;inventoryDirty=false;inventoryBusy=false;
  inventoryContext=property?{project:$('project').value,property:property.fastighet_id,buildings:property.byggnader||[]}:null;
  const select=$('inventoryBuilding');select.replaceChildren(new Option('Välj byggnad…',''));
  if(inventoryContext)for(const b of inventoryContext.buildings)select.add(new Option(b.internt_namn,b.byggnad_id));
  select.disabled=!inventoryContext||!inventoryContext.buildings.length;
  $('inventoryFields').disabled=true;
  for(const id of ['inventorySystems','inventoryTrapphus','inventoryUnits','inventorySpaces'])$(id).replaceChildren();
  inventoryMessage(property?'Välj byggnad.':'Välj en sparad fastighet.');
}
function inventoryUrl(building){return '/api/ovk/projects/'+enc(inventoryContext.project)+'/fastighet/'+enc(inventoryContext.property)+'/byggnad/'+enc(building)+'/struktur'}
function inventoryChanged(){clearBulkPreview();clearTemplatePreview();clearPromotionPreview();inventoryDirty=true;inventoryMessage('Osparade ändringar.')}
function inventoryButton(label,action){const button=document.createElement('button');button.type='button';button.className='button secondary';button.textContent=label;button.onclick=action;return button}
function inventoryInput(parent,label,value,change,options=null){
  const wrap=document.createElement('label');wrap.textContent=label;
  const input=document.createElement(options?'select':'input');
  if(options)for(const [key,name] of options)input.add(new Option(name,key));
  input.value=value;input.oninput=()=>{change(input.value);inventoryChanged()};wrap.append(input);parent.append(wrap);return input;
}
function trapphusLabel(item){const namn=String(item.namn||'').trim(),adress=String(item.adress||'').trim();return (namn||'(namn saknas)')+(adress?' – '+adress:'')}
function inventoryCard(parent){const card=document.createElement('div');card.className='bygg';parent.append(card);return card}
function inventoryRemove(items,item){if(!confirm('Ta bort posten från byggnadsregistret?'))return;items.splice(items.indexOf(item),1);inventoryChanged();renderInventory()}
function renderInventory(){
  renderTemplateRules();
  if(!inventory)return;
  for(const id of ['inventorySystems','inventoryTrapphus','inventoryUnits','inventorySpaces'])$(id).replaceChildren();
  for(const system of inventory.systems){
    const card=inventoryCard($('inventorySystems'));
    const identity=document.createElement('p');identity.className='muted';identity.textContent='System-ID: '+system.system_id;card.append(identity);
    inventoryInput(card,'Beteckning / namn',system.label,v=>system.label=v);
    inventoryInput(card,'Systemtyp',system.system_type,v=>system.system_type=v,['S','F','FT','FTX','FX'].map(v=>[v,v]));
    card.append(inventoryButton('Ta bort system',()=>{if(inventory.technical_spaces.some(s=>s.system_id===system.system_id)||inventory.units.some(u=>u.rooms.some(r=>(r.measurement_points||[]).some(p=>p.system_id===system.system_id)))){inventoryMessage('Ta först bort eller flytta systemets tekniska utrymmen och mätpunkter.',true);return}inventoryRemove(inventory.systems,system)}));
  }
  // Trapphus är en egen lista. Enheterna pekar på sitt trapphus; listan i
  // registret förblir platt och visas här grupperad.
  if(!Array.isArray(inventory.trapphus))inventory.trapphus=[];
  const trapphusOptions=[['','Inget trapphus'],...inventory.trapphus.map(t=>[t.trapphus_id,trapphusLabel(t)])];
  const bulkTrapphus=$('bulkTrapphus'),bulkChosen=bulkTrapphus.value;
  bulkTrapphus.replaceChildren(...trapphusOptions.map(([key,name])=>new Option(name,key)));
  bulkTrapphus.value=inventory.trapphus.some(t=>t.trapphus_id===bulkChosen)?bulkChosen:'';
  bulkTrapphus.disabled=!inventory.trapphus.length;
  const groups=new Map(),headings=new Map();
  const unitGroup=key=>{
    if(!inventory.trapphus.length)return $('inventoryUnits');
    if(!groups.has(key)){
      const section=document.createElement('section');section.className='trapphus-group';
      const heading=document.createElement('h4');section.append(heading);headings.set(key,heading);
      $('inventoryUnits').append(section);groups.set(key,section);
    }
    return groups.get(key);
  };
  const unitCount=key=>inventory.units.filter(u=>(inventory.trapphus.some(t=>t.trapphus_id===u.trapphus_id)?u.trapphus_id:'')===key).length;
  const updateHeadings=()=>{
    for(const [key,heading] of headings){
      const item=inventory.trapphus.find(t=>t.trapphus_id===key),count=unitCount(key);
      heading.textContent=(item?'Trapphus '+trapphusLabel(item):'Utan trapphus')+' · '+count+(count===1?' enhet':' enheter');
    }
  };
  for(const item of inventory.trapphus){
    const card=inventoryCard($('inventoryTrapphus'));
    inventoryInput(card,'Trapphusets namn (t.ex. A eller Uppgång 2)',item.namn,v=>{item.namn=v;updateHeadings()});
    inventoryInput(card,'Adress (gata och nummer)',item.adress||'',v=>{item.adress=v;updateHeadings()});
    card.append(inventoryButton('Ta bort trapphus',()=>{
      if(inventory.units.some(u=>u.trapphus_id===item.trapphus_id)){inventoryMessage('Flytta först trapphusets lägenheter och lokaler till ett annat trapphus.',true);return}
      inventoryRemove(inventory.trapphus,item);
    }));
    unitGroup(item.trapphus_id);
  }
  for(const unit of inventory.units){
    const known=inventory.trapphus.some(t=>t.trapphus_id===unit.trapphus_id);
    const card=inventoryCard(unitGroup(known?unit.trapphus_id:''));
    if(inventory.trapphus.length){
      const select=inventoryInput(card,'Trapphus',known?unit.trapphus_id:'',v=>{if(v)unit.trapphus_id=v;else delete unit.trapphus_id;renderInventory()},trapphusOptions);
      select.setAttribute('aria-label','Trapphus för enheten');
    }
    const kindInput=inventoryInput(card,'Typ',unit.kind,v=>{
      unit.kind=v;
      if(v==='premises'){unit.label=unit.label||'';unit.display_mode=unit.display_mode||'number'}
      renderInventory();
    },[['apartment','Lägenhet'],['premises','Lokal']]);
    kindInput.setAttribute('aria-label','Enhetstyp');
    inventoryInput(card,unit.kind==='premises'?'Permanent lokalnummer':'Lägenhetsnummer',unit.number,v=>unit.number=v);
    if(unit.kind==='premises'){
      inventoryInput(card,'Visa lokalen som',unit.display_mode||((unit.label||'').trim()?'name':'number'),v=>{
        unit.display_mode=v;renderInventory();
      },[['number','Lokalnummer'],['name','Lokalnamn (fritext)']]);
      inventoryInput(card,'Lokalnamn (kan ändras vid byte av hyresgäst)',unit.label||'',v=>unit.label=v);
      const hint=document.createElement('p');hint.className='muted';
      hint.textContent='Lokalnumret är obligatoriskt och följer lokalen över tid. Lokalnamnet kan ändras utan att identiteten ändras.';
      card.append(hint);
    }
    for(const room of unit.rooms){
      const row=inventoryCard(card);inventoryInput(row,'Rum',room.name,v=>room.name=v);
      for(const point of (room.measurement_points||[])){
        const item=inventoryCard(row);
        inventoryInput(item,'Donets beteckning',point.label,v=>point.label=v);
        inventoryInput(item,'Dontyp',point.point_type,v=>point.point_type=v,[['franluftsdon','Frånluft'],['tilluftsdon','Tilluft'],['overluftsdon','Överluft']]);
        inventoryInput(item,'System',point.system_id,v=>point.system_id=v,inventory.systems.map(s=>[s.system_id,s.label||s.system_id]));
        inventoryInput(item,'Projekterat flöde (l/s)',point.designed_value||'',v=>point.designed_value=v.trim().replace(',','.')||null);
        item.append(inventoryButton('Ta bort mätpunkt',()=>inventoryRemove(room.measurement_points,point)));
      }
      row.append(inventoryButton('+ Mätpunkt',()=>{
        if(!inventory.systems.length){inventoryMessage('Lägg till ett ventilationssystem först.',true);return}
        room.measurement_points=room.measurement_points||[];
        room.measurement_points.push({point_id:inventoryId('point'),label:'',point_type:'franluftsdon',system_id:inventory.systems[0].system_id,designed_value:null,unit_of_measure:'l/s'});
        inventoryChanged();renderInventory();
      }));
      row.append(inventoryButton('Ta bort rum',()=>inventoryRemove(unit.rooms,room)));
    }
    card.append(inventoryButton('+ Rum',()=>{unit.rooms.push({room_id:inventoryId('room'),name:''});inventoryChanged();renderInventory()}));
    card.append(inventoryButton('Ta bort enhet',()=>inventoryRemove(inventory.units,unit)));
  }
  updateHeadings();
  for(const space of inventory.technical_spaces){
    const card=inventoryCard($('inventorySpaces'));
    inventoryInput(card,'Beteckning',space.label,v=>space.label=v);
    inventoryInput(card,'Installationstyp',space.kind||'unclassified',v=>space.kind=v,[['unclassified','Ej klassificerad'],['flaktrum','Fläktrum / aggregat'],['takflakt','Frånluftsfläkt tak / vind'],['other','Övrig installation']]);
    inventoryInput(card,'Placering',space.location||'',v=>space.location=v);
    inventoryInput(card,'Ventilationssystem',space.system_id,v=>space.system_id=v,inventory.systems.map(s=>[s.system_id,s.label||s.system_id]));
    card.append(inventoryButton('Ta bort utrymme',()=>inventoryRemove(inventory.technical_spaces,space)));
  }
}
$('inventoryBuilding').onchange=async()=>{
  const select=$('inventoryBuilding'),building=select.value;
  if(!inventoryCanLeave()){select.value=inventoryContext?.building||'';return}
  clearBulkPreview();clearTemplatePreview();resetPromotionSources();inventoryServerRevision=null;const revision=++inventoryRevision;inventory=null;inventoryDirty=false;inventoryContext.building=building;
  $('inventoryFields').disabled=true;
  for(const id of ['inventorySystems','inventoryTrapphus','inventoryUnits','inventorySpaces'])$(id).replaceChildren();
  if(!building){inventoryMessage('Välj byggnad.');return}
  inventoryMessage('Laddar byggnadsstruktur…');
  try{const data=await inventoryFetch(inventoryUrl(building),{cache:'no-store'});if(revision!==inventoryRevision)return;inventory=data.structure;inventoryServerRevision=data.revision;renderInventory();$('inventoryFields').disabled=false;inventoryMessage('Byggnadsstruktur laddad.');void loadPromotionSources(revision)}
  catch(error){if(revision===inventoryRevision)inventoryMessage(errText(error),true)}
};
$('inventoryAddSystem').onclick=()=>{inventory.systems.push({system_id:inventoryId('system'),system_type:'F',label:''});inventoryChanged();renderInventory()};
$('inventoryAddTrapphus').onclick=()=>{if(!Array.isArray(inventory.trapphus))inventory.trapphus=[];inventory.trapphus.push({trapphus_id:inventoryId('trapphus'),namn:'',adress:''});inventoryChanged();renderInventory()};
$('inventoryAddUnit').onclick=()=>{inventory.units.push({unit_id:inventoryId('unit'),number:'',kind:'apartment',label:'',display_mode:'number',rooms:[]});inventoryChanged();renderInventory()};
$('inventoryAddSpace').onclick=()=>{if(!inventory.systems.length){inventoryMessage('Lägg till ett ventilationssystem först.',true);return}inventory.technical_spaces.push({space_id:inventoryId('space'),label:'',kind:'unclassified',location:'',system_id:inventory.systems[0].system_id});inventoryChanged();renderInventory()};
$('inventorySave').onclick=async()=>{
  if(!inventory||inventoryBusy||!inventoryServerRevision)return;
  const trapphusNames=(inventory.trapphus||[]).map(t=>String(t.namn||'').trim().replace(/\s+/g,' ').toLowerCase());
  if(trapphusNames.some(n=>!n)){inventoryMessage('Ange namn på varje trapphus.',true);return}
  if(new Set(trapphusNames).size!==trapphusNames.length){inventoryMessage('Två trapphus har samma namn. Ge dem olika namn.',true);return}
  const revision=inventoryRevision,url=inventoryUrl(inventoryContext.building);
  inventoryBusy=true;$('inventoryFields').disabled=true;$('inventoryBuilding').disabled=true;
  try{const saved=await inventoryFetch(url,{method:'PUT',headers:{'content-type':'application/json','X-OVK-Inventory-Revision':inventoryServerRevision},body:JSON.stringify(inventory)});if(revision!==inventoryRevision)return;inventory=saved.structure;inventoryServerRevision=saved.revision;inventoryDirty=false;clearPromotionPreview();renderInventory();inventoryMessage('Byggnadsstruktur sparad.')}
  catch(error){if(revision===inventoryRevision)inventoryMessage(errText(error),true)}
  finally{if(revision===inventoryRevision){inventoryBusy=false;$('inventoryFields').disabled=false;$('inventoryBuilding').disabled=false}}
};
async function inventoryFetch(url,options){
  const response=await fetch(url,options);
  const text=await response.text();
  if(!response.ok)throw new Error(text);
  const revision=response.headers.get('X-OVK-Inventory-Revision');
  if(!revision||!/^[0-9a-f]{64}$/.test(revision))throw new Error('Serverns registerrevision saknas.');
  return {structure:JSON.parse(text),revision};
}
function clearPromotionPreview(message='Förhandsgranska ett sparat underlag.'){
  promotionRequest++;promotionPreview=null;
  $('promotionResult').replaceChildren();$('promotionConfirm').checked=false;
  $('promotionConfirm').disabled=true;$('promotionApply').disabled=true;
  $('promotionStatus').textContent=message;
}
function resetPromotionSources(){
  clearPromotionPreview('Välj en besiktning.');
  promotionAssignments=Object.create(null);
  $('promotionSource').replaceChildren(new Option('Välj besiktning…',''));
  $('promotionPreview').disabled=true;
}
async function loadPromotionSources(revision){
  const {project,property,building}=inventoryContext;
  try{
    const data=await jsonFetch('/api/ovk/projects/'+enc(project)+'/inspections',{cache:'no-store'});
    if(revision!==inventoryRevision)return;
    if(data.project_id!==project||!Array.isArray(data.inspections))throw new Error('Besiktningslistans identitet stämmer inte.');
    for(const item of data.inspections.filter(item=>item.object_id===property&&item.building_id===building)){
      const label=[item.object_name,item.planning?.planned_date,item.inspection_id].filter(Boolean).join(' · ');
      $('promotionSource').add(new Option(label,item.inspection_id));
    }
    $('promotionPreview').disabled=false;
    $('promotionStatus').textContent='Välj en besiktning och förhandsgranska synkat fältunderlag.';
  }catch(error){if(revision===inventoryRevision)$('promotionStatus').textContent='Besiktningar kunde inte läsas: '+errText(error)}
}
$('promotionSource').onchange=()=>{
  promotionAssignments=Object.create(null);clearPromotionPreview();
};
function promotionUrl(inspection,action){return inventoryUrl(inventoryContext.building)+'/aterforing/'+enc(inspection)+'/'+action}
function promotionLine(parent,text){
  const p=document.createElement('p');p.textContent=text;parent.append(p);
}
function renderPromotion(plan){
  const parent=$('promotionResult');parent.replaceChildren();
  const heading=(label)=>{const h=document.createElement('h4');h.textContent=label;parent.append(h)};
  heading('Föreslagna tillägg ('+plan.additions.length+')');
  for(const item of plan.additions)promotionLine(parent,({unit:'Enhet',room:'Rum',point:'Don'}[item.kind]||'Post')+' · '+item.label);
  if(plan.conflicts.length){heading('Lämnas oförändrade');for(const conflict of plan.conflicts)promotionLine(parent,conflict)}
  if(plan.unresolved.length){
    heading('Don som behöver systemkoppling');
    promotionLine(parent,'Välj registrerat system och förhandsgranska igen. Utan val förs donet inte över.');
    for(const item of plan.unresolved){
      const label=document.createElement('label');label.textContent=item.label;
      const select=document.createElement('select');select.add(new Option('Hoppa över donet',''));
      for(const system of plan.structure.systems)select.add(new Option(system.label+' · '+system.system_type,system.system_id));
      select.value=promotionAssignments[item.point_id]||'';
      select.onchange=()=>{
        if(select.value)promotionAssignments[item.point_id]=select.value;else delete promotionAssignments[item.point_id];
        promotionRequest++;promotionPreview=null;$('promotionConfirm').checked=false;$('promotionConfirm').disabled=true;$('promotionApply').disabled=true;
        $('promotionStatus').textContent='Systemval ändrat. Förhandsgranska igen.';
      };
      label.append(select);parent.append(label);
    }
  }
  $('promotionConfirm').checked=false;$('promotionConfirm').disabled=!plan.additions.length;
  $('promotionApply').disabled=true;
  $('promotionStatus').textContent=plan.additions.length+' tillägg · '+plan.conflicts.length+' konflikter/undantag · '+plan.unresolved.length+' don utan godkänd systemkoppling. Befintliga poster lämnas orörda.';
}
$('promotionPreview').onclick=async()=>{
  if(!inventory||inventoryBusy||inventoryDirty){clearPromotionPreview('Spara byggnadsregistret innan återföring.');return}
  const inspection=$('promotionSource').value;if(!inspection){clearPromotionPreview('Välj en besiktning.');return}
  clearPromotionPreview('Laddar synkat besiktningsunderlag…');
  const revision=inventoryRevision,request=promotionRequest,url=promotionUrl(inspection,'preview');
  const assignments={...promotionAssignments};
  try{
    const plan=await jsonFetch(url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({assignments})});
    if(revision!==inventoryRevision||request!==promotionRequest||inventoryDirty||inventoryBusy)return;
    if(plan.inventory_revision!==inventoryServerRevision){clearPromotionPreview('Registret har ändrats på servern. Välj om byggnaden för att ladda senaste versionen.');return}
    promotionPreview={plan,inspection,assignments};renderPromotion(plan);
  }catch(error){if(revision===inventoryRevision&&request===promotionRequest)clearPromotionPreview('Kunde inte förhandsgranska: '+errText(error))}
};
$('promotionConfirm').onchange=()=>{
  $('promotionApply').disabled=!promotionPreview||!$('promotionConfirm').checked||inventoryBusy||inventoryDirty||!promotionPreview.plan.additions.length;
};
$('promotionApply').onclick=async()=>{
  if(!promotionPreview||inventoryBusy||inventoryDirty||!$('promotionConfirm').checked)return;
  const {plan,inspection,assignments}=promotionPreview;
  if($('promotionSource').value!==inspection)return;
  const revision=inventoryRevision,url=promotionUrl(inspection,'apply');
  inventoryBusy=true;$('inventoryFields').disabled=true;$('inventoryBuilding').disabled=true;
  $('promotionStatus').textContent='Sparar granskade tillägg…';
  try{
    const result=await jsonFetch(url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({assignments,preview_token:plan.preview_token,confirmed:true})});
    if(revision!==inventoryRevision)return;
    inventory=result.structure;inventoryServerRevision=result.inventory_revision;inventoryDirty=false;
    promotionAssignments=Object.create(null);
    clearPromotionPreview(result.additions.length+' tillägg sparade. Besiktningsunderlaget är oförändrat.');
    renderInventory();inventoryMessage('Byggnadsstruktur sparad.');
  }catch(error){if(revision===inventoryRevision)clearPromotionPreview('Återföring kunde inte sparas. Förhandsgranska igen: '+errText(error))}
  finally{if(revision===inventoryRevision){inventoryBusy=false;$('inventoryFields').disabled=false;$('inventoryBuilding').disabled=false}}
};
let bulkPreview=null;
function clearBulkPreview(){
  bulkPreview=null;$('bulkApply').disabled=true;$('bulkResult').replaceChildren();
  $('bulkStatus').textContent='Ange numrering och rumsmall.';
}
function bulkPlan(){
  if(!inventory||inventoryBusy)throw new Error('Välj en sparad byggnad först.');
  const values=['bulkFloor','bulkFloors','bulkStart','bulkPerFloor'].map(id=>$(id).valueAsNumber);
  const [floor,floors,start,perFloor]=values;
  if(!values.every(Number.isInteger)||floor<0||floors<1||floor+floors>100||start<1||perFloor<1||start+perFloor>100||floors*perFloor>500)throw new Error('Ange giltiga heltal. Högst 500 lägenheter per generering.');
  const rooms=$('bulkRooms').value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean);
  if(!rooms.length||rooms.length>30||rooms.some(v=>v.length>100))throw new Error('Ange 1–30 rum med högst 100 tecken per namn.');
  const numbers=[];
  for(let f=floor;f<floor+floors;f++)for(let i=start;i<start+perFloor;i++)numbers.push(String(f).padStart(2,'0')+String(i).padStart(2,'0'));
  const existing=new Set(inventory.units.map(u=>String(u.number).trim()));
  const conflicts=numbers.filter(n=>existing.has(n));
  if(conflicts.length)throw new Error('Nummer finns redan: '+conflicts.slice(0,20).join(', ')+(conflicts.length>20?' …':''));
  const trapphus=$('bulkTrapphus').value;
  if(trapphus&&!(inventory.trapphus||[]).some(t=>t.trapphus_id===trapphus))throw new Error('Trapphuset finns inte längre. Välj igen.');
  return {numbers,rooms,trapphus,revision:inventoryRevision};
}
for(const id of ['bulkFloor','bulkFloors','bulkStart','bulkPerFloor','bulkRooms','bulkTrapphus'])$(id).oninput=clearBulkPreview;
$('bulkPreview').onclick=()=>{
  clearBulkPreview();
  try{
    bulkPreview=bulkPlan();
    const list=document.createElement('p');list.textContent=bulkPreview.numbers.join(', ');$('bulkResult').append(list);
    const bulkTarget=(inventory.trapphus||[]).find(t=>t.trapphus_id===bulkPreview.trapphus);
    $('bulkStatus').textContent=(bulkTarget?'Trapphus '+trapphusLabel(bulkTarget)+' · ':'')+bulkPreview.numbers.length+' lägenheter · '+bulkPreview.numbers.length*bulkPreview.rooms.length+' rum. Rumsmall: '+bulkPreview.rooms.join(', ');
    $('bulkApply').disabled=false;
  }catch(error){$('bulkStatus').textContent=errText(error)}
};
$('bulkApply').onclick=()=>{
  if(!bulkPreview||inventoryBusy)return;
  try{
    const plan=bulkPlan();
    if(plan.revision!==bulkPreview.revision||JSON.stringify(plan)!==JSON.stringify(bulkPreview))throw new Error('Förhandsgranska igen innan du lägger till.');
    const additions=plan.numbers.map(number=>({unit_id:inventoryId('unit'),number,kind:'apartment',...(plan.trapphus?{trapphus_id:plan.trapphus}:{}),rooms:plan.rooms.map(name=>({room_id:inventoryId('room'),name}))}));
    inventory.units.push(...additions);inventoryChanged();renderInventory();
    $('bulkStatus').textContent=additions.length+' lägenheter tillagda. Spara byggnadsstrukturen för att behålla ändringarna.';
  }catch(error){clearBulkPreview();$('bulkStatus').textContent=errText(error)}
};
let templateRules=[{suffix:'01',source:''}];
let templatePreview=null;
let templateContext=null;
function clearTemplatePreview(){
  templatePreview=null;$('templateApply').disabled=true;$('templateConfirmSystems').checked=false;$('templateResult').replaceChildren();
  $('templateStatus').textContent='Förhandsgranska innan generering.';
}
function renderTemplateRules(){
  const context=inventoryContext?JSON.stringify([inventoryContext.project,inventoryContext.property,inventoryContext.building]):null;
  if(templateContext!==context){templateContext=context;templateRules=[{suffix:'01',source:''}];$('templateFillEmpty').checked=false}
  clearTemplatePreview();
  const root=$('templateRules');root.replaceChildren();
  const sources=(inventory?.units||[]).filter(u=>u.kind==='apartment'&&u.rooms.length);
  for(const rule of templateRules){
    const row=document.createElement('div');row.className='row';
    const suffix=document.createElement('input');suffix.value=rule.suffix;suffix.maxLength=2;suffix.setAttribute('aria-label','Lägenhetssuffix XX');
    suffix.oninput=()=>{rule.suffix=suffix.value;clearTemplatePreview()};
    const select=document.createElement('select');select.setAttribute('aria-label','Mall från lägenhet');
    select.append(new Option('Välj mall från lägenhet…',''));
    for(const unit of sources)select.append(new Option(unit.number,unit.unit_id));
    select.value=rule.source;select.onchange=()=>{rule.source=select.value;clearTemplatePreview()};
    const remove=document.createElement('button');remove.type='button';remove.className='button secondary';remove.textContent='Ta bort regel';
    remove.onclick=()=>{templateRules=templateRules.filter(r=>r!==rule);renderTemplateRules()};
    row.append(suffix,select,remove);root.append(row);
  }
}
function templatePlan(){
  if(!inventory||inventoryBusy)throw new Error('Välj en sparad byggnad först.');
  const floor=$('templateFloor').valueAsNumber,floors=$('templateFloors').valueAsNumber;
  if(!Number.isInteger(floor)||!Number.isInteger(floors)||floor<0||floors<1||floor+floors>100||!templateRules.length||floors*templateRules.length>500)throw new Error('Ogiltigt våningsintervall eller antal regler (max 500 lägenheter).');
  const suffixes=new Set(),existing=new Map(),additions=[],completions=[],skipped=[];
  const fillEmpty=$('templateFillEmpty').checked;
  for(const unit of inventory.units){
    const number=String(unit.number).trim();
    if(existing.has(number))throw new Error('Dubbla enhetsnummer i byggnaden: '+number+'. Rätta numreringen först.');
    existing.set(number,unit);
  }
  const systems=new Set(inventory.systems.map(s=>s.system_id));
  for(const rule of templateRules){
    if(!/^(0[1-9]|[1-9][0-9])$/.test(rule.suffix)||suffixes.has(rule.suffix))throw new Error('Ange unika suffix 01–99.');
    suffixes.add(rule.suffix);
    const source=inventory.units.find(u=>u.unit_id===rule.source&&u.kind==='apartment');
    if(!source||!source.rooms.length)throw new Error('Välj en lägenhetsmall med minst ett rum för XX'+rule.suffix);
    const rooms=source.rooms.map(room=>({name:room.name,measurement_points:(room.measurement_points||[]).map(point=>{
      if(!systems.has(point.system_id)||!String(point.label||'').trim()||!['franluftsdon','tilluftsdon','overluftsdon'].includes(point.point_type)||point.unit_of_measure!=='l/s'||(point.designed_value!=null&&!/^[0-9]+(?:\.[0-9]+)?$/.test(point.designed_value)))throw new Error('Ogiltig mätpunkt i mall '+source.number);
      return {label:point.label,point_type:point.point_type,system_id:point.system_id,designed_value:point.designed_value??null,unit_of_measure:'l/s'};
    })}));
    if(rooms.some(r=>!r.name.trim()))throw new Error('Mallens rum måste ha namn.');
    for(let f=floor;f<floor+floors;f++){
      const number=String(f).padStart(2,'0')+rule.suffix;
      if(existing.has(number)){
        const target=existing.get(number);
        if(fillEmpty&&target.kind==='apartment'&&!target.rooms.length){
          completions.push({unit_id:target.unit_id,number,source:source.number,rooms});
        }else skipped.push(number);
        continue;
      }
      additions.push({number,source:source.number,rooms});
    }
  }
  return {revision:inventoryRevision,additions,completions,skipped};
}
$('templateAdd').onclick=()=>{templateRules.push({suffix:'',source:''});renderTemplateRules()};
for(const id of ['templateFloor','templateFloors','templateFillEmpty'])$(id).oninput=clearTemplatePreview;
$('templateConfirmSystems').onchange=()=>{
  $('templateApply').disabled=!templatePreview||!$('templateConfirmSystems').checked||!(templatePreview.additions.length+templatePreview.completions.length);
};
$('templatePreview').onclick=()=>{
  clearTemplatePreview();
  try{
    templatePreview=templatePlan();
    const {additions,completions,skipped}=templatePreview;
    const targets=[...additions,...completions];
    const points=targets.reduce((n,u)=>n+u.rooms.reduce((m,r)=>m+r.measurement_points.length,0),0);
    $('templateStatus').textContent=additions.length+' nya · '+completions.length+' tomma kompletteras · '+points+' mätpunkter · '+skipped.length+' befintliga lämnas oförändrade.';
    for(const u of targets){
      const p=document.createElement('p');
      const detail=u.rooms.map(room=>room.name+(room.measurement_points.length?' ('+room.measurement_points.map(point=>point.label+' · '+(inventory.systems.find(s=>s.system_id===point.system_id)?.label||point.system_id)+' · '+(point.designed_value??'saknar projekterat värde')+(point.designed_value!=null?' l/s':'')).join('; ')+')':'')).join(', ');
      p.textContent=(u.unit_id?'Komplettera ':'Skapa ')+u.number+' ← mall '+u.source+' · '+detail;
      $('templateResult').append(p);
    }
    if(skipped.length){const p=document.createElement('p');p.textContent='Lämnas oförändrade: '+skipped.join(', ');$('templateResult').append(p)}
    $('templateApply').disabled=true;
  }catch(error){$('templateStatus').textContent=errText(error)}
};
$('templateApply').onclick=()=>{
  if(!templatePreview||inventoryBusy||!$('templateConfirmSystems').checked)return;
  try{
    const plan=templatePlan();
    if(JSON.stringify(plan)!==JSON.stringify(templatePreview))throw new Error('Underlaget ändrades. Förhandsgranska igen.');
    const copyRooms=rooms=>rooms.map(r=>({room_id:inventoryId('room'),name:r.name,measurement_points:r.measurement_points.map(p=>({...p,point_id:inventoryId('point')}))}));
    const additions=plan.additions.map(u=>({unit_id:inventoryId('unit'),number:u.number,kind:'apartment',rooms:copyRooms(u.rooms)}));
    const completions=plan.completions.map(u=>{
      const target=inventory.units.find(item=>item.unit_id===u.unit_id&&item.kind==='apartment'&&!item.rooms.length&&String(item.number).trim()===u.number);
      if(!target)throw new Error('Mållägenheten ändrades. Förhandsgranska igen.');
      return {target,rooms:copyRooms(u.rooms)};
    });
    for(const item of completions)item.target.rooms=item.rooms;
    inventory.units.push(...additions);inventoryChanged();renderInventory();
    $('templateStatus').textContent=additions.length+' nya lägenheter och '+completions.length+' kompletterade. Spara byggnadsstrukturen.';
  }catch(error){clearTemplatePreview();$('templateStatus').textContent=errText(error)}
};
window.addEventListener('beforeunload',event=>{if(inventoryDirty||inventoryBusy){event.preventDefault();event.returnValue=''}});
// Öppnar en fastighet från registret i formuläret nedan, genom samma väg som
// när den väljs i listorna, så att skydden mot osparade ändringar gäller.
let registerOpenRevision=0;
async function openRegisteredProperty(project,id){
  const revision=++registerOpenRevision;
  const warn=text=>{$('status').className='status warn';$('status').textContent=text};
  // Ingenting i formuläret ändras förrän projektet finns, användaren har
  // bekräftat och fastigheten är hämtad. Annars kunde formuläret stå kvar med
  // den förra fastigheten under ett nytt projekt och sparas dit.
  if(![...$('project').options].some(option=>option.value===project)){warn('Fastighetens projekt finns inte i projektlistan.');return}
  if(!inventoryCanLeave())return;
  if(hasFormContent()&&($('fastighetId').value.trim()!==id||$('project').value!==project)&&!confirm('Formuläret innehåller uppgifter. Ersätt dem med den valda fastigheten?'))return;
  let data;
  try{data=await jsonFetch('/api/ovk/projects/'+enc(project)+'/fastighet/'+enc(id))}catch(error){if(revision===registerOpenRevision)warn(errText(error));return}
  if(revision!==registerOpenRevision)return;
  // Projekt och formulär byts i samma steg, utan väntan emellan, så att ett
  // senare klick aldrig kan lämna det nya projektet med den förra fastigheten.
  $('project').value=project;fillFastighet(data);inventoryReset(data);
  await loadFastighetList();
  if(revision!==registerOpenRevision)return;
  $('fastighetList').value=id;
  $('editorSelection').scrollIntoView({block:'start'});
}
window.ovkShell?.mount();
if(window.ovkKunder){ovkKunder.init({onChange:()=>window.ovkProperties?.load()});ovkKunder.load()}else $('kundStatus').textContent='Kunderna kunde inte laddas. Ladda om sidan.';
if(window.ovkProperties){ovkProperties.init({onOpen:openRegisteredProperty});ovkProperties.load()}else $('registerStatus').textContent='Registret kunde inte laddas. Ladda om sidan.';
renderByggnader();loadProjects();loadPersons();
