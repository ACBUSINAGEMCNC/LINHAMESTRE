/**
 * Service Worker - Kanban PWA
 * Cache de assets estáticos e stale-while-revalidate para páginas
 */

const CACHE_VERSION = 'v4';
const CACHE_STATIC = `linhamestre-static-${CACHE_VERSION}`;
const CACHE_PAGES  = `linhamestre-pages-${CACHE_VERSION}`;

// Assets estáticos para pré-cachear na instalação
const STATIC_ASSETS = [
    '/manifest.json',
    '/static/css/kanban-pwa.css',
    '/static/css/kanban-sortable.css',
    '/static/js/kanban-cache.js',
    '/static/js/kanban-sync.js',
    '/static/js/kanban-pwa.js',
    '/static/js/kanban-card-click.js'
];

// URLs que NUNCA devem ser cacheadas (sempre vai ao servidor)
const BYPASS_PATTERNS = [
    '/kanban/full-data',
    '/kanban/sync',
    '/kanban/mover',
    '/apontamento/',
    '/api/',
    '/auth/',
    '/uploads/'
];

// Instalação do Service Worker
self.addEventListener('install', (event) => {
    console.log('[SW] Instalando Service Worker...');
    event.waitUntil(
        caches.open(CACHE_STATIC)
            .then((cache) => {
                console.log('[SW] Cacheando assets estáticos...');
                // addAll falha se qualquer arquivo não existir - usar add individual
                return Promise.allSettled(
                    STATIC_ASSETS.map(url => cache.add(url).catch(e => console.warn('[SW] Não cacheou:', url)))
                );
            })
            .then(() => {
                console.log('[SW] Instalação concluída!');
                return self.skipWaiting();
            })
    );
});

// Ativação - limpar caches antigos
self.addEventListener('activate', (event) => {
    console.log('[SW] Ativando Service Worker...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((name) => {
                    if (name !== CACHE_STATIC && name !== CACHE_PAGES) {
                        console.log('[SW] Removendo cache antigo:', name);
                        return caches.delete(name);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Service Worker ativo!');
            return self.clients.claim();
        })
    );
});

// Interceptação de requests
self.addEventListener('fetch', (event) => {
    const { request } = event;
    
    // Apenas GET
    if (request.method !== 'GET') return;
    
    const url = new URL(request.url);
    
    // Ignorar outros domínios (CDN externo, etc)
    if (url.origin !== self.location.origin) return;
    
    // Bypass: URLs que sempre vão ao servidor
    const shouldBypass = BYPASS_PATTERNS.some(p => url.pathname.startsWith(p));
    if (shouldBypass) return;
    
    // Estratégia 1: CACHE-FIRST para assets estáticos
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(cacheFirstStrategy(request, CACHE_STATIC));
        return;
    }
    
    // Estratégia 2: STALE-WHILE-REVALIDATE para páginas HTML (inclui /kanban)
    if (request.destination === 'document' || url.pathname === '/kanban' || url.pathname.startsWith('/kanban')) {
        event.respondWith(staleWhileRevalidate(request, CACHE_PAGES));
        return;
    }
    
    // Default: network only
});

/**
 * Cache-First: serve do cache, busca da rede só se não tiver
 */
async function cacheFirstStrategy(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) return cached;
    
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (e) {
        console.error('[SW] Falha na rede:', request.url);
        return new Response('Offline', { status: 503 });
    }
}

/**
 * Stale-While-Revalidate: serve do cache IMEDIATAMENTE, atualiza em background
 * Isso faz a página carregar INSTANTANEAMENTE na segunda visita!
 */
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    
    // Buscar versão atualizada em background (sem await)
    const networkFetch = fetch(request).then((response) => {
        if (response.ok) {
            cache.put(request, response.clone());
            console.log('[SW] Cache da página atualizado:', request.url);
        }
        return response;
    }).catch(() => null);
    
    if (cached) {
        // Servir do cache imediatamente (carregamento INSTANTÂNEO!)
        console.log('[SW] Servindo do cache:', request.url);
        return cached;
    }
    
    // Primeira vez: esperar a rede
    console.log('[SW] Primeira visita, buscando da rede:', request.url);
    return networkFetch;
}

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
