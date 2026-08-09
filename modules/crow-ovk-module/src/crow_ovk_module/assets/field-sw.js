const CACHE='crow-ovk-field-shell-v1';
const APP_SHELL=['/ovk/falt','/ovk/falt/app.js','/api/ovk/field/defect-types'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(APP_SHELL)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim())});
self.addEventListener('fetch',event=>{const request=event.request;if(request.method!=='GET')return;const url=new URL(request.url);if(url.pathname==='/api/projects'){event.respondWith(fetch(request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy));return response}).catch(()=>caches.match(request)));return}if(url.pathname.startsWith('/ovk/falt')||url.pathname==='/api/ovk/field/defect-types'){event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy));return response})));}});
