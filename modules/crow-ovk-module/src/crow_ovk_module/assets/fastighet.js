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

function fillFastighet(data){$('fastighetId').value=data.fastighet_id||'';$('referensnr').value=data.referensnr||'';$('beteckning').value=data.fastighetsbeteckning||'';$('fastighetstyp').value=data.fastighetstyp||'flerbostadshus';
  const b=data.byggnadens_adress||{};$('bGata').value=b.gata||'';$('bPostnr').value=b.postnr||'';$('bOrt').value=b.ort||'';
  $('agare').value=data.byggnadsagare_namn||'';const a=data.byggnadsagare_adress||{};$('aGata').value=a.gata||'';$('aPostnr').value=a.postnr||'';$('aOrt').value=a.ort||'';
  const f=data.faktureringsadress||{};$('fGata').value=f.gata||'';$('fPostnr').value=f.postnr||'';$('fOrt').value=f.ort||'';
  const fv=data.forvaltare||{};$('forvNamn').value=fv.namn||'';$('forvTel').value=fv.telefon||'';$('forvEpost').value=fv.epost||'';
  byggnader=(data.byggnader||[]).map(item=>({...item}));renderByggnader()}

function buildFastighet(){return{referensnr:$('referensnr').value,fastighetsbeteckning:$('beteckning').value,fastighetstyp:$('fastighetstyp').value,
  byggnadens_adress:{gata:$('bGata').value,postnr:$('bPostnr').value,ort:$('bOrt').value},
  byggnadsagare_namn:$('agare').value,
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
  $('status').className='status';$('status').textContent='Fastigheten sparad.';await loadFastighetList();if($('project').value===project){$('fastighetList').value=id;inventoryReset(saved.fastighet)}}catch(error){$('status').className='status warn';$('status').textContent='Kunde inte spara: '+errText(error)}};

async function loadPersons(){try{const data=await jsonFetch('/api/ovk/registry/besiktningsman');const items=data.besiktningsman||[];
  $('personList').innerHTML=items.length?items.map(item=>'<div class="item" data-id="'+esc(item.besiktningsman_id)+'">'+esc(item.namn)+' <span class="pill">'+esc(item.behorighet)+'</span> <span class="muted">'+esc(item.certifieringsorgan)+' · '+esc(item.certnummer)+(item.giltig_till?' · t.o.m. '+esc(item.giltig_till):'')+'</span></div>').join(''):'<p class="muted">Inga registrerade ännu.</p>';
  for(const row of $('personList').querySelectorAll('.item')){row.onclick=async()=>{const person=await jsonFetch('/api/ovk/registry/besiktningsman/'+enc(row.dataset.id));
    $('pId').value=person.besiktningsman_id;$('pNamn').value=person.namn;$('pBeh').value=person.behorighet;$('pOrgan').value=person.certifieringsorgan;$('pCert').value=person.certnummer;$('pGiltig').value=person.giltig_till||'';$('pTel').value=person.telefon||'';$('pEpost').value=person.epost||'';$('pForetag').value=person.foretag||''}}}
  catch(error){$('personList').textContent=errText(error)}}

$('savePerson').onclick=async()=>{const id=$('pId').value.trim();if(!id){$('personStatus').className='status warn';$('personStatus').textContent='Ange ID.';return}
  try{await jsonFetch('/api/ovk/registry/besiktningsman/'+enc(id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({namn:$('pNamn').value,behorighet:$('pBeh').value,certifieringsorgan:$('pOrgan').value,certnummer:$('pCert').value,giltig_till:$('pGiltig').value||null,telefon:$('pTel').value,epost:$('pEpost').value,foretag:$('pForetag').value})});
  $('personStatus').className='status';$('personStatus').textContent='Besiktningsmannen sparad.';loadPersons()}catch(error){$('personStatus').className='status warn';$('personStatus').textContent='Kunde inte spara: '+errText(error)}};

