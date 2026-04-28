/**
 * Service Worker - Kanban PWA
 * Cache de assets estáticos e funcionamento offline
 */

const CACHE_NAME = 'linhamestre-kanban-v1';
const ASSETS_TO_CACHE = [
    '/static/css/styles.css',
    '/static/js/kanban-cache.js',
    '/static/js/kanban-sync.js',
    '/static/img/logo.png',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
];

// Instalação do Service Worker
self.addEventListener('install', (event) => {
    console.log('[SW] Instalando Service Worker...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Cache aberto, adicionando assets...');
                return cache.addAll(ASSETS_TO_CACHE);
            })
            .then(() => {
                console.log('[SW] Assets em cache!');
                return self.skipWaiting();
            })
            .catch((err) => {
                console.error('[SW] Erro ao cachear assets:', err);
            })
    );
});

// Ativação do Service Worker
self.addEventListener('activate', (event) => {
    console.log('[SW] Ativando Service Worker...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[SW] Removendo cache antigo:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Service Worker ativado!');
            return self.clients.claim();
        })
    );
});

// Interceptação de requests
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Ignora requests de API (deixa passar direto)
    if (url.pathname.startsWith('/kanban/full-data') || 
        url.pathname.startsWith('/kanban/sync') ||
        url.pathname.startsWith('/api/')) {
        return;
    }
    
    // Cache-first strategy para assets estáticos
    event.respondWith(
        caches.match(request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                return fetch(request).then((response) => {
                    // Cachear apenas GET requests bem-sucedidos
                    if (request.method === 'GET' && response.status === 200) {
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(request, responseToCache);
                        });
                    }
                    return response;
                });
            })
            .catch(() => {
                // Offline fallback
                if (request.destination === 'document') {
                    return caches.match('/kanban');
                }
            })
    );
});

// Mensagens do cliente
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => caches.delete(cacheName))
                );
            })
        );
    }
});
