/**
 * Service Worker - Kanban PWA
 * Cache de assets estáticos e stale-while-revalidate para páginas
 */

const CACHE_VERSION = 'v11';
const CACHE_STATIC = `linhamestre-static-${CACHE_VERSION}`;
const CACHE_PAGES  = `linhamestre-pages-${CACHE_VERSION}`;
const CACHE_MEDIA  = `linhamestre-media-${CACHE_VERSION}`;
const CACHE_API    = `linhamestre-api-${CACHE_VERSION}`;
const KNOWN_CACHES = new Set([CACHE_STATIC, CACHE_PAGES, CACHE_MEDIA, CACHE_API]);
const CACHE_LIMITS = {
    [CACHE_STATIC]: 120,
    [CACHE_PAGES]: 20,
    [CACHE_MEDIA]: 350,
    [CACHE_API]: 300
};

// Limite de tamanho total em bytes (50MB por cache para evitar colapso)
const CACHE_SIZE_LIMITS = {
    [CACHE_STATIC]: 50 * 1024 * 1024,   // 50MB
    [CACHE_PAGES]: 20 * 1024 * 1024,    // 20MB
    [CACHE_MEDIA]: 100 * 1024 * 1024,   // 100MB
    [CACHE_API]: 50 * 1024 * 1024       // 50MB
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
// Mantemos apenas endpoints de escrita/estado dinâmico crítico.
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
    // URLs são hash-based (imutáveis). PDFs são ignorados de propósito:
    // respostas opaque (no-cors, cross-origin) não podem ser consumidas
    // pelo visualizador de PDF do Chrome, resultando em "página indisponível".
    // Para PDF deixamos o browser seguir o 302 do Flask direto para Supabase.
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
    // Evita abrir com HTML antigo (listas/cartões desatualizados) após mudanças.
    if (request.destination === 'document' && (url.pathname === '/kanban' || url.pathname === '/kanban/')) {
        event.respondWith(networkFirstStrategy(request, CACHE_PAGES));
        return;
    }

    // Páginas administrativas / de configuração: SEM cache (sempre rede)
    if (request.destination === 'document' && (url.pathname.startsWith('/kanban/listas') || url.pathname.startsWith('/listas'))) {
        return;
    }
    
    // Default: network only
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
        // Para /uploads/* usamos no-cors porque a rota faz 302 para Supabase
        // (cross-origin). Com no-cors recebemos uma resposta opaca que ainda
        // pode ser cacheada e servida de volta pelo SW.
        const init = isMedia
            ? { mode: 'no-cors', credentials: 'include', redirect: 'follow' }
            : { redirect: 'follow' };
        const netRequest = isMedia ? new Request(request.url, init) : request;
        const response = await fetch(netRequest, isMedia ? undefined : init);

        if (response && (response.ok || response.type === 'opaque' || response.type === 'opaqueredirect')) {
            try {
                cache.put(request, response.clone());
                await enforceCacheLimit(cacheName);
            } catch (err) {
                // Cache.put pode rejeitar respostas opaqueredirect; ignoramos.
            }
        }
        return response;
    } catch (e) {
        console.warn('[SW] Falha na rede:', request.url, e && e.message);
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

    const networkFetchPromise = fetch(request)
        .then((response) => {
            if (response && response.ok) {
                cache.put(request, response.clone());
                enforceCacheLimit(cacheName);
                console.log('[SW] Cache da página atualizado:', request.url);
            }
            return response;
        })
        .catch((error) => {
            console.error('[SW] Falha ao buscar página:', request.url, error);
            return null;
        });
    
    if (cached) {
        // Atualiza em background, mas responde imediatamente do cache
        networkFetchPromise.catch(() => null);
        console.log('[SW] Servindo do cache:', request.url);
        return cached;
    }
    
    // Primeira vez: esperar a rede, com fallback seguro
    console.log('[SW] Primeira visita, buscando da rede:', request.url);
    const networkResponse = await networkFetchPromise;
    if (networkResponse) {
        return networkResponse;
    }

    return new Response('Offline', {
        status: 503,
        headers: {
            'Content-Type': 'text/plain; charset=utf-8'
        }
    });
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
            await enforceCacheLimit(cacheName);
            console.log('[SW] Network-first (rede):', request.url);
        }
        return response;
    } catch (error) {
        const cached = await cache.match(request);
        if (cached) {
            console.log('[SW] Network-first fallback (cache):', request.url);
            return cached;
        }

        return new Response('Offline', {
            status: 503,
            headers: {
                'Content-Type': 'text/plain; charset=utf-8'
            }
        });
    }
}

async function enforceCacheLimit(cacheName) {
    const countLimit = CACHE_LIMITS[cacheName];
    const sizeLimit = CACHE_SIZE_LIMITS[cacheName];
    if (!countLimit && !sizeLimit) return;

    const cache = await caches.open(cacheName);
    const keys = await cache.keys();

    // Primeiro, respeitar limite de contagem
    if (countLimit && keys.length > countLimit) {
        const excess = keys.length - countLimit;
        for (let i = 0; i < excess; i++) {
            await cache.delete(keys[i]);
        }
        // Recarregar keys após deletar por contagem
        keys.length = 0;
        (await cache.keys()).forEach(k => keys.push(k));
    }

    // Segundo, respeitar limite de tamanho total
    if (sizeLimit) {
        let totalSize = 0;
        const entries = [];

        for (const request of keys) {
            const response = await cache.match(request);
            if (response) {
                const blob = await response.blob();
                const size = blob.size;
                totalSize += size;
                entries.push({ request, size, response });
            }
        }

        if (totalSize > sizeLimit) {
            // Ordenar por tamanho (maior primeiro) para liberar espaço rápido
            entries.sort((a, b) => b.size - a.size);

            let currentSize = totalSize;
            for (const entry of entries) {
                if (currentSize <= sizeLimit) break;
                await cache.delete(entry.request);
                currentSize -= entry.size;
            }
        }
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
