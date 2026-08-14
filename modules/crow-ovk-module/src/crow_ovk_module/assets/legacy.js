const $ = id => document.getElementById(id);
const queue = [];
const factFields = ['inspection_date','system_id','apartment_number','measured_airflow','designed_airflow','finding'];
const esc = value => { const div=document.createElement('div'); div.textContent=String(value ?? ''); return div.innerHTML; };
const slug = value => String(value||'legacy').replace(/[^A-Za-z0-9._-]+/g,'-').replace(/^-+|-+$/g,'').slice(0,48) || 'legacy';

function sourceFact(fact){return {field:fact.field,value:fact.value,source_id:fact.source.source_id,filename:fact.source.filename,locator:fact.source.locator,source_sha256:fact.source.sha256};}
function inferredDate(item){const dates=item.data.facts.filter(f=>f.field==='inspection_date').map(f=>f.value);return [...new Set(dates)].length===1?dates[0]:'';}
function defaultInspectionId(item,index){const date=inferredDate(item)||'unknown-date';return 'legacy-'+date+'-'+slug(item.data.filename)+'-'+String(index+1).padStart(2,'0');}
function previewItem(data,index){const item={data,factAccepted:data.facts.map(()=>true),reviewAccepted:data.review.map(()=>false),reviewFields:data.review.map(()=>''),reviewValues:data.review.map(r=>r.source_text||''),inspectionId:'',inspectionDate:'',committed:false,error:false,status:'Preview klar · reviewposter kräver aktivt godkännande.'};item.inspectionDate=inferredDate(item);item.inspectionId=defaultInspectionId(item,index);return item;}

function render(){
  $('queue').innerHTML=queue.map((item,index)=>{
    const facts=item.data.facts.map((fact,fi)=>`<div class="fact"><input type="checkbox" data-action="fact" data-index="${index}" data-fi="${fi}" ${item.factAccepted[fi]?'checked':''}><strong>${esc(fact.field)}</strong><span>${esc(fact.value)}</span><span class="source">${esc(fact.source.locator)}<br>${esc(fact.source.source_id)}</span></div>`).join('');
    const reviews=item.data.review.map((review,ri)=>`<div class="review"><input type="checkbox" data-action="review" data-index="${index}" data-ri="${ri}" ${item.reviewAccepted[ri]?'checked':''}><select data-action="reviewField" data-index="${index}" data-ri="${ri}">${['<option value="">Välj fält…</option>',...factFields.map(field=>`<option value="${field}" ${item.reviewFields[ri]===field?'selected':''}>${field}</option>`)].join('')}</select><input data-action="reviewValue" data-index="${index}" data-ri="${ri}" value="${esc(item.reviewValues[ri]||'')}" placeholder="Godkänt värde"><span><strong>${esc(review.reason)}</strong><br>${esc(review.source_text)}<br><span class="source">${esc(review.source.locator)}</span></span></div>`).join('');
    const stateClass=item.committed?'pass':item.error?'warn':'';
    return `<section class="card file"><div class="grid"><div><h2>${esc(item.data.filename)}</h2><span class="pill">${esc(item.data.kind)}</span> <span class="pill">${item.data.facts.length} fakta</span> <span class="pill">${item.data.review.length} review</span></div><div><label>Historiskt besiktnings-ID</label><input data-action="inspectionId" data-index="${index}" value="${esc(item.inspectionId)}"><label>Besiktningsdatum</label><input data-action="inspectionDate" data-index="${index}" value="${esc(item.inspectionDate)}" placeholder="YYYY-MM-DD"></div></div><h3>Extraherade fakta</h3>${facts||'<p>Inga explicita fakta extraherades.</p>'}<h3>Reviewposter</h3>${reviews||'<p>Inga tvetydiga poster.</p>'}<div class="actions"><button data-action="commit" data-index="${index}" class="good">Commit:a denna besiktning</button><button data-action="remove" data-index="${index}" class="alt">Ta bort ur kö</button></div><div class="status ${stateClass}">${esc(item.status)}</div></section>`;
  }).join('');
}

