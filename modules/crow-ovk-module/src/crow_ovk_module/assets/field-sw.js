const CACHE_PREFIX='crow-ovk-field-shell-';
const CACHE=CACHE_PREFIX+'v5';
const STATIC_PATHS=new Set([
  '/ovk/falt',
  '/ovk/falt/app.js',
  '/ovk/falt/context.js',
  '/ovk/falt/unit-flow.js',
  '/ovk/falt/time.js'
]);
const REFERENCE_PATHS=new Set([
  '/api/ovk/field/defect-types',
  '/api/ovk/field/checklists'
]);

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>cache.addAll([...STATIC_PATHS]))
      .then(()=>self.skipWaiting())
  );
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
