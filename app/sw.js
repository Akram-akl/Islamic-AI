const CACHE_NAME = 'islamic-ai-v2';
const ASSETS_TO_CACHE = [
  '/',
  'index.html',
  'manifest.json',
  'icon.svg'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Ignore non-http requests (e.g., chrome-extension://)
  if (!e.request.url.startsWith('http')) return;

  // للـ API requests: Network first
  if (e.request.url.includes('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => {
        return new Response(JSON.stringify({
          error: "لا يتوفر اتصال بالإنترنت حالياً",
          offline: true
        }), { headers: { "Content-Type": "application/json" } });
      })
    );
    return;
  }

  // للأصول الثابتة: Cache first مع Network fallback
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      return cachedResponse || fetch(e.request).then((networkResponse) => {
        return caches.open(CACHE_NAME).then((cache) => {
          if (e.request.method === 'GET' && networkResponse && networkResponse.status === 200 && e.request.url.startsWith('http')) {
            cache.put(e.request, networkResponse.clone());
          }
          return networkResponse;
        });
      });
    }).catch(() => fetch(e.request))
  );
});
