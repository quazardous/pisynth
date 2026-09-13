// Service worker (#659) — GENERATED at build time from this template (vite.config.js):
// the build hash of the built files and their exact precache list are filled in, so every
// new build is a new service worker: it installs the new files, drops the old cache and the
// page reloads once. Pairing, session checks and the MIDI WebSocket always go to the network.
const VERSION = "pisynth-6af9cfd9d3eb";
const PRECACHE = ["/","/assets/bangers-latin-400-normal-DeHY8Ncq.woff2","/assets/index-CAoWF7rB.css","/assets/index-vifTLgXr.js","/Bangers-OFL.txt","/icon.svg","/manifest.webmanifest"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname === "/ws"
      || url.pathname === "/pair" || url.pathname.startsWith("/api/")) return;      // network only
  const key = e.request.mode === "navigate" ? "/" : url.pathname;                     // SPA routes share the shell
  e.respondWith(caches.open(VERSION).then(async cache => {
    const hit = await cache.match(key);
    if (hit) return hit;                                  // this build's files never change: cache-first
    const r = await fetch(e.request);
    if (r.ok) cache.put(key, r.clone());
    return r;
  }));
});
