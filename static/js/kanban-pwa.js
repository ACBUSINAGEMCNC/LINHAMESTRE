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
                this.hideLoading();
                console.log('[PWA] Cache carregado! Kanban renderizado localmente.');
                this.updateSyncIndicator('synced');
                break;
                
            case 'full_sync_complete':
                if (this.bootstrap.frontend_shell) {
                    this.updateLoadingProgress(65, 'Montando Kanban local...');
                    this.renderKanban(event.data);
                }
                this.updateLoadingProgress(100, 'Cache local concluído!');
                this.hideLoading();
                console.log('[PWA] Full sync completo! Dados em cache para próxima vez.');
                this.showNotification('Dados salvos no cache local!', 'success');
                this.updateSyncIndicator('synced');
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
