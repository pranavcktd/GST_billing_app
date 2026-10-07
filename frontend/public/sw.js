// Service worker: installable app + works offline.
// - Static files (/_next/static, icons): cache first (they never change once built).
// - App pages and their client-side navigation data: network first, last copy when offline.
// - /api is never cached here — the app keeps its own small offline copy of the data it needs to bill
//   (see src/lib/offline.ts) and uploads bills saved offline when the connection returns.
const STATIC = "gb-static-v2";
const PAGES = "gb-pages-v2";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== STATIC && k !== PAGES).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

function cacheFirst(req) {
  return caches.match(req).then(
    (hit) =>
      hit ||
      fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(STATIC).then((c) => c.put(req, copy));
        }
        return res;
      }),
  );
}

function networkFirst(req) {
  return fetch(req)
    .then((res) => {
      if (res.ok && res.type === "basic") {
        const copy = res.clone();
        caches.open(PAGES).then((c) => c.put(req, copy));
      }
      return res;
    })
    .catch(() =>
      caches.match(req).then((hit) => {
        if (hit) return hit;
        if (req.mode === "navigate") return caches.match("/dashboard").then((d) => d || caches.match("/"));
        return Response.error();
      }),
    );
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;
  if (url.pathname.startsWith("/_next/static/") || /^\/(icon|apple-touch-icon)[\w-]*\.(svg|png)$/.test(url.pathname) || url.pathname.startsWith("/fonts/")) {
    e.respondWith(cacheFirst(e.request));
    return;
  }
  if (url.pathname.startsWith("/_next/")) return; // dev / image endpoints
  e.respondWith(networkFirst(e.request));
});
