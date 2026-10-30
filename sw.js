/* Mesozoic Carousel service worker: works offline, keeps recent pictures. */
const VERSION = "mc-v3";
const SHELL = `${VERSION}-shell`, PICS = `${VERSION}-pics`, FONTS = `${VERSION}-fonts`;
const MAX_PICS = 160;
const PRECACHE = ["./", "index.html", "manifest.webmanifest", "data/dinos.json", "data/tree.json",
  "icons/icon-192.png", "icons/icon-512.png", "icons/favicon-64.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function trim(cacheName, max) {
  const c = await caches.open(cacheName), keys = await c.keys();
  for (let i = 0; i < keys.length - max; i++) await c.delete(keys[i]);
}

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET") return;

  // The page itself: newest when online, cached copy when offline.
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then(r => { const copy = r.clone(); caches.open(SHELL).then(c => c.put("index.html", copy)); return r; })
      .catch(() => caches.match("index.html").then(r => r || caches.match("./"))));
    return;
  }
  // Dinosaur data: answer from cache at once, refresh in the background.
  if (url.origin === location.origin && url.pathname.includes("/data/") && url.pathname.endsWith(".json")) {
    const key = new Request(url.origin + url.pathname);
    e.respondWith(caches.open(SHELL).then(async c => {
      const hit = await c.match(key);
      const fresh = fetch(req).then(r => { if (r.ok) c.put(key, r.clone()); return r; }).catch(() => hit);
      return hit || fresh;
    }));
    return;
  }
  // Fonts: cache forever.
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    e.respondWith(caches.open(FONTS).then(async c => (await c.match(req)) ||
      fetch(req).then(r => { c.put(req, r.clone()); return r; })));
    return;
  }
  // Pictures from Wikimedia: keep the most recent ones for offline use.
  if (url.hostname === "upload.wikimedia.org") {
    e.respondWith(caches.open(PICS).then(async c => {
      const hit = await c.match(req.url);
      if (hit) return hit;
      try {
        const r = await fetch(req.url, { mode: "cors", credentials: "omit" });
        if (r.ok) { await c.put(req.url, r.clone()); trim(PICS, MAX_PICS); }
        return r;
      } catch (_) {
        return fetch(req);   // no CORS: still show it, just don't keep it
      }
    }));
    return;
  }
  // Everything else from this site: cache first.
  if (url.origin === location.origin) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
      if (r.ok) { const copy = r.clone(); caches.open(SHELL).then(c => c.put(req, copy)); }
      return r;
    })));
  }
});
