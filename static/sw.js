/**
 * Service Worker - Kanban PWA
 * Cache de assets estáticos e stale-while-revalidate para páginas
 */

const CACHE_VERSION = 'v12';
const CACHE_STATIC = `linhamestre-static-${CACHE_VERSION}`;
const CACHE_PAGES  = `linhamestre-pages-${CACHE_VERSION}`;
const CACHE_MEDIA  = `linhamestre-media-${CACHE_VERSION}`;
const CACHE_API    = `linhamestre-api-${CACHE_VERSION}`;
const KNOWN_CACHES = new Set([CACHE_STATIC, CACHE_PAGES, CACHE_MEDIA, CACHE_API]);

// Limites de quantidade de itens por cache para evitar lentidão e bloat.
// Nota: Respostas opacas (Supabase) são "padronizadas" para ~7MB cada pelo browser.
// 100 itens de média ≈ 700MB de quota real, evitando estouro de 2GB.
const CACHE_LIMITS = {
    [CACHE_STATIC]: 120,
    [CACHE_PAGES]: 20,
    [CACHE_MEDIA]: 100,
    [CACHE_API]: 150
};

// Assets estáticos para pré-cachear na instalação
const STATIC_ASSETS = [
    '/static/css/kanban-pwa.css',
    '/static/css/kanban-sortable.css',
    '/static/js/kanban-cache.js',
    '/static/js/kanban-sync.js',
    '/static/js/kanban-pwa.js',
    '/static/js/kanban-card-click.js'
];

// URLs que NUNCA devem ser cacheadas (sempre vão ao servidor)
const BYPASS_PATTERNS = [
    '/kanban/full-data',
    '/kanban/sync',
    '/kanban/mover',
    '/kanban/reordenar',
    '/kanban/listas',
    '/listas/reordenar',
    '/kanban/finalizar',
    '/kanban/atualizar-tempo-real',
    '/kanban/enviar-para',
    '/cartao-fantasma/criar',
    '/cartao-fantasma/mover',
    '/cartao-fantasma/remover',
    '/apontamento/registrar',
    '/apontamento/validar-codigo',
    '/apontamento/status-ativos',
    '/apontamento/status-cronometro',
    '/auth/'
];

// GET endpoints de detalhes/apontamento que podem ser servidos via SWR.
const SWR_API_PATTERNS = [
    '/kanban/detalhes/',
    '/cartao-fantasma/detalhes/',
    '/apontamento/os/',
    '/apontamento/item/',
    '/apontamento/detalhes/',
    '/apontamento/quantidades-por-trabalho/'
];

// Instalação do Service Worker
self.addEventListener('install', (event) => {
    console.log('[SW] Instalando Service Worker...');
    event.waitUntil(
        caches.open(CACHE_STATIC)
            .then((cache) => {
                console.log('[SW] Cacheando assets estáticos...');
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
                    if (!KNOWN_CACHES.has(name)) {
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

    // Estratégia 2: CACHE-FIRST para IMAGENS em /uploads/*
    if (url.pathname.startsWith('/uploads/')) {
        const isPdf = /\.pdf(\?|$)/i.test(url.pathname);
        if (!isPdf) {
            event.respondWith(cacheFirstStrategy(request, CACHE_MEDIA));
        }
        return;
    }

    // Estratégia 3: STALE-WHILE-REVALIDATE para detalhes/apontamento (GET)
    const isSwrApi = SWR_API_PATTERNS.some(p => url.pathname.startsWith(p));
    if (isSwrApi) {
        event.respondWith(staleWhileRevalidate(request, CACHE_API));
        return;
    }
    
    // Estratégia 4: NETWORK-FIRST para a página principal do Kanban
    if (request.destination === 'document' && (url.pathname === '/kanban' || url.pathname === '/kanban/')) {
        event.respondWith(networkFirstStrategy(request, CACHE_PAGES));
        return;
    }

    // Páginas administrativas / de configuração: SEM cache (sempre rede)
    if (request.destination === 'document' && (url.pathname.startsWith('/kanban/listas') || url.pathname.startsWith('/listas'))) {
        return;
    }
});

/**
 * Cache-First: serve do cache, busca da rede só se não tiver
 */
async function cacheFirstStrategy(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    if (cached) return cached;

    const url = new URL(request.url);
    const isMedia = url.pathname.startsWith('/uploads/');

    try {
        const init = isMedia
            ? { mode: 'no-cors', credentials: 'include', redirect: 'follow' }
            : { redirect: 'follow' };
        const netRequest = isMedia ? new Request(request.url, init) : request;
        const response = await fetch(netRequest, isMedia ? undefined : init);

        if (response && (response.ok || response.type === 'opaque' || response.type === 'opaqueredirect')) {
            try {
                cache.put(request, response.clone());
                // Prunagem rápida apenas por contagem (O(1) amortizado)
                enforceCacheLimit(cacheName);
            } catch (err) {}
        }
        return response;
    } catch (e) {
        console.warn('[SW] Falha na rede:', request.url, e && e.message);
        return new Response('Offline', { status: 503 });
    }
}

/**
 * Stale-While-Revalidate: serve do cache IMEDIATAMENTE, atualiza em background
 */
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);

    const networkFetchPromise = fetch(request)
        .then((response) => {
            if (response && response.ok) {
                cache.put(request, response.clone());
                enforceCacheLimit(cacheName);
            }
            return response;
        })
        .catch((error) => {
            console.error('[SW] Falha ao buscar página:', request.url, error);
            return null;
        });
    
    if (cached) {
        networkFetchPromise.catch(() => null);
        return cached;
    }
    
    const networkResponse = await networkFetchPromise;
    if (networkResponse) {
        return networkResponse;
    }

    return new Response('Offline', { status: 503 });
}

/**
 * Network-First: prioriza rede e usa cache apenas como fallback
 */
async function networkFirstStrategy(request, cacheName) {
    const cache = await caches.open(cacheName);

    try {
        const response = await fetch(request);
        if (response && response.ok) {
            cache.put(request, response.clone());
            enforceCacheLimit(cacheName);
        }
        return response;
    } catch (error) {
        const cached = await cache.match(request);
        if (cached) return cached;
        return new Response('Offline', { status: 503 });
    }
}

/**
 * Otimizado: Remove itens antigos por contagem.
 * Evita ler blobs ou calcular tamanhos (lento e impreciso para opaque responses).
 */
async function enforceCacheLimit(cacheName) {
    const limit = CACHE_LIMITS[cacheName];
    if (!limit) return;

    try {
        const cache = await caches.open(cacheName);
        const keys = await cache.keys();
        if (keys.length > limit) {
            const excess = keys.length - limit;
            for (let i = 0; i < excess; i++) {
                await cache.delete(keys[i]);
            }
            console.log(`[SW] Limpeza no cache ${cacheName}: removidos ${excess} itens.`);
        }
    } catch (e) {
        console.warn('[SW] Erro ao limpar cache:', e);
    }
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
