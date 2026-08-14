const CACHE='crow-ovk-field-shell-v4';
const CACHE_PREFIX='crow-ovk-field-shell-';
const APP_SHELL=[
  '/ovk/falt',
  '/ovk/falt/app.js',
  '/ovk/falt/context.js',
  '/ovk/falt/time.js',
  '/api/ovk/field/defect-types',
  '/api/ovk/field/checklists'
];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>cache.addAll(APP_SHELL))
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

  if(url.pathname==='/api/projects'){
    event.respondWith(
      fetch(request)
        .then(response=>{
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put(request,copy));
          return response;
        })
        .catch(()=>caches.match(request))
    );
    return;
  }

  if(url.pathname==='/ovk/falt'){
    event.respondWith(
      fetch(request)
        .then(response=>{
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put('/ovk/falt',copy));
          return response;
        })
        .catch(()=>caches.match('/ovk/falt'))
    );
    return;
  }

  const cacheable=
    url.pathname.startsWith('/ovk/falt/')||
    url.pathname==='/api/ovk/field/defect-types'||
    url.pathname==='/api/ovk/field/checklists';
  if(!cacheable)return;

  event.respondWith(
    caches.match(request).then(cached=>cached||fetch(request).then(response=>{
      const copy=response.clone();
      caches.open(CACHE).then(cache=>cache.put(request,copy));
      return response;
    }))
  );
});
