// Service Worker for GhostHub PWA
const CACHE_NAME = 'ghosthub-v2';
const CORE_ASSETS = [
  '/',
  '/static/css/base.css',
  '/static/css/components.css',
  '/static/css/streaming-layout.css',
  '/static/js/main.js',
  '/static/icons/Ghosthub192.png'
];

// Install event - triggered when the service worker is installed
self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(CORE_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate event - triggered when the service worker is activated
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activated');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => clients.claim())
  );
});

// Fetch event - triggered when the app makes a network request
self.addEventListener('fetch', (event) => {
  // Only cache GET requests
  if (event.request.method !== 'GET') return;

  // For core assets, try cache then network
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).then((fetchResponse) => {
        // Don't cache media/API responses in sw.js (handled by app)
        if (event.request.url.includes('/media/') || event.request.url.includes('/api/')) {
          return fetchResponse;
        }

        return caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, fetchResponse.clone());
          return fetchResponse;
        });
      });
    }).catch(() => {
      return fetch(event.request);
    })
  );
});
