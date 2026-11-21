// Service Worker von E-Giant (Repo/Paket/Dienst heißen weiterhin edgefinder).
// - App-Shell: gehashte Dateien unter /assets (unveränderlich) werden beim ersten Abruf gespeichert,
//   Seiten (Navigation) gehen zuerst ans Netz und fallen offline auf die gespeicherte index.html zurück.
// - API: immer zuerst ans Netz (keine alten Daten, solange der Server antwortet). Nur ohne Verbindung
//   gibt es die letzte Antwort (max. 24 h alt) mit Header x-ef-cached-at; die App zeigt dann einen Hinweis.
// - Konto (/api/me*): NIE zwischenspeichern, immer network-only (Datenschutz zwischen Konten auf demselben
//   Gerät). Beim Abmelden/Kontowechsel leert die App zusätzlich alle `ef-api-*`-Caches (lib/account.ts).
// - Push: nur Struktur (Empfang + Klick); gesendet wird derzeit nichts.
// Der Platzhalter unten wird beim Build (scripts/sw-build-id.mjs) durch einen Hash der Build-Dateien ersetzt.
const VERSION = "__BUILD_ID__";
const SHELL = `ef-shell-${VERSION}`;
const API = `ef-api-${VERSION}`;
const API_MAX_AGE_MS = 24 * 60 * 60 * 1000;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(["/", "/manifest.webmanifest", "/favicon.svg"])));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => ![SHELL, API].includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function apiNetworkFirst(request) {
  const cache = await caches.open(API);
  try {
    const response = await fetch(request);
    if (response.ok) {
      const headers = new Headers(response.headers);
      headers.set("x-ef-stored-at", String(Date.now()));
      const body = await response.clone().blob();
      await cache.put(request, new Response(body, { status: 200, headers }));
    }
    return response;
  } catch (error) {
    const stored = await cache.match(request);
    const storedAt = stored && Number(stored.headers.get("x-ef-stored-at"));
    if (!stored || !storedAt || Date.now() - storedAt > API_MAX_AGE_MS) throw error;
    const headers = new Headers(stored.headers);
    headers.set("x-ef-cached-at", new Date(storedAt).toISOString());
    return new Response(await stored.blob(), { status: 200, headers });
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname === "/api/me" || url.pathname.startsWith("/api/me/")) {
    return; // kein respondWith: der Browser fragt direkt das Netz (und speichert nichts)
  }
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(apiNetworkFirst(request));
  } else if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.open(SHELL).then(async (cache) => {
        const hit = await cache.match(request);
        // Nur echte Dateien aus dem Cache: eine als index.html gespeicherte Antwort wäre ein toter Chunk.
        if (hit && !(hit.headers.get("content-type") || "").includes("text/html")) return hit;
        const response = await fetch(request);
        // Fehlende Dateien (404 nach einem Deploy) und HTML-Antworten nie speichern.
        if (response.ok && !(response.headers.get("content-type") || "").includes("text/html")) cache.put(request, response.clone());
        return response;
      }),
    );
  } else if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.open(SHELL).then((cache) => cache.match("/")).then((hit) => hit ?? Response.error())),
    );
  }
});

// --- Push (Vorbereitung): zeigt eine Meldung, falls künftig eine ankommt ---
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "E-Giant", {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      data: { url: data.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((windows) => {
      const open = windows.find((w) => "focus" in w);
      return open ? open.navigate(target).then((w) => w && w.focus()) : self.clients.openWindow(target);
    }),
  );
});
