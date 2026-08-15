const CACHE_PREFIX='crow-ovk-field-shell-';
const CACHE=CACHE_PREFIX+'v7';
const FIELD_PAGE='/ovk/falt';
const STATIC_PATHS=new Set([
  '/ovk/falt/app.js',
  '/ovk/falt/context.js',
  '/ovk/falt/unit-flow.js',
  '/ovk/falt/auth.js',
  '/ovk/falt/time.js'
]);
const REFERENCE_PATHS=new Set([
  '/api/ovk/field/defect-types',
  '/api/ovk/field/checklists'
]);

async function installShell(){
  const cache=await caches.open(CACHE);
  await cache.addAll([...STATIC_PATHS]);
  try{
    const response=await fetch(FIELD_PAGE,{credentials:'same-origin',cache:'no-store'});
    if(response.ok&&!response.redirected&&new URL(response.url).pathname===FIELD_PAGE){
      await cache.put(FIELD_PAGE,response.clone());
    }
  }catch(_error){
    // Offline during worker installation: static assets are still available.
  }
}

self.addEventListener('install',event=>{
  event.waitUntil(installShell().then(()=>self.skipWaiting()));
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key.startsWith(CACHE_PREFIX)&&key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);

  if(url.pathname===FIELD_PAGE){
    event.respondWith(
      fetch(request)
        .then(async response=>{
          if(response.ok&&!response.redirected&&new URL(response.url).pathname===FIELD_PAGE){
            const cache=await caches.open(CACHE);
            await cache.put(FIELD_PAGE,response.clone());
          }
          return response;
        })
        .catch(async()=>{
          const cached=await caches.open(CACHE).then(cache=>cache.match(FIELD_PAGE));
          return cached||new Response('Crow OVK Fält är inte tillgängligt offline ännu.',{
            status:503,
            headers:{'content-type':'text/plain; charset=utf-8'}
          });
        })
    );
    return;
  }

  if(STATIC_PATHS.has(url.pathname)){
    event.respondWith(
      caches.open(CACHE).then(async cache=>{
        const cached=await cache.match(url.pathname);
        if(cached)return cached;
        const response=await fetch(request);
        if(response.ok)await cache.put(url.pathname,response.clone());
        return response;
      })
    );
    return;
  }

  if(REFERENCE_PATHS.has(url.pathname)){
    event.respondWith(
      fetch(request)
        .then(response=>{
          if(response.ok){
            const copy=response.clone();
            caches.open(CACHE).then(cache=>cache.put(url.pathname,copy));
          }
          return response;
        })
        .catch(()=>caches.open(CACHE).then(cache=>cache.match(url.pathname)))
    );
  }
});
