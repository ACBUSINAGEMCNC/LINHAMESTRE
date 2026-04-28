/**
 * Kanban Sync Manager
 * Gerencia sincronização incremental com servidor
 */

class KanbanSync {
    constructor() {
        this.syncInterval = 10000; // 10 segundos
        this.syncTimer = null;
        this.isSyncing = false;
        this.lastSync = null;
        this.onUpdateCallback = null;
    }
    
    /**
     * Inicia o processo de sincronização
     */
    async start(onUpdate) {
        this.onUpdateCallback = onUpdate;
        
        console.log('[Sync] Iniciando sincronização...');
        
        // Verificar se tem cache
        const cached = await window.kanbanCache.getAll();
        
        if (cached.listas && cached.listas.length > 0) {
            // Tem cache - carregar do cache primeiro
            console.log('[Sync] Cache encontrado! Carregando...');
            this.lastSync = cached.last_sync;
            
            if (this.onUpdateCallback) {
                this.onUpdateCallback({
                    type: 'cache_loaded',
                    data: cached
                });
            }
            
            // Depois sincronizar em background
            await this.incrementalSync();
        } else {
            // Não tem cache - fazer full sync
            console.log('[Sync] Cache vazio. Fazendo full sync...');
            await this.fullSync();
        }
        
        // Iniciar sync automático
        this.startAutoSync();
    }
    
    /**
     * Full sync - carrega tudo do servidor
     */
    async fullSync() {
        console.log('[Sync] Full sync iniciado...');
        this.isSyncing = true;
        
        try {
            const response = await fetch('/kanban/full-data');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.message || 'Erro ao carregar dados');
            }
            
            // Salvar no cache
            await window.kanbanCache.saveAll(data);
            this.lastSync = data.timestamp;
            
            // Notificar UI
            if (this.onUpdateCallback) {
                this.onUpdateCallback({
                    type: 'full_sync_complete',
                    data: data
                });
            }
            
            console.log('[Sync] Full sync concluído!');
            
        } catch (error) {
            console.error('[Sync] Erro no full sync:', error);
            
            if (this.onUpdateCallback) {
                this.onUpdateCallback({
                    type: 'sync_error',
                    error: error.message
                });
            }
        } finally {
            this.isSyncing = false;
        }
    }
    
    /**
     * Incremental sync - busca apenas mudanças
     */
    async incrementalSync() {
        if (this.isSyncing) {
            console.log('[Sync] Sync já em andamento, pulando...');
            return;
        }
        
        if (!this.lastSync) {
            console.log('[Sync] Sem timestamp, fazendo full sync...');
            return await this.fullSync();
        }
        
        console.log('[Sync] Incremental sync iniciado...');
        this.isSyncing = true;
        
        try {
            const url = `/kanban/sync?last_update=${encodeURIComponent(this.lastSync)}`;
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const delta = await response.json();
            
            if (!delta.success) {
                throw new Error(delta.message || 'Erro ao sincronizar');
            }
            
            if (delta.has_changes) {
                console.log('[Sync] Mudanças detectadas:', delta);
                
                // Aplicar mudanças no cache
                await this.applyDelta(delta);
                
                // Atualizar timestamp
                this.lastSync = delta.timestamp;
                await window.kanbanCache.updateLastSync(delta.timestamp);
                
                // Notificar UI
                if (this.onUpdateCallback) {
                    this.onUpdateCallback({
                        type: 'incremental_update',
                        delta: delta
                    });
                }
            } else {
                console.log('[Sync] Nenhuma mudança detectada');
            }
            
        } catch (error) {
            console.error('[Sync] Erro no incremental sync:', error);
            
            // Se falhar, tentar full sync
            if (error.message.includes('404') || error.message.includes('500')) {
                console.log('[Sync] Erro no servidor, tentando full sync...');
                await this.fullSync();
            }
        } finally {
            this.isSyncing = false;
        }
    }
    
    /**
     * Aplica mudanças incrementais no cache
     */
    async applyDelta(delta) {
        // Atualizar cartões modificados
        if (delta.updated_cards && delta.updated_cards.length > 0) {
            for (const cartao of delta.updated_cards) {
                await window.kanbanCache.updateCartao(cartao);
            }
        }
        
        // Remover cartões deletados
        if (delta.deleted_cards && delta.deleted_cards.length > 0) {
            for (const cartaoId of delta.deleted_cards) {
                await window.kanbanCache.deleteCartao(cartaoId);
            }
        }
        
        // Adicionar novos cartões
        if (delta.new_cards && delta.new_cards.length > 0) {
            for (const cartao of delta.new_cards) {
                await window.kanbanCache.updateCartao(cartao);
            }
        }
    }
    
    /**
     * Inicia sincronização automática
     */
    startAutoSync() {
        if (this.syncTimer) {
            clearInterval(this.syncTimer);
        }
        
        this.syncTimer = setInterval(() => {
            this.incrementalSync();
        }, this.syncInterval);
        
        console.log(`[Sync] Auto-sync ativado (${this.syncInterval / 1000}s)`);
    }
    
    /**
     * Para sincronização automática
     */
    stopAutoSync() {
        if (this.syncTimer) {
            clearInterval(this.syncTimer);
            this.syncTimer = null;
            console.log('[Sync] Auto-sync desativado');
        }
    }
    
    /**
     * Força sincronização imediata
     */
    async forceSync() {
        console.log('[Sync] Sincronização forçada...');
        await this.incrementalSync();
    }
    
    /**
     * Envia mudança para servidor (optimistic update)
     */
    async sendUpdate(type, data) {
        try {
            const response = await fetch(`/kanban/${type}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.message || 'Erro ao enviar atualização');
            }
            
            // Atualizar timestamp
            if (result.timestamp) {
                this.lastSync = result.timestamp;
                await window.kanbanCache.updateLastSync(result.timestamp);
            }
            
            return result;
            
        } catch (error) {
            console.error('[Sync] Erro ao enviar atualização:', error);
            throw error;
        }
    }
}

// Instância global
window.kanbanSync = new KanbanSync();
