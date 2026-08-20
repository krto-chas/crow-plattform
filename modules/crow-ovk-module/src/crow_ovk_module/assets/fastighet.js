const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const enc=encodeURIComponent;
let byggnader=[];

function errText(error){const text=error&&error.message?error.message:String(error);try{const data=JSON.parse(text);const detail=data.detail||data;return (detail.code?detail.code+' · ':'')+(detail.message||'Servern avvisade anropet.')}catch(_){return text}}
async function jsonFetch(url,options){const response=await fetch(url,options);const body=await response.text();if(!response.ok)throw new Error(body);return body?JSON.parse(body):{}}

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

function fillFastighet(data){$('fastighetId').value=data.fastighet_id||'';$('referensnr').value=data.referensnr||'';$('beteckning').value=data.fastighetsbeteckning||'';
  const b=data.byggnadens_adress||{};$('bGata').value=b.gata||'';$('bPostnr').value=b.postnr||'';$('bOrt').value=b.ort||'';
  $('agare').value=data.byggnadsagare_namn||'';const a=data.byggnadsagare_adress||{};$('aGata').value=a.gata||'';$('aPostnr').value=a.postnr||'';$('aOrt').value=a.ort||'';
  const f=data.faktureringsadress||{};$('fGata').value=f.gata||'';$('fPostnr').value=f.postnr||'';$('fOrt').value=f.ort||'';
  const fv=data.forvaltare||{};$('forvNamn').value=fv.namn||'';$('forvTel').value=fv.telefon||'';$('forvEpost').value=fv.epost||'';
  byggnader=(data.byggnader||[]).map(item=>({...item}));renderByggnader()}

function buildFastighet(){return{referensnr:$('referensnr').value,fastighetsbeteckning:$('beteckning').value,
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

$('project').onchange=()=>{fillFastighet({});loadFastighetList()};
$('fastighetList').onchange=async()=>{const project=$('project').value;const id=$('fastighetList').value;if(!id){fillFastighet({});return}
  try{fillFastighet(await jsonFetch('/api/ovk/projects/'+enc(project)+'/fastighet/'+enc(id)))}catch(error){$('status').className='status warn';$('status').textContent=errText(error)}};

$('saveFastighet').onclick=async()=>{const project=$('project').value;const id=$('fastighetId').value.trim();
  if(!project){$('status').className='status warn';$('status').textContent='Välj projekt först.';return}
  if(!id){$('status').className='status warn';$('status').textContent='Ange fastighets-ID.';return}
  try{await jsonFetch('/api/ovk/projects/'+enc(project)+'/fastighet/'+enc(id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(buildFastighet())});
  $('status').className='status';$('status').textContent='Fastigheten sparad.';loadFastighetList()}catch(error){$('status').className='status warn';$('status').textContent='Kunde inte spara: '+errText(error)}};

async function loadPersons(){try{const data=await jsonFetch('/api/ovk/registry/besiktningsman');const items=data.besiktningsman||[];
  $('personList').innerHTML=items.length?items.map(item=>'<div class="item" data-id="'+esc(item.besiktningsman_id)+'">'+esc(item.namn)+' <span class="pill">'+esc(item.behorighet)+'</span> <span class="muted">'+esc(item.certifieringsorgan)+' · '+esc(item.certnummer)+(item.giltig_till?' · t.o.m. '+esc(item.giltig_till):'')+'</span></div>').join(''):'<p class="muted">Inga registrerade ännu.</p>';
  for(const row of $('personList').querySelectorAll('.item')){row.onclick=async()=>{const person=await jsonFetch('/api/ovk/registry/besiktningsman/'+enc(row.dataset.id));
    $('pId').value=person.besiktningsman_id;$('pNamn').value=person.namn;$('pBeh').value=person.behorighet;$('pOrgan').value=person.certifieringsorgan;$('pCert').value=person.certnummer;$('pGiltig').value=person.giltig_till||'';$('pTel').value=person.telefon||'';$('pEpost').value=person.epost||'';$('pForetag').value=person.foretag||''}}}
  catch(error){$('personList').textContent=errText(error)}}

$('savePerson').onclick=async()=>{const id=$('pId').value.trim();if(!id){$('personStatus').className='status warn';$('personStatus').textContent='Ange ID.';return}
  try{await jsonFetch('/api/ovk/registry/besiktningsman/'+enc(id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({namn:$('pNamn').value,behorighet:$('pBeh').value,certifieringsorgan:$('pOrgan').value,certnummer:$('pCert').value,giltig_till:$('pGiltig').value||null,telefon:$('pTel').value,epost:$('pEpost').value,foretag:$('pForetag').value})});
  $('personStatus').className='status';$('personStatus').textContent='Besiktningsmannen sparad.';loadPersons()}catch(error){$('personStatus').className='status warn';$('personStatus').textContent='Kunde inte spara: '+errText(error)}};

renderByggnader();loadProjects();loadPersons();
