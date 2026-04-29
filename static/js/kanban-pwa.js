/**
 * Kanban PWA Integration
 * Integra Service Worker, Cache e Sync no Kanban existente
 */

class KanbanPWA {
    constructor() {
        this.isLoading = false;
        this.hasCache = false;
        this.loadingProgress = 0;
        this.initialCacheChecked = false;
        this.bootstrap = window.KANBAN_BOOTSTRAP || { frontend_shell: false, listas: [] };
        // Flags de controle de precache
        this._precacheDone = false;
        this._precacheRunning = false;
        this._precacheCompleteCalled = false;
    }
    
    /**
     * Inicializa o PWA
     */
    async init() {
        console.log('[PWA] Inicializando Kanban PWA em modo background...');
        console.log('[PWA] O Kanban tradicional continuará funcionando normalmente.');
        console.log('[PWA] Cache e sync serão feitos em background para melhorar próximos acessos.');
        
        // Registrar Service Worker
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
                console.log('[PWA] Service Worker registrado:', registration);

                // Forçar ativação imediata do novo SW se houver um waiting
                // Isso evita que o usuário precise recarregar manualmente
                if (registration.waiting) {
                    console.log('[PWA] Novo SW esperando, ativando...');
                    registration.waiting.postMessage({ type: 'SKIP_WAITING' });
                }

                // Se um novo SW for instalado, ativar imediatamente
                registration.addEventListener('updatefound', () => {
                    console.log('[PWA] Novo SW encontrado, instalando...');
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            console.log('[PWA] Novo SW instalado, ativando...');
                            newWorker.postMessage({ type: 'SKIP_WAITING' });
                        }
                    });
                });

                // Recarregar quando o novo SW for ativado
                navigator.serviceWorker.addEventListener('controllerchange', () => {
                    console.log('[PWA] SW ativado, recarregando página...');
                    window.location.reload();
                });
            } catch (error) {
                console.error('[PWA] Erro ao registrar Service Worker:', error);
            }
        }
        
        // Inicializar cache
        await window.kanbanCache.init();

        const cached = await window.kanbanCache.getAll();
        this.hasCache = Boolean(cached?.listas && cached.listas.length > 0);
        this.initialCacheChecked = true;

        if (!this.hasCache) {
            this.showLoading();
            this.updateLoadingProgress(15, 'Preparando cache local do Kanban...');
        }
        
        // Iniciar sincronização em background
        await window.kanbanSync.start((event) => {
            this.handleSyncEvent(event);
        });
    }
    
    /**
     * Trata eventos de sincronização
     */
    handleSyncEvent(event) {
        console.log('[PWA] Evento de sync:', event.type);
        
        switch (event.type) {
            case 'cache_loaded':
                this.hasCache = true;
                if (this.bootstrap.frontend_shell) {
                    this.renderKanban(event.data);
                }
                // Não esconde loading ainda — espera pré-cache terminar
                console.log('[PWA] Cache carregado! Aguardando pré-cache...');
                this.updateSyncIndicator('synced');
                // Preenche buracos de mídia/detalhes em background (não bloqueia UI).
                if (!this._precacheDone) {
                    this.precacheEverything(event.data, { onlyMissing: true, onComplete: () => this.onPrecacheComplete('cache_loaded') });
                }
                break;

            case 'full_sync_complete':
                if (this.bootstrap.frontend_shell) {
                    this.updateLoadingProgress(65, 'Montando Kanban local...');
                    this.renderKanban(event.data);
                }
                this.updateLoadingProgress(80, 'Pré-aquecendo cache...');
                console.log('[PWA] Full sync completo! Pré-aquecendo cache...');
                this.updateSyncIndicator('synced');
                // Primeira carga: baixa tudo (detalhes, imagens, apontamentos) em background.
                if (!this._precacheDone) {
                    this.precacheEverything(event.data, { onlyMissing: false, onComplete: () => this.onPrecacheComplete('full_sync') });
                }
                break;
                
            case 'incremental_update':
                if (this.bootstrap.frontend_shell) {
                    this.applyIncrementalUpdate(event.delta);
                }
                // Atualização incremental - mostrar notificação
                if (event.delta.has_changes) {
                    const totalChanges = (event.delta.updated_cards?.length || 0) + 
                                       (event.delta.new_cards?.length || 0) + 
                                       (event.delta.deleted_cards?.length || 0);
                    if (totalChanges > 0) {
                        this.showNotification(`${totalChanges} mudança(s) detectada(s). Recarregue para ver.`, 'info');
                    }
                }
                this.updateSyncIndicator('synced');
                break;
                
            case 'sync_error':
                this.hideLoading();
                console.error('[PWA] Erro de sync:', event.error);
                break;
        }
    }
    
    /**
     * Renderiza o Kanban com dados do cache
     */
    renderKanban(data) {
        console.log('[PWA] Renderizando Kanban...', data);
        
        const container = document.getElementById('kanban-container');
        if (!container) {
            console.error('[PWA] Container do Kanban não encontrado!');
            return;
        }
        
        container.innerHTML = '';

        const listas = data.listas || this.bootstrap.listas || [];
        const cartoes = [...(data.cartoes || [])].sort((a, b) => (a.posicao || 0) - (b.posicao || 0));

        for (const lista of listas) {
            const listaEl = this.createListaElement(lista, cartoes.filter(c => c.lista_id === lista.id));
            container.appendChild(listaEl);
        }

        this.afterRender();
        
        this.updateSyncIndicator('synced');
    }
    
    /**
     * Cria elemento de lista
     */
    createListaElement(lista, cartoesDaLista) {
        const div = document.createElement('div');
        div.className = 'kanban-column';
        div.dataset.listaId = lista.id;
        div.id = `column-${this.slugify(lista.nome)}`;
        
        div.innerHTML = `
            <div class="kanban-column-header">
                <span>${lista.nome}</span>
                <span class="column-counter">${cartoesDaLista.length}</span>
            </div>
            <div class="kanban-column-body" data-lista="${this.escapeHtml(lista.nome)}"></div>
        `;

        const body = div.querySelector('.kanban-column-body');
        for (const cartao of cartoesDaLista) {
            body.appendChild(this.createCartaoElement(cartao, lista.nome));
        }

        return div;
    }

    createCartaoElement(cartao, listaNome) {
        const div = document.createElement('div');
        const isFantasma = Boolean(cartao.is_fantasma);
        div.className = `kanban-card${isFantasma ? ' fantasma' : ''}`;
        div.dataset.search = cartao.search_text || cartao.numero || '';
        div.dataset.ordemId = cartao.ordem_id || cartao.id;
        if (isFantasma) {
            div.dataset.cartaoId = cartao.fantasma_id || cartao.id;
        }

        const itensHtml = (cartao.itens || []).map((item) => `
            <li class="os-item">
                <span class="os-item-name">${this.escapeHtml(item.nome || 'Item')}</span>
                <span class="badge rounded-pill bg-primary os-item-qty">${this.escapeHtml(String(item.quantidade || 0))}</span>
            </li>
        `).join('');

        const moveOptions = (this.bootstrap.listas || [])
            .filter((nome) => nome !== listaNome && nome !== 'Entrada')
            .map((nome) => `
                <li><a class="dropdown-item btn-mover-visual" href="#" data-ordem-id="${cartao.ordem_id || cartao.id}" data-lista-destino="${this.escapeHtml(nome)}">
                    <i class="fas fa-arrow-right me-2 text-primary"></i>${this.escapeHtml(nome)}
                </a></li>
            `).join('');

        const apontamentoHtml = (!isFantasma && !['Entrada', 'Expedição'].includes(listaNome)) ? `
            <div class="apontamento-buttons mt-2 pt-2 border-top">
                <div class="row g-1">
                    <div class="col-6"><button class="btn btn-outline-primary btn-sm w-100 apontamento-btn" data-acao="inicio_setup" data-ordem-id="${cartao.ordem_id || cartao.id}" onclick="iniciarApontamentoSetup(this.dataset.ordemId);"><i class="fas fa-play"></i> Setup</button></div>
                    <div class="col-6"><button class="btn btn-outline-info btn-sm w-100 apontamento-btn" data-acao="fim_setup" data-ordem-id="${cartao.ordem_id || cartao.id}" onclick="finalizarSetup(this.dataset.ordemId);"><i class="fas fa-stop"></i> Fim Setup</button></div>
                    <div class="col-6"><button class="btn btn-outline-success btn-sm w-100 apontamento-btn" data-acao="inicio_producao" data-ordem-id="${cartao.ordem_id || cartao.id}" onclick="iniciarApontamentoProducao(this.dataset.ordemId);"><i class="fas fa-cogs"></i> Produção</button></div>
                    <div class="col-6"><button class="btn btn-outline-warning btn-sm w-100 apontamento-btn" data-acao="pausa" data-ordem-id="${cartao.ordem_id || cartao.id}" onclick="pausarApontamento(this.dataset.ordemId);"><i class="fas fa-pause"></i> Pausa</button></div>
                    <div class="col-12"><button class="btn btn-outline-danger btn-sm w-100 apontamento-btn" data-acao="stop" data-ordem-id="${cartao.ordem_id || cartao.id}" onclick="pararApontamento(this.dataset.ordemId);"><i class="fas fa-stop"></i> Stop</button></div>
                </div>
            </div>
        ` : '';

        div.innerHTML = isFantasma ? `
            <div class="kanban-card-header">
                <div class="card-header-main">
                    <div class="drag-handle"><i class="fas fa-grip-lines"></i></div>
                    <div class="fantasma-info" style="cursor: pointer">
                        <strong>${this.escapeHtml(cartao.numero || '')}</strong>
                        <br><small><i class="fas fa-cog"></i> ${this.escapeHtml(cartao.trabalho_nome || 'Fantasma')}</small>
                    </div>
                </div>
            </div>
            <div class="kanban-card-body">
                <div class="os-items mt-1">
                    <div class="small text-muted">Itens da OS</div>
                    <ul class="os-item-list list-unstyled mb-1">${itensHtml || '<li class="os-item"><span class="os-item-name">Sem itens</span></li>'}</ul>
                </div>
            </div>
        ` : `
            <div class="drag-handle" style="position: absolute; top: 8px; left: 8px; cursor: grab; z-index: 10;">
                <i class="fas fa-grip-lines"></i>
            </div>
            <div class="card-header-top">
                ${cartao.item_imagem_path ? `<img src="${this.escapeAttribute(cartao.item_imagem_path)}" class="item-thumb" alt="Imagem do item" loading="lazy">` : ''}
                <div class="card-header-actions">
                    ${cartao.item_id ? `<button class="btn btn-sm btn-outline-info" type="button" onclick="event.stopPropagation(); window.open('/folhas-processo-novas?item_id=${cartao.item_id}', '_blank')"><i class="fas fa-clipboard-list"></i> Folha</button>` : ''}
                    <button class="btn btn-sm btn-outline-purple btn-criar-fantasma-direto" type="button" data-ordem-id="${cartao.ordem_id || cartao.id}" data-lista-origem="${this.escapeHtml(listaNome)}" onclick="event.stopPropagation()"><i class="fas fa-ghost"></i> Fantasma</button>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false" onclick="event.stopPropagation()"><i class="fas fa-ellipsis-v"></i> Mover</button>
                        <ul class="dropdown-menu dropdown-menu-end kanban-dropdown-mover">${moveOptions}</ul>
                    </div>
                </div>
            </div>
            <div class="card-header-main">
                <button class="os-number-btn" data-ordem-id="${cartao.ordem_id || cartao.id}" onclick="event.stopPropagation();">${this.escapeHtml(cartao.numero || '')}</button>
            </div>
            <div class="kanban-card-body">
                <div class="os-items mt-1">
                    <div class="small text-muted">Itens da OS</div>
                    <ul class="os-item-list list-unstyled mb-1">${itensHtml || '<li class="os-item"><span class="os-item-name">Sem itens</span></li>'}</ul>
                </div>
                <div class="qtd-por-trabalho mt-1" id="qtd-por-trabalho-${cartao.ordem_id || cartao.id}">
                    <div class="small text-muted d-flex justify-content-between align-items-center">
                        <span>Quantidades por trabalho</span>
                        <span class="badge rounded-pill bg-secondary ultima-qtd" id="ultima-qtd-${cartao.ordem_id || cartao.id}">-</span>
                    </div>
                    <ul class="qpt-list list-unstyled mb-1">
                        <li class="qpt-item"><span class="qpt-label">-</span><span class="badge rounded-pill bg-secondary qpt-qty">-</span></li>
                    </ul>
                </div>
                ${apontamentoHtml}
                <div class="status-apontamento mt-1" id="status-${cartao.ordem_id || cartao.id}">
                    <small class="text-muted">Aguardando apontamento</small>
                    <span class="apontamento-timer" id="timer-${cartao.ordem_id || cartao.id}">00:00:00</span>
                </div>
            </div>
        `;

        return div;
    }

    afterRender() {
        if (typeof window.initializeKanbanSortable === 'function') {
            window.initializeKanbanSortable();
        }
        if (typeof window.initializeOSButtonClicks === 'function') {
            window.initializeOSButtonClicks();
        }
        if (typeof window.initializeKanbanEvents === 'function') {
            window.initializeKanbanEvents();
        }
        if (typeof window.aplicarFiltrosKanban === 'function') {
            window.aplicarFiltrosKanban();
        }
    }

    slugify(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/(^-|-$)/g, '');
    }

    escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    escapeAttribute(value) {
        return this.escapeHtml(value);
    }
    
    /**
     * Aplica atualização incremental
     */
    applyIncrementalUpdate(delta) {
        console.log('[PWA] Aplicando atualização incremental...', delta);
        
        // Atualizar cartões modificados
        if (delta.updated_cards && delta.updated_cards.length > 0) {
            for (const cartao of delta.updated_cards) {
                this.updateCartaoInDOM(cartao);
            }
            this.showNotification(`${delta.updated_cards.length} cartão(ões) atualizado(s)`, 'info');
        }
        
        // Remover cartões deletados
        if (delta.deleted_cards && delta.deleted_cards.length > 0) {
            for (const cartaoId of delta.deleted_cards) {
                this.removeCartaoFromDOM(cartaoId);
            }
        }
        
        // Adicionar novos cartões
        if (delta.new_cards && delta.new_cards.length > 0) {
            for (const cartao of delta.new_cards) {
                this.addCartaoToDOM(cartao);
            }
        }
        
        this.updateSyncIndicator('synced');
    }
    
    /**
     * Atualiza cartão no DOM
     */
    updateCartaoInDOM(cartao) {
        const cartaoEl = document.querySelector(`[data-cartao-id="${cartao.id}"]`);
        if (cartaoEl) {
            const newCartaoEl = this.createCartaoElement(cartao);
            cartaoEl.replaceWith(newCartaoEl);
        }
    }
    
    /**
     * Remove cartão do DOM
     */
    removeCartaoFromDOM(cartaoId) {
        const cartaoEl = document.querySelector(`[data-cartao-id="${cartaoId}"]`);
        if (cartaoEl) {
            cartaoEl.remove();
        }
    }
    
    /**
     * Adiciona cartão ao DOM
     */
    addCartaoToDOM(cartao) {
        const listaEl = document.querySelector(`[data-lista-id="${cartao.lista_id}"] .kanban-cards`);
        if (listaEl) {
            const cartaoEl = this.createCartaoElement(cartao);
            listaEl.appendChild(cartaoEl);
        }
    }
    
    /**
     * Abre detalhes do cartão
     */
    openCartaoDetails(cartao) {
        // Usar modal existente do Kanban
        if (window.abrirDetalhesCartao) {
            window.abrirDetalhesCartao(cartao.ordem_id || cartao.id);
        }
    }
    
    /**
     * Mostra tela de loading
     */
    showLoading() {
        this.isLoading = true;
        
        let loadingEl = document.getElementById('pwa-loading');
        if (!loadingEl) {
            loadingEl = document.createElement('div');
            loadingEl.id = 'pwa-loading';
            loadingEl.className = 'pwa-loading-overlay';
            loadingEl.innerHTML = `
                <div class="pwa-loading-content">
                    <div class="pwa-loading-spinner">
                        <i class="fas fa-sync fa-spin fa-3x"></i>
                    </div>
                    <h3>Carregando Kanban...</h3>
                    <div class="pwa-progress-bar">
                        <div class="pwa-progress-fill" id="pwa-progress-fill"></div>
                    </div>
                    <p id="pwa-loading-status">Inicializando...</p>
                </div>
            `;
            document.body.appendChild(loadingEl);
        }
        
        loadingEl.style.display = 'flex';
    }
    
    /**
     * Esconde tela de loading
     */
    hideLoading() {
        this.isLoading = false;
        
        const loadingEl = document.getElementById('pwa-loading');
        if (loadingEl) {
            loadingEl.style.display = 'none';
        }
    }
    
    /**
     * Atualiza progresso do loading
     */
    updateLoadingProgress(percent, status) {
        this.loadingProgress = percent;
        
        const fillEl = document.getElementById('pwa-progress-fill');
        if (fillEl) {
            fillEl.style.width = `${percent}%`;
        }
        
        const statusEl = document.getElementById('pwa-loading-status');
        if (statusEl) {
            statusEl.textContent = status;
        }
    }
    
    /**
     * Atualiza indicador de sync
     */
    updateSyncIndicator(status) {
        let indicator = document.getElementById('pwa-sync-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'pwa-sync-indicator';
            indicator.className = 'pwa-sync-indicator';
            document.body.appendChild(indicator);
        }
        
        switch (status) {
            case 'syncing':
                indicator.innerHTML = '<i class="fas fa-sync fa-spin"></i> Sincronizando...';
                indicator.className = 'pwa-sync-indicator syncing';
                break;
            case 'synced':
                indicator.innerHTML = '<i class="fas fa-check"></i> Atualizado';
                indicator.className = 'pwa-sync-indicator synced';
                setTimeout(() => {
                    indicator.style.display = 'none';
                }, 2000);
                break;
            case 'error':
                indicator.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Erro';
                indicator.className = 'pwa-sync-indicator error';
                break;
        }
        
        indicator.style.display = 'block';
    }
    
    /**
     * Mostra notificação
     */
    showNotification(message, type = 'info') {
        // Usar sistema de notificação existente se disponível
        if (window.showToast) {
            window.showToast(message, type);
            return;
        }
        
        // Fallback: criar notificação simples
        const notification = document.createElement('div');
        notification.className = `pwa-notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    /**
     * Força sincronização manual
     */
    async forceSync() {
        this.updateSyncIndicator('syncing');
        await window.kanbanSync.forceSync();
    }
    
    /**
     * Limpa cache
     */
    async clearCache() {
        if (confirm('Tem certeza que deseja limpar o cache? Isso irá recarregar todos os dados.')) {
            await window.kanbanCache.clear();
            window.location.reload();
        }
    }

    /**
     * Pré-aquece o cache do Service Worker baixando, em segundo plano,
     * todos os recursos que o usuário vai consultar (detalhes, imagens,
     * apontamentos). Similar ao WhatsApp Web: depois da primeira carga,
     * o app praticamente não precisa mais do servidor para leitura.
     *
     * @param {Object} data            Dados da sync (listas + cartoes)
     * @param {Object} [opts]
     * @param {boolean} [opts.onlyMissing=true]  Se true, só baixa o que não
     *                                           estiver no cache ainda.
     */
    async precacheEverything(data, opts = {}) {
        // Trava global: não iniciar se já está rodando ou já concluído
        if (this._precacheDone || this._precacheRunning) {
            console.log(`[PWA] Pré-cache ignorado (já ${this._precacheDone ? 'concluído' : 'rodando'})`);
            if (opts.onComplete && this._precacheDone) {
                opts.onComplete('success');
            } else if (opts.onComplete) {
                this._precacheCallback = opts.onComplete;
            }
            return;
        }

        this._precacheRunning = true;
        this._precacheCallback = opts.onComplete || null;

        const onlyMissing = opts.onlyMissing !== false;
        const cartoes = (data && data.cartoes) || [];
        if (!cartoes.length) {
            this._precaching = false;
            if (this._precacheCallback) this._precacheCallback();
            return;
        }

        const urls = this._collectPrecacheUrls(cartoes);
        console.log(`[PWA] Agendando pré-cache: ${urls.length} recursos (aguardando idle)`);

        // Timeout de segurança: se o pré-cache não terminar em 30s, esconde o loading
        // para não travar o usuário para sempre.
        this._precacheTimeout = setTimeout(() => {
            if (this._precaching) {
                console.warn('[PWA] Pré-cache timeout (30s), liberando UI.');
                this.onPrecacheComplete('timeout');
            }
        }, 30000);

        // Espera o navegador ficar ocioso + um pequeno delay antes de começar
        // para não colidir com a renderização inicial e cliques imediatos.
        const start = () => this._runPrecache(urls, onlyMissing);
        if ('requestIdleCallback' in window) {
            window.requestIdleCallback(() => setTimeout(start, 1500), { timeout: 4000 });
        } else {
            setTimeout(start, 2500);
        }
    }

    async _runPrecache(urls, onlyMissing) {
        try {
            let done = 0;
            const report = (label) => {
                done++;
                if (done % 20 === 0 || done === urls.length) {
                    console.log(`[PWA] Pré-cache: ${done}/${urls.length} (${label})`);
                    // Atualiza progresso no loading overlay
                    if (this.isLoading) {
                        const percent = Math.min(95, 80 + (done / urls.length) * 15);
                        this.updateLoadingProgress(percent, `Pré-aquecendo cache (${done}/${urls.length})...`);
                    }
                }
            };

            // Concorrência baixa para não travar o servidor de desenvolvimento
            // (Flask dev é single-thread) nem brigar com cliques reais.
            await this._runInBatches(urls, 2, async (item) => {
                try {
                    if (onlyMissing) {
                        const match = await caches.match(item.url);
                        if (match) { report('hit'); return; }
                    }
                    const init = item.type === 'media'
                        ? { credentials: 'include', mode: 'no-cors' }
                        : { credentials: 'same-origin' };
                    await fetch(item.url, init);
                    report('fetch');
                    // Pequeno respiro entre requests para o servidor
                    await new Promise(r => setTimeout(r, 30));
                } catch (e) {
                    // silencioso: um recurso a menos não quebra a experiência
                }
            });

            console.log('[PWA] Pré-cache concluído.');
            this._precachingDone = true;
            this.onPrecacheComplete('success');
        } catch (err) {
            console.warn('[PWA] Erro no pré-cache:', err);
            this.onPrecacheComplete('error');
        } finally {
            if (this._precacheTimeout) {
                clearTimeout(this._precacheTimeout);
                this._precacheTimeout = null;
            }
            this._precaching = false;
        }
    }

    onPrecacheComplete(reason) {
        // Evitar loop infinito - não chamar callback se já foi chamado
        if (this._precacheCompleteCalled) {
            return;
        }
        this._precacheCompleteCalled = true;

        console.log(`[PWA] Pré-cache completo (motivo: ${reason})`);

        // Limpar callback ANTES de executar para evitar loop
        const callback = this._precacheCallback;
        this._precacheCallback = null;

        if (callback) {
            callback(reason);
        }

        // Marcar como concluído e liberar trava
        this._precacheDone = true;
        this._precacheRunning = false;

        this.hideLoading();
        if (reason === 'success') {
            this.showNotification('Cache pré-aquecido com sucesso!', 'success');
        } else if (reason === 'timeout') {
            this.showNotification('Pré-cache em background. O app continuará funcionando.', 'info');
        }
    }

    _collectPrecacheUrls(cartoes) {
        const set = new Map();
        const add = (url, type) => {
            if (!url) return;
            if (!set.has(url)) set.set(url, { url, type });
        };

        // Foco: detalhes (HTML do modal) e mídia (imagens/PDF).
        // Endpoints de apontamento são leves e ficam em SWR via SW
        // na primeira abertura real — não precisam pré-aquecer.
        for (const cartao of cartoes) {
            const ordemId = cartao.ordem_id || cartao.id;
            const listaNome = String(cartao.lista_nome || '').trim().toLowerCase();

            // Em Expedição não precisamos pré-aquecer endpoints de apontamento.
            const shouldPrefetchApontamento = listaNome !== 'expedição' && listaNome !== 'expedicao';

            // Pré-aquecer endpoints de leitura do apontamento.
            // O Service Worker usa SWR para estes endpoints. Ao pré-baixar aqui,
            // a primeira abertura do modal tende a ser instantânea.
            if (shouldPrefetchApontamento && ordemId && !String(ordemId).startsWith('fantasma-')) {
                add(`/apontamento/os/${ordemId}/itens`, 'api');
                add(`/apontamento/quantidades-por-trabalho/${ordemId}`, 'api');
            }

            if (cartao.item_imagem_path) {
                add(this._resolveMediaUrl(cartao.item_imagem_path), 'media');
            }
            for (const item of (cartao.itens || [])) {
                if (item.imagem_path) add(this._resolveMediaUrl(item.imagem_path), 'media');
            }
            if (cartao.pedido && cartao.pedido.item_imagem) {
                add(this._resolveMediaUrl(cartao.pedido.item_imagem), 'media');
            }
        }

        return Array.from(set.values());
    }

    _resolveMediaUrl(path) {
        if (!path) return '';
        // PDFs não são cacheados pelo SW (opaque response quebra o viewer),
        // então não tem sentido pré-baixar.
        if (/\.pdf(\?|$)/i.test(path)) return '';
        if (/^https?:\/\//i.test(path)) return path;
        if (path.startsWith('/uploads/')) return path;
        return `/uploads/${path.replace(/^\/+/, '')}`;
    }

    async _runInBatches(items, concurrency, worker) {
        const queue = items.slice();
        const runners = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
            while (queue.length) {
                const item = queue.shift();
                await worker(item);
            }
        });
        await Promise.all(runners);
    }
}

// Instância global
window.kanbanPWA = new KanbanPWA();

// Inicializar quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.kanbanPWA.init();
    });
} else {
    window.kanbanPWA.init();
}
