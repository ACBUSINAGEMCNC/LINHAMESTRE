/**
 * Kanban Cache Manager - IndexedDB
 * Gerencia cache local de dados do Kanban
 */

class KanbanCache {
    constructor() {
        this.dbName = 'linhamestre-kanban';
        this.dbVersion = 2;
        this.db = null;
    }
    
    /**
     * Inicializa o banco IndexedDB
     */
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => {
                console.error('[Cache] Erro ao abrir IndexedDB:', request.error);
                reject(request.error);
            };
            
            request.onsuccess = () => {
                this.db = request.result;
                console.log('[Cache] IndexedDB aberto com sucesso!');
                resolve(this.db);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Recriar object stores do zero para invalidar payloads antigos
                ['listas', 'cartoes', 'apontamentos', 'metadata'].forEach((store) => {
                    if (db.objectStoreNames.contains(store)) {
                        db.deleteObjectStore(store);
                    }
                });

                db.createObjectStore('listas', { keyPath: 'id' });
                db.createObjectStore('cartoes', { keyPath: 'id' });
                db.createObjectStore('apontamentos', { keyPath: 'id' });
                db.createObjectStore('metadata', { keyPath: 'key' });

                console.log('[Cache] Object stores recriados (upgrade).');
            };
        });
    }
    
    /**
     * Salva todos os dados do Kanban
     */
    async saveAll(data) {
        if (!this.db) await this.init();
        
        const transaction = this.db.transaction(
            ['listas', 'cartoes', 'apontamentos', 'metadata'], 
            'readwrite'
        );
        
        // Salvar listas
        const listasStore = transaction.objectStore('listas');
        await this.clearStore(listasStore);
        for (const lista of data.listas || []) {
            listasStore.put(lista);
        }
        
        // Salvar cartões
        const cartoesStore = transaction.objectStore('cartoes');
        await this.clearStore(cartoesStore);
        for (const cartao of data.cartoes || []) {
            cartoesStore.put(cartao);
        }
        
        // Salvar apontamentos
        const apontamentosStore = transaction.objectStore('apontamentos');
        await this.clearStore(apontamentosStore);
        for (const apontamento of data.apontamentos || []) {
            apontamentosStore.put(apontamento);
        }
        
        // Salvar metadata
        const metadataStore = transaction.objectStore('metadata');
        metadataStore.put({
            key: 'last_sync',
            timestamp: data.timestamp || new Date().toISOString()
        });
        
        return new Promise((resolve, reject) => {
            transaction.oncomplete = () => {
                console.log('[Cache] Dados salvos com sucesso!');
                resolve();
            };
            transaction.onerror = () => {
                console.error('[Cache] Erro ao salvar dados:', transaction.error);
                reject(transaction.error);
            };
        });
    }
    
    /**
     * Carrega todos os dados do cache
     */
    async getAll() {
        if (!this.db) await this.init();
        
        const transaction = this.db.transaction(
            ['listas', 'cartoes', 'apontamentos', 'metadata'], 
            'readonly'
        );
        
        const listas = await this.getAllFromStore(transaction.objectStore('listas'));
        const cartoes = await this.getAllFromStore(transaction.objectStore('cartoes'));
        const apontamentos = await this.getAllFromStore(transaction.objectStore('apontamentos'));
        const metadata = await this.getFromStore(transaction.objectStore('metadata'), 'last_sync');
        
        return {
            listas,
            cartoes,
            apontamentos,
            last_sync: metadata ? metadata.timestamp : null
        };
    }
    
    /**
     * Atualiza um cartão específico
     */
    async updateCartao(cartao) {
        if (!this.db) await this.init();
        
        const transaction = this.db.transaction(['cartoes'], 'readwrite');
        const store = transaction.objectStore('cartoes');
        store.put(cartao);
        
        return new Promise((resolve, reject) => {
            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        });
    }
    
    /**
     * Remove um cartão
     */
    async deleteCartao(cartaoId) {
        if (!this.db) await this.init();
        
        const transaction = this.db.transaction(['cartoes'], 'readwrite');
        const store = transaction.objectStore('cartoes');
        store.delete(cartaoId);
        
        return new Promise((resolve, reject) => {
            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        });
    }
    
    /**
     * Atualiza timestamp da última sincronização
     */
    async updateLastSync(timestamp) {
        if (!this.db) await this.init();
        
        const transaction = this.db.transaction(['metadata'], 'readwrite');
        const store = transaction.objectStore('metadata');
        store.put({
            key: 'last_sync',
            timestamp: timestamp
        });
        
        return new Promise((resolve, reject) => {
            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        });
    }
    
    /**
     * Limpa todo o cache
     */
    async clear() {
        if (!this.db) await this.init();
        
        const transaction = this.db.transaction(
            ['listas', 'cartoes', 'apontamentos', 'metadata'], 
            'readwrite'
        );
        
        await this.clearStore(transaction.objectStore('listas'));
        await this.clearStore(transaction.objectStore('cartoes'));
        await this.clearStore(transaction.objectStore('apontamentos'));
        await this.clearStore(transaction.objectStore('metadata'));
        
        return new Promise((resolve, reject) => {
            transaction.oncomplete = () => {
                console.log('[Cache] Cache limpo!');
                resolve();
            };
            transaction.onerror = () => reject(transaction.error);
        });
    }
    
    // Helpers
    
    clearStore(store) {
        return new Promise((resolve, reject) => {
            const request = store.clear();
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
    
    getAllFromStore(store) {
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    getFromStore(store, key) {
        return new Promise((resolve, reject) => {
            const request = store.get(key);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
}

// Instância global
window.kanbanCache = new KanbanCache();
