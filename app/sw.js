// Version: 2.2.0 - Cache Busted 2026-09-29
importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js');

const CACHE_VER = 'v2.2.0';

if (workbox) {
  console.log(`[SW] Workbox is loaded (${CACHE_VER})`);

  workbox.core.skipWaiting();
  workbox.core.clientsClaim();

  // Cache static assets (CSS, JS, Fonts)
  workbox.routing.registerRoute(
    ({request}) => request.destination === 'style' || request.destination === 'script' || request.destination === 'font',
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: `static-resources-${CACHE_VER}`,
    })
  );

  // Cache API Responses (Answers, Translations, Search)
  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/api/'),
    new workbox.strategies.NetworkFirst({
      cacheName: 'api-cache',
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 100,
          maxAgeSeconds: 24 * 60 * 60, // 24 hours
        }),
      ],
    })
  );

  // Cache HTML Pages
  workbox.routing.registerRoute(
    ({request}) => request.mode === 'navigate',
    new workbox.strategies.NetworkFirst({
      cacheName: 'pages-cache',
    })
  );

  // Cache Audio files from external sources
  workbox.routing.registerRoute(
    ({url}) => url.href.includes('mp3quran.net') || url.pathname.endsWith('.mp3'),
    new workbox.strategies.CacheFirst({
      cacheName: 'audio-cache',
      plugins: [
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 50,
          maxAgeSeconds: 7 * 24 * 60 * 60, // 1 week
        }),
      ],
    })
  );
} else {
  console.log(`[SW] Workbox didn't load`);
}
