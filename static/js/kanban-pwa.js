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
                this.hideLoading();
                console.log('[PWA] Cache carregado! Kanban tradicional já renderizado.');
                this.updateSyncIndicator('synced');
                break;
                
            case 'full_sync_complete':
                this.updateLoadingProgress(100, 'Cache local concluído!');
                this.hideLoading();
                console.log('[PWA] Full sync completo! Dados em cache para próxima vez.');
                this.showNotification('Dados salvos no cache local!', 'success');
                this.updateSyncIndicator('synced');
                break;
                
            case 'incremental_update':
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
        
        // Limpar listas existentes
        const container = document.getElementById('kanban-container');
        if (!container) {
            console.error('[PWA] Container do Kanban não encontrado!');
            return;
        }
        
        container.innerHTML = '';
        
        // Renderizar cada lista
        for (const lista of data.listas || []) {
            const listaEl = this.createListaElement(lista);
            
            // Adicionar cartões da lista
            const cartoesDaLista = (data.cartoes || []).filter(c => c.lista_id === lista.id);
            for (const cartao of cartoesDaLista) {
                const cartaoEl = this.createCartaoElement(cartao);
                listaEl.querySelector('.kanban-cards').appendChild(cartaoEl);
            }
            
            container.appendChild(listaEl);
        }
        
        // Reinicializar drag & drop
        if (window.initDragAndDrop) {
            window.initDragAndDrop();
        }
        
        // Atualizar indicador de sync
        this.updateSyncIndicator('synced');
    }
    
    /**
     * Cria elemento de lista
     */
    createListaElement(lista) {
        const div = document.createElement('div');
        div.className = 'kanban-list';
        div.dataset.listaId = lista.id;
        
        div.innerHTML = `
            <div class="kanban-list-header" style="background-color: ${lista.cor || '#6c757d'}">
                <h5>${lista.nome}</h5>
                <span class="badge bg-light text-dark">0</span>
            </div>
            <div class="kanban-cards" data-lista-id="${lista.id}">
                <!-- Cartões serão inseridos aqui -->
            </div>
        `;
        
        return div;
    }
    
    /**
     * Cria elemento de cartão
     */
    createCartaoElement(cartao) {
        const div = document.createElement('div');
        div.className = 'kanban-card';
        div.dataset.cartaoId = cartao.id;
        div.draggable = true;
        
        const pedido = cartao.pedido || {};
        const isFantasma = cartao.is_fantasma;
        
        div.innerHTML = `
            <div class="card-header ${isFantasma ? 'bg-warning' : ''}">
                <strong>${cartao.numero}</strong>
                ${isFantasma ? '<span class="badge bg-warning">Fantasma</span>' : ''}
            </div>
            <div class="card-body">
                ${pedido.cliente ? `<p><strong>Cliente:</strong> ${pedido.cliente}</p>` : ''}
                ${pedido.item_codigo ? `<p><strong>Item:</strong> ${pedido.item_codigo}</p>` : ''}
                ${pedido.quantidade ? `<p><strong>Qtd:</strong> ${pedido.quantidade}</p>` : ''}
            </div>
        `;
        
        // Event listeners
        div.addEventListener('click', () => {
            this.openCartaoDetails(cartao);
        });
        
        return div;
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