async function previewFiles(){
  const project=$('project').value.trim(); const files=[...$('files').files];
  if(!project||!files.length){$('globalStatus').textContent='Projekt-ID och minst en PDF/XLSX krävs.';return;}
  $('globalStatus').textContent='Analyserar '+files.length+' filer…';
  for(const file of files){
    const form=new FormData(); form.append('project_id',project); form.append('file',file);
    try{
      const response=await fetch('/api/ovk/legacy/preview',{method:'POST',body:form}); const data=await response.json();
      if(!response.ok)throw new Error(JSON.stringify(data));
      queue.push(previewItem(data,queue.length));
    }catch(error){queue.push({data:{filename:file.name,kind:'unknown',facts:[],review:[],source_sha256:''},factAccepted:[],reviewAccepted:[],reviewFields:[],reviewValues:[],inspectionId:'',inspectionDate:'',committed:false,error:true,status:'Preview misslyckades: '+String(error)});}
    render();
  }
  $('globalStatus').textContent=queue.length+' filer i granskningskön.';
}

async function loadProjectAsset(){
  const params=new URLSearchParams(location.search);const project=(params.get('project_id')||'').trim();const checksum=(params.get('checksum')||'').trim();
  if(project)$('project').value=project;
  if(!project||!checksum)return;
  $('globalStatus').textContent='Laddar Workbench-underlag…';
  try{
    const response=await fetch('/api/ovk/projects/'+encodeURIComponent(project)+'/legacy-assets/'+encodeURIComponent(checksum)+'/preview');const data=await response.json();
    if(!response.ok)throw new Error(JSON.stringify(data));
    queue.push(previewItem(data,queue.length));render();$('globalStatus').textContent='Workbench-underlaget är laddat i granskningskön.';
  }catch(error){$('globalStatus').textContent='Kunde inte ladda Workbench-underlaget: '+String(error);}
}

function reviewedFacts(item){
  const facts=item.data.facts.filter((_,i)=>item.factAccepted[i]).map(sourceFact);
  item.data.review.forEach((review,i)=>{if(!item.reviewAccepted[i])return;const field=item.reviewFields[i];const value=(item.reviewValues[i]||'').trim();if(!field||!value)throw new Error('Godkänd reviewpost saknar fält eller värde.');facts.push({field,value,source_id:review.source.source_id,filename:review.source.filename,locator:review.source.locator,source_sha256:review.source.sha256});});
  return facts;
}

async function commitItem(index){
  const item=queue[index]; if(!item||item.committed)return true;
  const project=$('project').value.trim(); const inspector=$('inspector').value.trim();
  try{
    if(!project||!inspector)throw new Error('Projekt-ID och importansvarig krävs.');
    if(!item.inspectionId.trim())throw new Error('Historiskt besiktnings-ID krävs.');
    const facts=reviewedFacts(item); if(!facts.length)throw new Error('Minst ett godkänt faktum krävs.');
    const payload={inspection_id:item.inspectionId.trim(),project_id:project,inspector,inspection_date:item.inspectionDate.trim(),source_filename:item.data.filename,source_sha256:item.data.source_sha256,facts};
    item.status='Commit pågår…'; item.error=false; render();
    const response=await fetch('/api/ovk/legacy/commit',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)}); const data=await response.json();
    if(!response.ok)throw new Error(JSON.stringify(data));
    item.committed=true; item.status='Commit klar · snapshot '+String(data.snapshot_sha256||'').slice(0,12)+'…'; render(); return true;
  }catch(error){item.error=true;item.status='Commit stoppad: '+String(error);render();return false;}
}

async function commitAll(){
  let ok=0,failed=0;
  for(let index=0;index<queue.length;index++){if(queue[index].committed)continue;(await commitItem(index))?ok++:failed++;}
  $('globalStatus').textContent='Batch klar · '+ok+' commit:ade · '+failed+' stoppade. Varje fil redovisas separat.';
}

$('preview').onclick=previewFiles;
$('commitAll').onclick=commitAll;
$('queue').onchange=event=>{const target=event.target;const index=Number(target.dataset.index);const item=queue[index];if(!item)return;const ri=Number(target.dataset.ri);const fi=Number(target.dataset.fi);switch(target.dataset.action){case'fact':item.factAccepted[fi]=target.checked;break;case'review':item.reviewAccepted[ri]=target.checked;break;case'reviewField':item.reviewFields[ri]=target.value;break;case'reviewValue':item.reviewValues[ri]=target.value;break;case'inspectionId':item.inspectionId=target.value;break;case'inspectionDate':item.inspectionDate=target.value;break;}};
$('queue').oninput=$('queue').onchange;
$('queue').onclick=event=>{const target=event.target.closest('button');if(!target)return;const index=Number(target.dataset.index);if(target.dataset.action==='commit')commitItem(index);if(target.dataset.action==='remove'){queue.splice(index,1);render();}};
loadProjectAsset();
