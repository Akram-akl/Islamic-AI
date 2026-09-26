const CACHE_NAME = 'islamic-ai-v5';
const ASSETS_TO_CACHE = [
  '/',
  'index.html',
  'manifest.json',
  'icon.svg'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  // Ignore non-http requests (e.g. chrome-extension://)
  if (e.request.method !== 'GET' || !e.request.url.startsWith('http')) return;

  // Network-First for HTML/document/index.html to ensure live updates without stale cache
  if (e.request.mode === 'navigate' || e.request.destination === 'document' || e.request.url.endsWith('index.html') || e.request.url.endsWith('/')) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
          }
          return res;
        })
        .catch(() => caches.match(e.request).then((cached) => cached || caches.match('/index.html') || caches.match('/')))
    );
    return;
  }

  // Network-first for static scripts and data, fallback to cache
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
