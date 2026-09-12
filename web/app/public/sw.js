// Service worker (#659): the app is fetched from the Pi once, then served from the phone's
// cache (stale-while-revalidate: instant start, refreshed in the background). Pairing, session
// checks and the MIDI WebSocket always go to the network. Vite hashes asset names, so the cache
// fills at runtime; bump VERSION to drop old entries.
const VERSION = "pisynth-v1";

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(["/", "/manifest.webmanifest", "/icon.svg"])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname === "/ws"
      || url.pathname === "/pair" || url.pathname.startsWith("/api/")) return;      // network only
  const key = url.pathname === "/latency" ? "/" : e.request;                          // SPA routes share the shell
  e.respondWith(caches.open(VERSION).then(async cache => {
    const cached = await cache.match(key, { ignoreSearch: true });
    const fresh = fetch(e.request).then(r => { if (r.ok) cache.put(key, r.clone()); return r; }).catch(() => cached);
    return cached || fresh;
  }));
});