let inventoryContext=null,inventory=null,inventoryRevision=0,inventoryDirty=false,inventoryBusy=false;
const inventoryId=prefix=>prefix+'-'+Array.from(crypto.getRandomValues(new Uint8Array(12)),v=>v.toString(16).padStart(2,'0')).join('');
function inventoryMessage(message,error=false){$('inventoryStatus').textContent=message;$('inventoryStatus').className='status'+(error?' warn':'')}
function inventoryCanLeave(){return !inventoryBusy&&(!inventoryDirty||confirm('Byggnadsstrukturen har osparade ändringar. Vill du lämna dem?'))}
function inventoryReset(property=null){
  inventoryRevision++;inventory=null;inventoryDirty=false;inventoryBusy=false;
  inventoryContext=property?{project:$('project').value,property:property.fastighet_id,buildings:property.byggnader||[]}:null;
  const select=$('inventoryBuilding');select.replaceChildren(new Option('Välj byggnad…',''));
  if(inventoryContext)for(const b of inventoryContext.buildings)select.add(new Option(b.internt_namn,b.byggnad_id));
  select.disabled=!inventoryContext||!inventoryContext.buildings.length;
  $('inventoryFields').disabled=true;
  for(const id of ['inventorySystems','inventoryUnits','inventorySpaces'])$(id).replaceChildren();
  inventoryMessage(property?'Välj byggnad.':'Välj en sparad fastighet.');
}
function inventoryUrl(building){return '/api/ovk/projects/'+enc(inventoryContext.project)+'/fastighet/'+enc(inventoryContext.property)+'/byggnad/'+enc(building)+'/struktur'}
function inventoryChanged(){inventoryDirty=true;inventoryMessage('Osparade ändringar.')}
function inventoryButton(label,action){const button=document.createElement('button');button.type='button';button.className='button secondary';button.textContent=label;button.onclick=action;return button}
function inventoryInput(parent,label,value,change,options=null){
  const wrap=document.createElement('label');wrap.textContent=label;
  const input=document.createElement(options?'select':'input');
  if(options)for(const [key,name] of options)input.add(new Option(name,key));
  input.value=value;input.oninput=()=>{change(input.value);inventoryChanged()};wrap.append(input);parent.append(wrap);return input;
}
function inventoryCard(parent){const card=document.createElement('div');card.className='bygg';parent.append(card);return card}
function inventoryRemove(items,item){if(!confirm('Ta bort posten från byggnadsregistret?'))return;items.splice(items.indexOf(item),1);inventoryChanged();renderInventory()}
function renderInventory(){
  if(!inventory)return;
  for(const id of ['inventorySystems','inventoryUnits','inventorySpaces'])$(id).replaceChildren();
  for(const system of inventory.systems){
    const card=inventoryCard($('inventorySystems'));
    const identity=document.createElement('p');identity.className='muted';identity.textContent='System-ID: '+system.system_id;card.append(identity);
    inventoryInput(card,'Beteckning / namn',system.label,v=>system.label=v);
    inventoryInput(card,'Systemtyp',system.system_type,v=>system.system_type=v,['S','F','FT','FTX','FX'].map(v=>[v,v]));
    card.append(inventoryButton('Ta bort system',()=>{if(inventory.technical_spaces.some(s=>s.system_id===system.system_id)){inventoryMessage('Ta först bort eller flytta systemets tekniska utrymmen.',true);return}inventoryRemove(inventory.systems,system)}));
  }
  for(const unit of inventory.units){
    const card=inventoryCard($('inventoryUnits'));
    inventoryInput(card,'Lägenhets- / lokalnummer',unit.number,v=>unit.number=v);
    inventoryInput(card,'Typ',unit.kind,v=>unit.kind=v,[['apartment','Lägenhet'],['premises','Lokal']]);
    for(const room of unit.rooms){
      const row=inventoryCard(card);inventoryInput(row,'Rum',room.name,v=>room.name=v);
      row.append(inventoryButton('Ta bort rum',()=>inventoryRemove(unit.rooms,room)));
    }
    card.append(inventoryButton('+ Rum',()=>{unit.rooms.push({room_id:inventoryId('room'),name:''});inventoryChanged();renderInventory()}));
    card.append(inventoryButton('Ta bort enhet',()=>inventoryRemove(inventory.units,unit)));
  }
  for(const space of inventory.technical_spaces){
    const card=inventoryCard($('inventorySpaces'));
    inventoryInput(card,'Tekniskt utrymme',space.label,v=>space.label=v);
    inventoryInput(card,'Ventilationssystem',space.system_id,v=>space.system_id=v,inventory.systems.map(s=>[s.system_id,s.label||s.system_id]));
    card.append(inventoryButton('Ta bort utrymme',()=>inventoryRemove(inventory.technical_spaces,space)));
  }
}
$('inventoryBuilding').onchange=async()=>{
  const select=$('inventoryBuilding'),building=select.value;
  if(!inventoryCanLeave()){select.value=inventoryContext?.building||'';return}
  const revision=++inventoryRevision;inventory=null;inventoryDirty=false;inventoryContext.building=building;
  $('inventoryFields').disabled=true;
  for(const id of ['inventorySystems','inventoryUnits','inventorySpaces'])$(id).replaceChildren();
  if(!building){inventoryMessage('Välj byggnad.');return}
  inventoryMessage('Laddar byggnadsstruktur…');
  try{const data=await jsonFetch(inventoryUrl(building),{cache:'no-store'});if(revision!==inventoryRevision)return;inventory=data;renderInventory();$('inventoryFields').disabled=false;inventoryMessage('Byggnadsstruktur laddad.')}
  catch(error){if(revision===inventoryRevision)inventoryMessage(errText(error),true)}
};
$('inventoryAddSystem').onclick=()=>{inventory.systems.push({system_id:inventoryId('system'),system_type:'F',label:''});inventoryChanged();renderInventory()};
$('inventoryAddUnit').onclick=()=>{inventory.units.push({unit_id:inventoryId('unit'),number:'',kind:'apartment',rooms:[]});inventoryChanged();renderInventory()};
$('inventoryAddSpace').onclick=()=>{if(!inventory.systems.length){inventoryMessage('Lägg till ett ventilationssystem först.',true);return}inventory.technical_spaces.push({space_id:inventoryId('space'),label:'',system_id:inventory.systems[0].system_id});inventoryChanged();renderInventory()};
$('inventorySave').onclick=async()=>{
  if(!inventory||inventoryBusy)return;
  const revision=inventoryRevision,url=inventoryUrl(inventoryContext.building);
  inventoryBusy=true;$('inventoryFields').disabled=true;$('inventoryBuilding').disabled=true;
  try{const saved=await jsonFetch(url,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(inventory)});if(revision!==inventoryRevision)return;inventory=saved;inventoryDirty=false;renderInventory();inventoryMessage('Byggnadsstruktur sparad.')}
  catch(error){if(revision===inventoryRevision)inventoryMessage(errText(error),true)}
  finally{if(revision===inventoryRevision){inventoryBusy=false;$('inventoryFields').disabled=false;$('inventoryBuilding').disabled=false}}
};
window.addEventListener('beforeunload',event=>{if(inventoryDirty||inventoryBusy){event.preventDefault();event.returnValue=''}});
renderByggnader();loadProjects();loadPersons();
