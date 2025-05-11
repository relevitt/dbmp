self.addEventListener("install", (event) => {
  // Skip waiting to immediately activate the new service worker
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Claim clients immediately to ensure updates are loaded instantly
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
