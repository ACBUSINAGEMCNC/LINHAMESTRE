/**
 * Sistema de persistência para apontamentos
 * Garante que os apontamentos ativos não sejam perdidos ao recarregar a página
 */

// Lock global para evitar execuções concorrentes
let _carregandoEstado = false;

// Coordenação de QPT: marcação de "toque recente" para evitar renders duplicados
// Mantém um carimbo de tempo por OS sempre que a QPT for atualizada manualmente
try { window.__qptTouch = window.__qptTouch || {}; } catch {}

// Guardião de fetch para evitar requisições duplicadas por OS ao usar o fallback
try { window.__qptFetching = window.__qptFetching || {}; } catch {}

// Inicialização única: renderiza QPT a partir do cache/localStorage no carregamento
try {
    if (!window.__qptInitOnce) {
        window.__qptInitOnce = true;
        document.addEventListener('DOMContentLoaded', function() {
            try {
                const cards = document.querySelectorAll('.kanban-card[data-ordem-id]:not(.fantasma)');
                cards.forEach(card => {
                    const idStr = card.getAttribute('data-ordem-id');
                    const osId = parseInt(idStr, 10);
                    if (!Number.isNaN(osId) && typeof window.atualizarQuantidadesPorTrabalho === 'function') {
                        // Não limpa conteúdo; apenas tenta preencher via cache
                        window.atualizarQuantidadesPorTrabalho(osId, []);
                    }
                });
            } catch (e) { console.warn('Falha ao inicializar QPT via cache no load:', e); }
        }, { once: true });
    }
} catch {}

// Sincronização entre abas via localStorage
try {
    window.addEventListener('storage', function(ev) {
        if (!ev) return;
        const key = ev.key || '';
        // Broadcast de novo apontamento/quantidade
        if (key === 'apontamento_event') {
            try {
                const payload = JSON.parse(ev.newValue || 'null');
                if (!payload || typeof payload !== 'object') return;
                const osId = parseInt(payload.osId, 10);
                if (!Number.isNaN(osId)) {
                    // Atualizar cache QPT quando houver quantidade válida
                    const qtdNum = Number.isFinite(Number(payload.quantidade)) ? Number(payload.quantidade) : null;
                    if (qtdNum !== null && typeof window.atualizarQPTCacheEntrada === 'function') {
                        window.atualizarQPTCacheEntrada(
                            osId,
                            payload.trabalhoId || null,
                            payload.trabalhoNome || null,
                            payload.itemCodigoBase || null,
                            qtdNum
                        );
                        // Força atualização imediata e envia broadcast para outras abas
                        try {
                            localStorage.setItem('force_qpt_refresh', JSON.stringify({osId, timestamp: Date.now()}));
                        } catch {}
                    }
                    // Atualizar rótulo "Última qtd" no cabeçalho da QPT
                    try {
                        if (qtdNum !== null && typeof window.atualizarUltimaQuantidadeNoCard === 'function') {
                            window.atualizarUltimaQuantidadeNoCard(osId, qtdNum);
                        }
                    } catch {}
                    // Forçar render imediato a partir do cache, respeitando o guard
                    try {
                        const c = document.getElementById(`qtd-por-trabalho-${osId}`);
                        if (c && c.dataset) delete c.dataset.qptSig;
                        if (typeof window.atualizarQuantidadesPorTrabalho === 'function') {
                            window.atualizarQuantidadesPorTrabalho(osId, []);
                            // Fallback 200ms
                            setTimeout(() => {
                                try { if (window.atualizarQuantidadesPorTrabalho) window.atualizarQuantidadesPorTrabalho(osId, []); } catch {}
                            }, 200);
                        }
                        if (typeof window.markQptTouch === 'function') window.markQptTouch(osId);
                        // Forçar atualização dos chips de status
                        if (typeof window.renderizarChipsStatus === 'function' && Array.isArray(payload.ativos_por_trabalho)) {
                            window.renderizarChipsStatus(osId, payload.ativos_por_trabalho);
                        }
                    } catch {}
                    // Não recarregar status aqui para evitar piscadas nos timers
                }
            } catch (e) { console.warn('Falha ao processar apontamento_event de outra aba:', e); }
        }
        // Forçar refresh de QPT quando outra aba emitir o evento
        if (key === 'force_qpt_refresh') {
            try {
                const data = JSON.parse(ev.newValue || 'null');
                if (!data || typeof data !== 'object') return;
                const osId = parseInt(data.osId, 10);
                if (Number.isNaN(osId)) return;
                
                // Limpar assinatura da QPT para forçar re-render
                const c = document.getElementById(`qtd-por-trabalho-${osId}`);
                if (c && c.dataset) delete c.dataset.qptSig;
                
                // Forçar atualização imediata da QPT sem esperar debounce
                if (typeof window.atualizarQuantidadesPorTrabalho === 'function') {
                    window.atualizarQuantidadesPorTrabalho(osId, []);
                    // Fallback 200ms
                    setTimeout(() => {
                        try { if (window.atualizarQuantidadesPorTrabalho) window.atualizarQuantidadesPorTrabalho(osId, []); } catch {}
                    }, 200);
                }
            } catch (e) { console.warn('Falha ao processar force_qpt_refresh:', e); }
        }
        
        // Broadcast genérico (atualizações diversas: qpt_update, stop, etc.)
        if (key === 'apontamento_broadcast') {
            try {
                const payload = JSON.parse(ev.newValue || 'null');
                if (!payload || typeof payload !== 'object') return;
                const { type, osId } = payload;
                const osNum = parseInt(osId, 10);
                if (Number.isNaN(osNum)) return;
                if (type === 'qpt_update') {
                    // Reaproveita caminho do apontamento_event
                    try {
                        const c = document.getElementById(`qtd-por-trabalho-${osNum}`);
                        if (c && c.dataset) delete c.dataset.qptSig;
                    } catch {}
                    try {
                        if (!(typeof shouldSkipQpt === 'function' && shouldSkipQpt(osNum))) {
                            if (typeof window.atualizarQuantidadesPorTrabalho === 'function') {
                                window.atualizarQuantidadesPorTrabalho(osNum, []);
                                // Fallback 200ms
                                setTimeout(() => {
                                    try { if (window.atualizarQuantidadesPorTrabalho) window.atualizarQuantidadesPorTrabalho(osNum, []); } catch {}
                                }, 200);
                            }
                        }
                        if (typeof window.markQptTouch === 'function') window.markQptTouch(osNum);
                    } catch {}
                    // Não recarregar status neste tipo para evitar piscadas no cronômetro
                } else if (type === 'stop') {
                    // Limpa timers e UI imediatamente na mesma aba
                    try { if (typeof limparTimersTrabalhoDaOS === 'function') limparTimersTrabalhoDaOS(osNum); } catch {}
                    try { if (typeof pararTimerApontamento === 'function') pararTimerApontamento(osNum); } catch {}
                    // Marcar flag para forçar atualização imediata de QPT após stop
                    try {
                        window.__qptAfterStop = window.__qptAfterStop || {};
                        window.__qptAfterStop[osNum] = true;
                        console.debug('[QPT] Marcando OS para atualização imediata após STOP:', osNum);
                        // Forçar atualização imediata de QPT
                        if (typeof window.atualizarQuantidadesPorTrabalho === 'function') {
                            // Limpar assinatura anterior para forçar re-render
                            try {
                                const container = document.getElementById(`qtd-por-trabalho-${osNum}`);
                                if (container && container.dataset) delete container.dataset.qptSig;
                            } catch {}
                            // Chamar com lista vazia para forçar uso do cache
                            window.atualizarQuantidadesPorTrabalho(osNum, []);
                            // Fallback 200ms
                            setTimeout(() => {
                                try { if (window.atualizarQuantidadesPorTrabalho) window.atualizarQuantidadesPorTrabalho(osNum, []); } catch {}
                            }, 200);
                        }
                    } catch {}
                    try {
                        const allCards = document.querySelectorAll(`[data-ordem-id="${osNum}"]`);
                        let card = null;
                        for (const c of allCards) { if (!c.classList.contains('fantasma')) { card = c; break; } }
                        if (card) {
                            const container = card.querySelector(`#status-${osNum}`) || card.querySelector('.status-apontamento');
                            if (container) container.innerHTML = '<small class="text-muted">Aguardando apontamento</small>';
                        }
                    } catch {}
                    // Em seguida, recarrega estado e mantém QPT a partir do cache
                    try { if (typeof window.recarregarEstadoApontamentos === 'function') window.recarregarEstadoApontamentos(); } catch {}
                    try {
                        const c = document.getElementById(`qtd-por-trabalho-${osNum}`);
                        if (c && c.dataset) delete c.dataset.qptSig;
                        if (!(typeof shouldSkipQpt === 'function' && shouldSkipQpt(osNum))) {
                            if (typeof window.atualizarQuantidadesPorTrabalho === 'function') {
                                window.atualizarQuantidadesPorTrabalho(osNum, []);
                                // Fallback 200ms
                                setTimeout(() => {
                                    try { if (window.atualizarQuantidadesPorTrabalho) window.atualizarQuantidadesPorTrabalho(osNum, []); } catch {}
                                }, 200);
                            }
                        }
                        if (typeof window.markQptTouch === 'function') window.markQptTouch(osNum);
                    } catch {}
                }
            } catch (e) { console.warn('Falha ao processar apontamento_broadcast de outra aba:', e); }
        }
        // Alterações no snapshot de status local: recarregar estado para refletir STOP/PAUSA/etc
        if (key === 'apontamento_status') {
            try { if (typeof window.recarregarEstadoApontamentos === 'function') window.recarregarEstadoApontamentos(); } catch {}
        }
    });
} catch (e) { console.warn('Falha ao registrar listener de storage para sincronização entre abas:', e); }
function markQptTouch(osId) {
    try { window.__qptTouch[osId] = Date.now(); } catch {}
}
function shouldSkipQpt(osId) {
    try {
        const t = (window.__qptTouch && window.__qptTouch[osId]) || 0;
        return t && (Date.now() - t) < 1200; // 1,2s de tolerância para pular renders concorrentes
    } catch { return false; }
}

// Emite um evento customizado na mesma aba sempre que a QPT for atualizada
function emitQptChange(osId) {
    try {
        window.dispatchEvent(new CustomEvent('qpt:cache-updated', { detail: { osId } }));
    } catch (_) {}
}

// Normaliza nomes de trabalho para comparação/deduplicação
function normalizeTrabLabel(n) {
    try {
        return (n || '').toString().replace(/\s*\([^)]*\)\s*$/, '').trim().toLowerCase();
    } catch {
        return '';
    }
}

// Função para carregar o estado dos apontamentos ao iniciar a página
function carregarEstadoApontamentos() {
    if (_carregandoEstado) {
        console.debug('carregarEstadoApontamentos já em execução, ignorando chamada duplicada');
        return;
    }
    _carregandoEstado = true;
    console.log('Carregando estado dos apontamentos...');
    
    // Limpar apenas debounce; manter caches para preservar últimas quantidades
    try {
        if (window._qptDebounceMap) {
            window._qptDebounceMap.clear();
        }
        // Não limpar localStorage nem __cacheQtdTrabalho aqui; isso removia as últimas quantidades por trabalho
    } catch (e) {
        console.debug('Debounce QPT não encontrado ou já limpo');
    }
    // Verificar se há algum apontamento ativo no momento da recarga
    fetch('/apontamento/status-ativos')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro na resposta: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Para cada OS com status ativo, atualizar visualmente
            const ativos = Array.isArray(data.status_ativos) ? data.status_ativos : [];
            const ativosIds = new Set();
            if (ativos.length > 0) {
                console.log(`Encontrados ${ativos.length} apontamentos ativos`); 
                ativos.forEach(status => {
                    // Usar ordem_servico_id em vez de ordem_id (que não existe no modelo)
                    const ordemId = status.ordem_servico_id;
                    if (ordemId != null) ativosIds.add(String(ordemId));
                    const statusAtual = status.status_atual;
                    
                    console.log(`Restaurando status para OS ${ordemId}: ${statusAtual}`);
                    console.debug(`[BACKEND] Dados completos para OS ${ordemId}:`, {
                        status_atual: status.status_atual,
                        ativos_por_trabalho: status.ativos_por_trabalho,
                        tem_ativos: Array.isArray(status.ativos_por_trabalho) && status.ativos_por_trabalho.length > 0
                    });
                    
                    // Atualizar visual do card conforme status
                    // Atualizar o status visual normalmente (inclusive Pausado)
                    atualizarStatusCartao(ordemId, statusAtual);

                    // Atualizar "Última qtd" no card, se disponível do backend
                    if (typeof window.atualizarUltimaQuantidadeNoCard === 'function' &&
                        Object.prototype.hasOwnProperty.call(status, 'ultima_quantidade')) {
                        window.atualizarUltimaQuantidadeNoCard(ordemId, status.ultima_quantidade);
                    }

                    // Quantidades por trabalho (lista lateral)
                    try {
                        if (!(typeof shouldSkipQpt === 'function' && shouldSkipQpt(ordemId))) {
                            atualizarQuantidadesPorTrabalho(ordemId, Array.isArray(status.ativos_por_trabalho) ? status.ativos_por_trabalho : []);
                            markQptTouch(ordemId); // Marcar toque recente
                        }
                    } catch (eUI) {
                        console.warn('Falha ao atualizar UI de múltiplos/quantidades por trabalho:', eUI);
                    }

                    // Chips no status com (tipo de trabalho + timer) lado a lado
                    try {
                        if (Array.isArray(status.ativos_por_trabalho)) {
                            renderizarChipsStatus(ordemId, status.ativos_por_trabalho);
                        } else {
                            renderizarChipsStatus(ordemId, []);
                        }
                    } catch (eChips) {
                        console.warn('Falha ao renderizar chips de status:', eChips);
                    }

                    // Exibir indicador de operador no card
                    if (status.operador_nome) {
                        adicionarIndicadorOperador(ordemId, status.operador_nome, status.operador_codigo);
                    }
                    
                    // Carregar logs para este card
                    carregarLogsParaCard(ordemId);
                    
                    // Verificar se o operador atual é o mesmo que está logado
                    if (status.operador_id) {
                        const usuarioAtualId = document.body.getAttribute('data-usuario-id');
                        if (usuarioAtualId && parseInt(usuarioAtualId) !== status.operador_id) {
                            // Desabilitar botões para operadores diferentes
                            desabilitarBotoesOperadorDiferente(ordemId, status.operador_nome);
                        }
                    }
                    
                });
                
                console.log('Estado dos apontamentos restaurado com sucesso!');
            } else {
                console.log('Nenhum apontamento ativo encontrado.');
            }

            // Garante QPT visível para OS sem ativo (renderiza via cache/LS)
            try {
                const cards = document.querySelectorAll('.kanban-card[data-ordem-id]:not(.fantasma)');
                cards.forEach(card => {
                    const idStr = card.getAttribute('data-ordem-id');
                    if (!ativosIds.has(String(idStr))) {
                        const osId = parseInt(idStr, 10);
                        if (!Number.isNaN(osId)) {
                            if (!(typeof shouldSkipQpt === 'function' && shouldSkipQpt(osId))) {
                                atualizarQuantidadesPorTrabalho(osId, []);
                            }
                        }
                    }
                });
            } catch (eAll) {
                console.warn('Falha ao garantir QPT para OS sem ativo:', eAll);
            }
        })
        .catch(error => {
            console.error('Erro ao carregar estado dos apontamentos:', error);
            // Tentar novamente após 3 segundos em caso de falha
            setTimeout(carregarEstadoApontamentos, 3000);
        })
        .finally(() => {
            _carregandoEstado = false;
        });
}

// Gerenciamento de timers por trabalho (independentes)
const timersTrabalho = {}; // chave: `${ordemId}:${itemId}:${trabalhoId}` => intervalId

function keyTrabalho(ordemId, itemId, trabalhoId) {
    return `${ordemId}:${itemId}:${trabalhoId}`;
}

function iniciarTimerTrabalho(ordemId, itemId, trabalhoId, startTimeStr) {
    const key = keyTrabalho(ordemId, itemId, trabalhoId);
    // Limpar anterior, se existir
    if (timersTrabalho[key]) {
        clearInterval(timersTrabalho[key]);
        delete timersTrabalho[key];
    }
    const el = document.getElementById(`timer-${ordemId}-${itemId}-${trabalhoId}`);
    if (!el) return;
    const startTs = startTimeStr ? new Date(startTimeStr).getTime() : Date.now();
    // Atualização imediata
    atualizarElementoTimer(el, startTs);
    // Intervalo de 1s
    timersTrabalho[key] = setInterval(() => atualizarElementoTimer(el, startTs), 1000);
}

function atualizarElementoTimer(el, startTs) {
    const now = Date.now();
    const elapsed = Math.max(0, Math.floor((now - startTs) / 1000));
    const h = Math.floor(elapsed / 3600).toString().padStart(2, '0');
    const m = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
    const s = (elapsed % 60).toString().padStart(2, '0');
    el.textContent = `${h}:${m}:${s}`;
    el.style.display = 'inline-block';
}

function pararTimerTrabalho(ordemId, itemId, trabalhoId) {
    const key = keyTrabalho(ordemId, itemId, trabalhoId);
    if (timersTrabalho[key]) {
        clearInterval(timersTrabalho[key]);
        delete timersTrabalho[key];
    }
}

function limparTimersTrabalhoDaOS(ordemId) {
    const prefix = `${ordemId}:`;
    Object.keys(timersTrabalho).forEach(k => {
        if (k.startsWith(prefix)) {
            clearInterval(timersTrabalho[k]);
            delete timersTrabalho[k];
        }
    });
}

// Função para sincronizar cronômetro do cartão fantasma com o cartão real
function sincronizarCronometroFantasma(ordemId, containerFantasma) {
    try {
        console.debug(`[SYNC] Iniciando sincronização para OS ${ordemId}`);
        
        // Buscar cartão real da mesma OS - tentar vários seletores
        let cartoesReais = document.querySelectorAll(`[data-ordem-id="${ordemId}"]:not(.fantasma)`);
        if (cartoesReais.length === 0) {
            cartoesReais = document.querySelectorAll(`[data-os-id="${ordemId}"]:not(.fantasma)`);
        }
        if (cartoesReais.length === 0) {
            cartoesReais = document.querySelectorAll(`.kanban-card[data-ordem-id="${ordemId}"]:not(.fantasma)`);
        }
        // Tentar buscar por qualquer cartão que contenha a OS no ID
        if (cartoesReais.length === 0) {
            const todosCartoes = document.querySelectorAll('.kanban-card:not(.fantasma)');
            cartoesReais = Array.from(todosCartoes).filter(cartao => {
                const ordemAttr = cartao.dataset.ordemId || cartao.dataset.osId;
                return ordemAttr == ordemId;
            });
        }
        
        console.debug(`[SYNC] Encontrados ${cartoesReais.length} cartões reais para OS ${ordemId}`);
        
        if (cartoesReais.length === 0) {
            console.debug(`[SYNC] Nenhum cartão real encontrado para OS ${ordemId}`);
            return;
        }
        
        const cartaoReal = cartoesReais[0];
        console.debug(`[SYNC] Cartão real encontrado:`, cartaoReal);
        
        // Buscar container de status no cartão real - tentar vários seletores
        let containerReal = cartaoReal.querySelector('.apontamento-status');
        if (!containerReal) {
            containerReal = cartaoReal.querySelector('.status-apontamento');
        }
        if (!containerReal) {
            containerReal = cartaoReal.querySelector(`#status-${ordemId}`);
        }
        if (!containerReal) {
            containerReal = cartaoReal.querySelector(`[id*="status-${ordemId}"]`);
        }
        if (!containerReal) {
            containerReal = cartaoReal.querySelector('[class*="apontamento"][class*="status"]');
        }
        
        console.debug(`[SYNC] Container real encontrado:`, containerReal);
        
        if (!containerReal) {
            console.debug(`[SYNC] Container real não encontrado para OS ${ordemId}`);
            return;
        }
        
        // Buscar todos os timers no cartão real e fantasma
        const timersReais = containerReal.querySelectorAll('.apontamento-timer');
        const timersFantasma = containerFantasma.querySelectorAll('.apontamento-timer');
        
        console.debug(`[SYNC] Timers encontrados - Reais: ${timersReais.length}, Fantasma: ${timersFantasma.length}`);
        console.debug(`[SYNC] Timers reais:`, Array.from(timersReais).map(t => ({ id: t.id, text: t.textContent })));
        console.debug(`[SYNC] Timers fantasma:`, Array.from(timersFantasma).map(t => ({ id: t.id, text: t.textContent })));
        
        // Sincronizar cada timer
        let sincronizados = 0;
        timersReais.forEach((timerReal, index) => {
            const timerFantasma = timersFantasma[index];
            if (timerFantasma && timerReal.textContent) {
                const tempoAnterior = timerFantasma.textContent;
                
                // Copiar conteúdo e atributos
                timerFantasma.textContent = timerReal.textContent;
                timerFantasma.innerHTML = timerReal.innerHTML;
                
                // Forçar estilos de visibilidade
                timerFantasma.style.display = 'inline-block';
                timerFantasma.style.visibility = 'visible';
                timerFantasma.style.opacity = '1';
                timerFantasma.style.minWidth = '60px';
                timerFantasma.style.textAlign = 'center';
                timerFantasma.style.fontWeight = '700';
                
                // Copiar classes do timer real
                timerFantasma.className = timerReal.className;
                
                // Forçar repaint
                timerFantasma.offsetHeight;
                
                sincronizados++;
                console.debug(`[SYNC] Timer ${index} sincronizado: ${tempoAnterior} -> ${timerReal.textContent}`);
                console.debug(`[SYNC] Timer fantasma após sync:`, {
                    display: timerFantasma.style.display,
                    visibility: timerFantasma.style.visibility,
                    content: timerFantasma.textContent,
                    classes: timerFantasma.className
                });
            } else if (timerFantasma) {
                console.debug(`[SYNC] Timer ${index} não sincronizado - Real: '${timerReal.textContent}', Fantasma existe: ${!!timerFantasma}`);
            } else {
                console.debug(`[SYNC] Timer fantasma ${index} não encontrado`);
            }
        });
        
        console.debug(`[SYNC] Total de timers sincronizados: ${sincronizados}`);
        
        // Configurar observador para manter sincronização contínua
        if (!containerFantasma.dataset.syncObserver) {
            const observer = new MutationObserver((mutations) => {
                let shouldSync = false;
                mutations.forEach((mutation) => {
                    if (mutation.type === 'childList' || 
                        (mutation.type === 'characterData' && mutation.target.parentElement && mutation.target.parentElement.classList.contains('apontamento-timer'))) {
                        shouldSync = true;
                    }
                });
                
                if (shouldSync) {
                    setTimeout(() => sincronizarCronometroFantasma(ordemId, containerFantasma), 50);
                }
            });
            
            observer.observe(containerReal, {
                childList: true,
                subtree: true,
                characterData: true
            });
            
            containerFantasma.dataset.syncObserver = 'true';
            console.debug(`[SYNC] Observer configurado para OS ${ordemId}`);
        }
        
    } catch (error) {
        console.error(`[SYNC] Erro ao sincronizar cronômetro fantasma OS ${ordemId}:`, error);
    }
}

// Função global para debug manual
window.debugSyncFantasma = function(ordemId) {
    console.log(`[DEBUG] Forçando sincronização manual para OS ${ordemId}`);
    const containersFantasma = document.querySelectorAll(`[id*="status-fantasma-${ordemId}"], [id*="status-${ordemId}"]`);
    console.log(`[DEBUG] Containers fantasma encontrados:`, containersFantasma);
    
    containersFantasma.forEach(container => {
        if (container.closest('.fantasma')) {
            console.log(`[DEBUG] Sincronizando container:`, container);
            sincronizarCronometroFantasma(ordemId, container);
        }
    });
};

// Função para sincronizar todos os cartões fantasma visíveis
window.debugSyncTodosFantasmas = function() {
    const cartoesFantasma = document.querySelectorAll('.kanban-card.fantasma');
    console.log(`[DEBUG] Sincronizando ${cartoesFantasma.length} cartões fantasma`);
    
    cartoesFantasma.forEach(cartao => {
        const ordemId = cartao.dataset.fantasmaOrdemId || cartao.dataset.ordemId;
        const container = cartao.querySelector('.apontamento-status');
        if (ordemId && container) {
            console.log(`[DEBUG] Sincronizando cartão fantasma OS ${ordemId}`);
            sincronizarCronometroFantasma(ordemId, container);
        }
    });
};

// Renderiza chips no status com tipo de trabalho + operador + timer
function renderizarChipsStatus(ordemId, ativosLista) {
    // Coletar possíveis nós e normalizar para o elemento do cartão real (.kanban-card)
    const candidateNodes = Array.from(document.querySelectorAll(`[data-os-id="${ordemId}"], [data-ordem-id="${ordemId}"]`));
    let allCards = candidateNodes
        .map(n => n.closest('.kanban-card') || n)
        .filter(el => el && el.classList && el.classList.contains('kanban-card'));
    // Se nada encontrado, tentativa direta por seletor específico do cartão
    if (allCards.length === 0) {
        allCards = Array.from(document.querySelectorAll(`.kanban-card[data-ordem-id="${ordemId}"]`));
    }
    // Deduplicar
    allCards = Array.from(new Set(allCards));
    console.debug(`[CHIPS] Encontrados ${allCards.length} cartões (.kanban-card) para OS ${ordemId}`);
    // Forçar uso da função local sempre no kanban para garantir que chips apareçam
    console.debug(`[CHIPS] Usando função local do persistence para OS ${ordemId}`);
    
    // Processar tanto cartões reais quanto fantasmas
    const cartoesReais = [];
    const cartoesFantasma = [];
    
    for (const c of allCards) {
        if (c.classList.contains('fantasma')) {
            cartoesFantasma.push(c);
        } else {
            cartoesReais.push(c);
        }
    }
    
    console.debug(`[CHIPS] Encontrados ${cartoesReais.length} cartões reais e ${cartoesFantasma.length} cartões fantasma para OS ${ordemId}`);
    
    // Se não há cartões, sair
    if (cartoesReais.length === 0 && cartoesFantasma.length === 0) {
        console.debug(`[CHIPS] Nenhum cartão encontrado para OS ${ordemId}`);
        return;
    }
    
    // Função para processar um cartão (real ou fantasma)
    function processarCartao(card, isFantasma = false) {
        const container = card.querySelector(`#status-${ordemId}`) || card.querySelector('.status-apontamento');
        console.debug(`[CHIPS] Procurando container para OS ${ordemId} (${isFantasma ? 'fantasma' : 'real'})`, {
            card: card,
            statusById: card.querySelector(`#status-${ordemId}`),
            statusByClass: card.querySelector('.status-apontamento'),
            container: container
        });
        
        if (!container) {
            console.debug(`[CHIPS] Container de status não encontrado para OS ${ordemId} (${isFantasma ? 'fantasma' : 'real'})`);
            return;
        }
        
        // Limpar timers anteriores dessa OS e conteúdo
        if (!isFantasma) {
            limparTimersTrabalhoDaOS(ordemId);
        }
        container.innerHTML = '';
        
        return container;
    }
    
    // Verificar se esta OS tem cartões fantasmas associados
    const temCartaoFantasma = cartoesFantasma.length > 0;
    
    // Verificar se já existe um cartão fantasma com status ativo
    let fantasmaTemStatus = false;
    if (temCartaoFantasma) {
        fantasmaTemStatus = cartoesFantasma.some(card => {
            const container = card.querySelector('.apontamento-status') || card.querySelector('.status-apontamento');
            return container && container.innerHTML && container.innerHTML.trim() !== '';
        });
    }
    
    // Processar cartões reais primeiro
    const containersReais = cartoesReais.map(card => {
        // Sempre processar cartões reais normalmente, sem bloquear
        return processarCartao(card, false);
    }).filter(Boolean);
    
    // Processar cartões fantasma
    const containersFantasma = cartoesFantasma.map(card => {
        // Garantir que o cartão fantasma tenha um container de status
        const container = card.querySelector('.apontamento-status') || card.querySelector('.status-apontamento');
        if (container) {
            console.debug(`[CHIPS] Container encontrado para cartão fantasma OS ${ordemId}, ID ${card.dataset.cartaoId || 'desconhecido'}`);
            
            // Verificar se já tem conteúdo e está bloqueado
            if (container.dataset.statusLocked === 'true' && container.innerHTML && container.innerHTML.trim() !== '') {
                console.debug(`[CHIPS] Mantendo conteúdo existente do cartão fantasma OS ${ordemId}`);
                return container;
            }
            
            // Limpar conteúdo apenas se não estiver bloqueado
            container.innerHTML = '';
            return container;
        } else {
            console.debug(`[CHIPS] Nenhum container encontrado para cartão fantasma OS ${ordemId}`);
            return null;
        }
    }).filter(Boolean);
    
    if (containersReais.length === 0 && containersFantasma.length === 0) {
        console.debug(`[CHIPS] Nenhum container de status encontrado para OS ${ordemId}`);
        return;
    }
    
    console.debug(`[CHIPS] Dados recebidos para OS ${ordemId}:`, {
        ativosLista: ativosLista,
        isArray: Array.isArray(ativosLista),
        length: ativosLista?.length
    });
    
    if (!Array.isArray(ativosLista) || ativosLista.length === 0) {
        // Verificar se há apontamento ativo no backend antes de mostrar "aguardando"
        console.debug(`[CHIPS] Lista vazia para OS ${ordemId}, verificando status no backend`);
        
        // Fazer uma verificação rápida do status atual
        fetch(`/apontamento/status-ativos`)
            .then(response => response.json())
            .then(data => {
                const statusAtivos = data.status_ativos || [];
                const osAtiva = statusAtivos.find(s => (s.ordem_servico_id || s.os_id || s.id) == ordemId);
                
                if (osAtiva && Array.isArray(osAtiva.ativos_por_trabalho) && osAtiva.ativos_por_trabalho.length > 0) {
                    console.debug(`[CHIPS] Encontrado status ativo no backend para OS ${ordemId}, re-renderizando`);
                    // Re-chamar com os dados corretos
                    renderizarChipsStatus(ordemId, osAtiva.ativos_por_trabalho);
                } else {
                    // Mostrar "aguardando" em todos os containers
                    [...containersReais, ...containersFantasma].forEach(container => {
                        // Não atualizar containers com status bloqueado (cartões fantasma)
                        if (container.dataset.statusLocked === 'true') return;
                        container.innerHTML = '<small class="text-muted">Aguardando apontamento</small>';
                    });
                }
            });
        return;
    }
    const frags = [];
    ativosLista.forEach(ap => {
        const itemId = ap.item_id;
        const trabId = ap.trabalho_id;
        const trabNome = ap.trabalho_nome || `Trabalho #${trabId ?? '-'}`;
        const inicio = ap.inicio_acao; // ISO string
        const status = (ap.status || '').toLowerCase();
        let chipClass = 'chip-producao';
        if (status.includes('setup')) chipClass = 'chip-setup';
        else if (status.includes('paus')) chipClass = 'chip-pausa';
        const opCod = ap.operador_codigo ? `OP:${ap.operador_codigo}` : '';
        const opNome = ap.operador_nome || '';
        const opLine = (opCod || opNome) ? `<span class="chip-op small">${[opCod, opNome].filter(Boolean).join(' - ')}</span>` : '';
        const motivoLine = chipClass === 'chip-pausa' && (ap.motivo_pausa || ap.motivo_parada)
            ? `<span class="chip-motivo small">Motivo: ${ap.motivo_pausa || ap.motivo_parada}</span>`
            : '';
        frags.push(
            `<span class="apontamento-chip ${chipClass}" data-item-id="${itemId}" data-trabalho-id="${trabId}">`
          +   `<div class="chip-row">`
          +     `<div class="chip-col">`
          +       `<span class="chip-title small fw-semibold">${trabNome}</span>`
          +        opLine
          +        motivoLine
          +     `</div>`
          +     `<span class="apontamento-timer" id="timer-${ordemId}-${itemId}-${trabId}">00:00:00</span>`
          +   `</div>`
          + `</span>`
        );
        // Iniciar timer em seguida (após injetar DOM)
        setTimeout(() => iniciarTimerTrabalho(ordemId, itemId, trabId, inicio), 0);
    });
    
    // Renderizar chips em todos os containers (reais e fantasmas)
    const htmlContent = frags.join('');
    [...containersReais, ...containersFantasma].forEach((container, index) => {
        // Verificar se o container já está bloqueado e tem conteúdo
        if (container.dataset.statusLocked === 'true' && container.innerHTML && container.innerHTML.trim() !== '') {
            console.debug(`[CHIPS] Pulando atualização de container bloqueado`);
            return;
        }
        
        const isFantasma = index >= containersReais.length;
        // Cartões fantasma agora mostram o mesmo conteúdo que os reais (sem badge "Fantasma")
        container.innerHTML = htmlContent;
        
        if (isFantasma) {
            // Para cartões fantasma, sincronizar cronômetro com cartão real
            console.debug(`[SYNC] Configurando sincronização para cartão fantasma OS ${ordemId}`);
            
            // Sincronização inicial imediata
            setTimeout(() => {
                sincronizarCronometroFantasma(ordemId, container);
            }, 50);
            
            // Sincronização adicional após 500ms para garantir
            setTimeout(() => {
                sincronizarCronometroFantasma(ordemId, container);
            }, 500);
            
            // Configurar sincronização periódica a cada 1 segundo
            const syncInterval = setInterval(() => {
                if (document.contains(container)) {
                    sincronizarCronometroFantasma(ordemId, container);
                } else {
                    // Container foi removido, limpar intervalo
                    clearInterval(syncInterval);
                    console.debug(`[SYNC] Limpando intervalo para OS ${ordemId} - container removido`);
                }
            }, 1000);
            
            // Armazenar referência do intervalo para limpeza posterior
            container.dataset.syncInterval = syncInterval;
            console.debug(`[SYNC] Intervalo configurado para OS ${ordemId}:`, syncInterval);
            
            // Garantir que o conteúdo não seja sobrescrito por outras atualizações
            container.dataset.statusLocked = 'true';
        } else {
            // Bloquear temporariamente cartões reais com status ativos para evitar sobrescrita
            if (htmlContent && htmlContent.trim() !== '') {
                container.dataset.statusLocked = 'true';
                
                // Registrar timestamp para desbloquear após 30 segundos
                const now = Date.now();
                container.dataset.statusLockedTs = now;
                
                // Programar desbloqueio após 30 segundos
                setTimeout(() => {
                    // Só desbloquear se o timestamp ainda for o mesmo
                    if (container.dataset.statusLockedTs == now) {
                        delete container.dataset.statusLocked;
                        delete container.dataset.statusLockedTs;
                        console.debug(`[CHIPS] Desbloqueando status do cartão real OS ${ordemId} após 30s`);
                    }
                }, 30000);
                
                console.debug(`[CHIPS] Bloqueando temporariamente status do cartão real OS ${ordemId} por 30s`);
            }
        }
    });
}

// Renderiza a lista de quantidades por trabalho ativo no card
function atualizarQuantidadesPorTrabalho(ordemId, ativosLista) {
    let container = document.getElementById(`qtd-por-trabalho-${ordemId}`);
    if (!container) {
        // Tentar localizar dentro do cartão REAL (não-fantasma) para evitar colisão de IDs
        try {
            const allCards = document.querySelectorAll(`[data-ordem-id="${ordemId}"]`);
            for (const c of allCards) {
                if (!c.classList.contains('fantasma')) {
                    const scoped = c.querySelector(`#qtd-por-trabalho-${ordemId}`);
                    if (scoped) { container = scoped; break; }
                }
            }
        } catch {}
    }
    if (!container) { try { console.debug('[QPT] container não encontrado para OS', ordemId); } catch {} return; }

    // Cache por OS para manter últimas quantidades por trabalho após primeiro apontamento
    window.__cacheQtdTrabalho = window.__cacheQtdTrabalho || {}; // { [ordemId]: { enabled: true, items: { [trabIdOrKey]: { trab, qty } } } }
    const store = window.__cacheQtdTrabalho;
    if (!store[ordemId]) {
        store[ordemId] = { enabled: false, items: {} };
    }

    // Registrar timestamp para debounce
    window.__qptRenderLast = window.__qptRenderLast || {};
    const isEmptyCall = !(Array.isArray(ativosLista) && ativosLista.length > 0);
    
    // Verificar se esta é uma chamada após STOP (forçar atualização)
    const isAfterStop = window.__qptAfterStop && window.__qptAfterStop[ordemId];
    if (isAfterStop) {
        // Limpar flag após uso
        delete window.__qptAfterStop[ordemId];
        console.debug('[QPT] Forçando atualização após STOP para OS', ordemId);
    } else if (isEmptyCall) {
        // Manter debounce apenas para chamadas vazias que não são após STOP
        const lastTs = window.__qptRenderLast[ordemId] || 0;
        if (lastTs && (Date.now() - lastTs) < 400) {
            try { console.debug('[QPT] debounce: ignorando render vazio recente', { ordemId }); } catch {}
            return;
        }
    }

    const current = store[ordemId];
    try { console.debug('[QPT] atualizarQuantidadesPorTrabalho', { ordemId, recebidos: Array.isArray(ativosLista) ? ativosLista.length : 'n/a' }); } catch {}

    // Persistência local para sobreviver a reloads
    const LS_KEY = 'qpt_cache_v1';
    let ls = {};
    try {
        ls = JSON.parse(localStorage.getItem(LS_KEY) || '{}');
    } catch (e) {
        ls = {};
    }

    // Pré-preencher cache atual a partir do LS (se ainda vazio)
    try {
        if ((!current.items || Object.keys(current.items).length === 0) && ls[ordemId]) {
            const raw = ls[ordemId] || {};
            const rebuilt = {};
            Object.entries(raw).forEach(([k, v]) => {
                if (!v) return;
                const trabNome = (v.trab || '').toString();
                const trabKey = k.toString();
                const qtyNum = Number.isFinite(Number(v.qty)) ? Number(v.qty) : '-';
                if (!rebuilt[trabKey]) rebuilt[trabKey] = { trab: trabNome || 'Trabalho', qty: qtyNum };
                else {
                    const prev = rebuilt[trabKey];
                    const nPrev = Number(prev.qty);
                    const nNow = Number(qtyNum);
                    if (Number.isFinite(nNow) && (!Number.isFinite(nPrev) || nNow > nPrev)) rebuilt[trabKey] = { trab: trabNome, qty: qtyNum };
                }
            });
            current.items = rebuilt;
            // Deduplicar por nome normalizado (preferir chaves numéricas e maior qty)
            try {
                const byLabel = {};
                const dedup = {};
                Object.entries(current.items || {}).forEach(([k, v]) => {
                    if (!v) return;
                    const label = normalizeTrabLabel(v.trab);
                    if (!label) return;
                    const isId = /^\d+$/.test(k);
                    const qtyNum = Number.isFinite(Number(v.qty)) ? Number(v.qty) : Number.NEGATIVE_INFINITY;
                    if (!byLabel[label]) {
                        byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                    } else {
                        const cur = byLabel[label];
                        const better = (isId && !cur.isId) || (!isId && !cur.isId && qtyNum > cur.qty) || (isId && cur.isId && qtyNum > cur.qty);
                        if (better) byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                    }
                });
                Object.values(byLabel).forEach(({ key, val }) => { dedup[key] = val; });
                current.items = dedup;
            } catch {}
            if (Object.keys(current.items).length > 0) current.enabled = true;
        }
    } catch {}

    // Se recebemos lista de ativos, atualizar o cache por TRABALHO e habilitar a persistência visual
    if (Array.isArray(ativosLista) && ativosLista.length > 0) {
        current.enabled = true;
        // Atualizar itens ativos e migrar possíveis chaves antigas por NOME -> ID
        ativosLista.forEach(ap => {
            const trabNomeNorm = (ap.trabalho_nome || '')
                .toString()
                .replace(/\s*\([^)]*\)\s*$/, '')
                .trim();
            const trabKey = (ap.trabalho_id != null)
                ? String(ap.trabalho_id)
                : (trabNomeNorm || '-');
            const trabLabel = (ap.trabalho_nome && ap.trabalho_nome.toString().trim())
                ? ap.trabalho_nome.toString().replace(/\s*\([^)]*\)\s*$/, '').trim()
                : (trabNomeNorm || `Trabalho #${trabKey}`);
            const qtd = Number.isFinite(Number(ap.ultima_quantidade)) ? Number(ap.ultima_quantidade) : '-';

            // Migrar: remover chave antiga baseada em nome se existir com mesmo label
            try {
                const label = normalizeTrabLabel(trabLabel);
                Object.entries(current.items || {}).forEach(([k, v]) => {
                    if (k === trabKey || !v) return;
                    if (normalizeTrabLabel(v.trab) === label && !/^\d+$/.test(k) && /^\d+$/.test(trabKey)) {
                        delete current.items[k];
                    }
                });
            } catch {}

            current.items[trabKey] = { trab: trabLabel, qty: qtd };
        });

        // Deduplicar por nome normalizado após atualização dos ativos
        try {
            const byLabel = {};
            const dedup = {};
            Object.entries(current.items).forEach(([k, v]) => {
                if (!v) return;
                const label = normalizeTrabLabel(v.trab);
                if (!label) return;
                const isId = /^\d+$/.test(k);
                const qtyNum = Number.isFinite(Number(v.qty)) ? Number(v.qty) : Number.NEGATIVE_INFINITY;
                if (!byLabel[label]) {
                    byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                } else {
                    const cur = byLabel[label];
                    const better = (isId && !cur.isId) || (!isId && !cur.isId && qtyNum > cur.qty) || (isId && cur.isId && qtyNum > cur.qty);
                    if (better) byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                }
            });
            Object.values(byLabel).forEach(({ key, val }) => { dedup[key] = val; });
            current.items = dedup;
        } catch {}

        // Salvar no localStorage (formato novo: items por trabalho)
        try {
            ls[String(ordemId)] = current.items;
            localStorage.setItem(LS_KEY, JSON.stringify(ls));
            // Emitir evento personalizado para atualizar em tempo real
            window.dispatchEvent(new CustomEvent('qpt:cache-updated', { detail: ordemId }));
        } catch (e) {}
        // Notificar a mesma aba para atualização em tempo real
        try { emitQptChange(ordemId); } catch (_) {}
    }

    // Fallback: se não houver itens ainda, tentar carregar do localStorage (compatível com formato antigo)
    if ((!current.items || Object.keys(current.items).length === 0) && ls[ordemId]) {
        const raw = ls[ordemId] || {};
        const rebuilt = {};
        // Placeholder removido: compatibilidade com formato antigo mantida no bloco try abaixo
        try {
            // Formato novo: { [trabId]: { trab, qty } }
            // Formato antigo: { [qualquer]: { trab, itemCod, qty } } -> usar trabId como chave para evitar duplicação
            Object.entries(raw).forEach(([k, v]) => {
                if (!v) return;
                const trabNome = (v.trab || '').toString();
                // Use trabId se disponível, senão use a chave original
                const trabKey = k.toString();
                const qtyNum = Number.isFinite(Number(v.qty)) ? Number(v.qty) : '-';
                if (!rebuilt[trabKey]) rebuilt[trabKey] = { trab: trabNome || `Trabalho`, qty: qtyNum };
                else {
                    const prev = rebuilt[trabKey];
                    const nPrev = Number(prev.qty);
                    const nNow = Number(qtyNum);
                    if (Number.isFinite(nNow) && (!Number.isFinite(nPrev) || nNow > nPrev)) rebuilt[trabKey] = { trab: trabNome, qty: qtyNum };
                }
            });
        } catch {}
        current.items = rebuilt;
        if (Object.keys(current.items).length > 0) current.enabled = true;
    }

    // Renderização: se houver itens no cache, mostrar sempre (mesmo se enabled não estiver setado)
    let entries = Object.values(current.items || {});
    if (entries.length > 0) {
        if (!current.enabled) current.enabled = true;
        // Ordena por nome do trabalho para consistência visual
        entries.sort((a, b) => (a.trab || '').localeCompare(b.trab || ''));

        // Assinatura de conteúdo para evitar re-render sem mudança
        const signature = entries.map(e => `${(e.trab || '').toString().replace(/\s*\([^)]*\)\s*$/, '').trim()}=${e.qty ?? '-'}`).join(';');
        if (container.dataset && container.dataset.qptSig === signature) {
            try { console.debug('[QPT] sem mudanças, evitando re-render', { ordemId }); } catch {}
            // Atualiza timestamp de última tentativa para manter debounce funcional
            try { window.__qptRenderLast[ordemId] = Date.now(); } catch {}
            return;
        }

        // Persistir no formato novo (por trabalho)
        try {
            const LS_KEY = 'qpt_cache_v1';
            let ls2 = {};
            try { ls2 = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch {}
            ls2[String(ordemId)] = current.items;
            try { localStorage.setItem(LS_KEY, JSON.stringify(ls2)); } catch {}
        } catch (ePersist) { try { console.warn('[QPT] falha ao persistir QPT', ePersist); } catch {} }
        // Notificar a mesma aba para atualização em tempo real
        try { emitQptChange(ordemId); } catch (_) {}

        const linhas = [];
        // Cabeçalho simples sem badge duplicado
        const header = `<div class="small text-muted">`
                     +   `<span>Quantidades por trabalho</span>`
                     + `</div>`;
        linhas.push(header);
        linhas.push('<ul class="qpt-list list-unstyled mb-1">');
        entries.forEach(e => {
            const qty = (e.qty ?? '-')
            const trabSafe = (e.trab || '').toString();
            linhas.push(
                `<li class=\"qpt-item\" data-trab-nome=\"${trabSafe.replace(/\"/g, '&quot;')}\">`
              +   `<span class=\"qpt-label\">${trabSafe}</span>`
              +   `<span class=\"badge rounded-pill bg-secondary qpt-qty\" title=\"Último apontamento\">${qty}</span>`
              + `</li>`
            );
        });
        linhas.push('</ul>');
        const html = linhas.join('');
        container.innerHTML = html;
        if (container.dataset) container.dataset.qptSig = signature;
        // Registrar timestamp da última renderização para suportar debounce
        try { window.__qptRenderLast[ordemId] = Date.now(); } catch {}
        try { console.debug('[QPT] renderizado via cache', { ordemId, itens: entries.length }); } catch {}
        return;
    }

    // Sem dados atuais: não limpar o container para manter o último valor visível
    // Caso seja o primeiro load e o container esteja vazio, opcionalmente poderíamos
    // exibir um placeholder. Por ora, não alterar o conteúdo existente.

    // Fallback inteligente: buscar últimas quantidades por trabalho na API de detalhes
    // quando não houver ativos e não houver cache para esta OS.
    try {
        const hasAny = current && current.items && Object.keys(current.items).length > 0;
        if (!hasAny && !window.__qptFetching[ordemId]) {
            window.__qptFetching[ordemId] = true;
            fetch(`/apontamento/detalhes/${ordemId}`)
                .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
                .then(det => {
                    try {
                        const trabalhos = Array.isArray(det.trabalhos) ? det.trabalhos : [];
                        if (trabalhos.length === 0) return;

                        // Montar items a partir do fallback de detalhes
                        const bucket = { enabled: true, items: {} };
                        trabalhos.forEach(t => {
                            const trabNomeNorm = (t.trabalho_nome || '')
                                .toString()
                                .replace(/\s*\([^)]*\)\s*$/, '')
                                .trim();
                            const trabKey = (t.trabalho_id != null)
                                ? String(t.trabalho_id)
                                : (trabNomeNorm || '-');
                            const trabLabel = (t.trabalho_nome && t.trabalho_nome.toString().trim())
                                ? t.trabalho_nome.toString().replace(/\s*\([^)]*\)\s*$/, '').trim()
                                : (trabNomeNorm || `Trabalho #${trabKey}`);
                            const qtyRaw = (t.ultima_quantidade != null ? t.ultima_quantidade : '-');
                            const qty = Number.isFinite(Number(qtyRaw)) ? Number(qtyRaw) : '-';
                            bucket.items[trabKey] = { trab: trabLabel, qty };
                        });

                        // Deduplicar por nome normalizado (preferir chave numérica e maior qty)
                        try {
                            const byLabel = {};
                            const dedup = {};
                            Object.entries(bucket.items || {}).forEach(([k, v]) => {
                                if (!v) return;
                                const label = normalizeTrabLabel(v.trab);
                                if (!label) return;
                                const isId = /^\d+$/.test(k);
                                const qtyNum = Number.isFinite(Number(v.qty)) ? Number(v.qty) : Number.NEGATIVE_INFINITY;
                                if (!byLabel[label]) {
                                    byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                                } else {
                                    const cur = byLabel[label];
                                    const better = (isId && !cur.isId) || (!isId && !cur.isId && qtyNum > cur.qty) || (isId && cur.isId && qtyNum > cur.qty);
                                    if (better) byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                                }
                            });
                            Object.values(byLabel).forEach(({ key, val }) => { dedup[key] = val; });
                            bucket.items = dedup;
                        } catch {}

                        // Atualizar cache em memória e LS
                        current.enabled = true;
                        current.items = bucket.items;
                        try {
                            ls[String(ordemId)] = current.items;
                            localStorage.setItem(LS_KEY, JSON.stringify(ls));
                        } catch {}

                        // Notificar e forçar re-render agora usando os dados em cache
                        try { emitQptChange(ordemId); } catch (_) {}
                        // Resolver container dentro do cartão REAL ao limpar assinatura
                        try {
                            let cont = document.getElementById(`qtd-por-trabalho-${ordemId}`);
                            if (!cont) {
                                const cards = document.querySelectorAll(`[data-ordem-id="${ordemId}"]`);
                                for (const c of cards) {
                                    if (!c.classList.contains('fantasma')) {
                                        const scoped = c.querySelector(`#qtd-por-trabalho-${ordemId}`);
                                        if (scoped) { cont = scoped; break; }
                                    }
                                }
                            }
                            if (cont && cont.dataset) delete cont.dataset.qptSig;
                        } catch {}
                        try { window.atualizarQuantidadesPorTrabalho(ordemId, []); } catch {}
                        try { markQptTouch(ordemId); } catch {}
                    } catch (eDet) { console.warn('[QPT] falha ao aplicar detalhes para QPT', eDet); }
                })
                .catch(e => { try { console.debug('[QPT] detalhes indisponíveis', e); } catch {} })
                .finally(() => { try { delete window.__qptFetching[ordemId]; } catch {} });
        }
    } catch {}
}

// Disponibilizar no escopo global
try { window.atualizarQuantidadesPorTrabalho = atualizarQuantidadesPorTrabalho; } catch {}

// Semear/atualizar cache de QPT a partir de um apontamento individual (ex: após registrar quantidade no modal)
try {
    window.atualizarQPTCacheEntrada = function(ordemId, trabalhoId, trabalhoNome, itemCod, quantidade) {
        if (ordemId == null) return;
        const osId = parseInt(ordemId, 10);
        if (Number.isNaN(osId)) return;
        const trabId = (trabalhoId != null && trabalhoId !== '') ? String(trabalhoId) : '';
        // Normaliza nome do trabalho: remove sufixo final entre parênteses
        const trabNomeNorm = (trabalhoNome && trabalhoNome.trim())
            ? trabalhoNome.replace(/\s+/g, ' ').replace(/\s*\([^)]*\)\s*$/, '').trim()
            : '';
        const trabKey = (trabId !== '') ? trabId : (trabNomeNorm || '-');
        const trabNome = trabNomeNorm || (trabId ? `Trabalho #${trabId}` : `Trabalho #${trabKey}`);
        // Determinar a quantidade final: preferir numérica informada; caso vazio, reaproveitar última do cache/LS (por trabalho)
        let qty;
        if (Number.isFinite(Number(quantidade))) {
            qty = Number(quantidade);
        } else {
            let prevQty = undefined;
            // Buscar no cache em memória
            try {
                if (window.__cacheQtdTrabalho && window.__cacheQtdTrabalho[osId] && window.__cacheQtdTrabalho[osId].items) {
                    const prev = window.__cacheQtdTrabalho[osId].items[trabKey];
                    if (prev && prev.qty !== undefined) prevQty = prev.qty;
                }
            } catch {}
            // Buscar no localStorage
            if (prevQty === undefined) {
                try {
                    const LS_KEY = 'qpt_cache_v1';
                    const lsObj = JSON.parse(localStorage.getItem(LS_KEY) || '{}');
                    const osEntry = lsObj[String(osId)];
                    if (osEntry) {
                        // Tentar formato novo (por trabalho)
                        if (osEntry[trabKey] && osEntry[trabKey].qty !== undefined) prevQty = osEntry[trabKey].qty;
                        // Compat: formato antigo -> procurar por mesmo nome de trabalho
                        if (prevQty === undefined) {
                            Object.values(osEntry).forEach(v => {
                                if (!v) return;
                                const vNome = (v.trab || '').toString().replace(/\s*\([^)]*\)\s*$/, '').trim().toLowerCase();
                                const tNome = trabNome.toLowerCase();
                                if (vNome && vNome === tNome && prevQty === undefined && v.qty !== undefined) prevQty = v.qty;
                            });
                        }
                    }
                } catch {}
            }
            if (Number.isFinite(Number(prevQty))) qty = Number(prevQty);
            else qty = '-';
        }

        window.__cacheQtdTrabalho = window.__cacheQtdTrabalho || {};
        const store = window.__cacheQtdTrabalho;
        if (!store[osId]) store[osId] = { enabled: false, items: {} };
        const current = store[osId];
        current.enabled = true;
        // Migrar chaves antigas por NOME -> ID, se aplicável
        try {
            const labelNew = normalizeTrabLabel(trabNome);
            Object.entries(current.items || {}).forEach(([k, v]) => {
                if (!v || k === trabKey) return;
                if (normalizeTrabLabel(v.trab) === labelNew && !/^\d+$/.test(k) && /^\d+$/.test(trabKey)) {
                    delete current.items[k];
                }
            });
        } catch {}

        current.items[trabKey] = { trab: trabNome, qty };

        // Deduplicar por nome normalizado (preferir chave numérica e maior qty)
        try {
            const byLabel = {};
            const dedup = {};
            Object.entries(current.items || {}).forEach(([k, v]) => {
                if (!v) return;
                const label = normalizeTrabLabel(v.trab);
                if (!label) return;
                const isId = /^\d+$/.test(k);
                const qtyNum = Number.isFinite(Number(v.qty)) ? Number(v.qty) : Number.NEGATIVE_INFINITY;
                if (!byLabel[label]) {
                    byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                } else {
                    const cur = byLabel[label];
                    const better = (isId && !cur.isId) || (!isId && !cur.isId && qtyNum > cur.qty) || (isId && cur.isId && qtyNum > cur.qty);
                    if (better) byLabel[label] = { key: k, val: v, isId, qty: qtyNum };
                }
            });
            Object.values(byLabel).forEach(({ key, val }) => { dedup[key] = val; });
            current.items = dedup;
        } catch {}

        // Persistir em localStorage
        const LS_KEY = 'qpt_cache_v1';
        let ls = {};
        try { ls = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch {}
        ls[String(osId)] = current.items;
        try { localStorage.setItem(LS_KEY, JSON.stringify(ls)); } catch {}
        // Notificar a mesma aba para atualização em tempo real
        try { emitQptChange(osId); } catch (_) {}

        // Re-renderizar imediatamente usando fallback de cache
        try {
            // Limpar assinatura anterior para forçar re-render, se existir (no cartão REAL)
            try {
                let cont = document.getElementById(`qtd-por-trabalho-${osId}`);
                if (!cont) {
                    const cards = document.querySelectorAll(`[data-ordem-id="${osId}"]`);
                    for (const c of cards) {
                        if (!c.classList.contains('fantasma')) {
                            const scoped = c.querySelector(`#qtd-por-trabalho-${osId}`);
                            if (scoped) { cont = scoped; break; }
                        }
                    }
                }
                if (cont && cont.dataset) delete cont.dataset.qptSig;
            } catch {}
            atualizarQuantidadesPorTrabalho(osId, []);
            // Marcar toque recente para evitar renders redundantes em seguida
            try { markQptTouch(osId); } catch {}
        } catch {}
        try { console.debug('[QPT] cache semeado via entrada', { osId, trabId, /* item ignorado no novo modelo */ qty }); } catch {}
    }
} catch {}

// Função para atualizar completamente o status visual de um card
function atualizarStatusCartaoCompleto(ordemId, statusAtual) {
    // Buscar TODOS os cartões com essa ordem e verificar qual é o real
    const allCards = document.querySelectorAll(`[data-ordem-id="${ordemId}"]`);
    let card = null;
    for (const c of allCards) {
        if (!c.classList.contains('fantasma')) {
            card = c;
            break;
        }
    }
    
    if (!card) {
        console.warn(`Card REAL não encontrado para OS ${ordemId}`);
        return;
    }
    
    // Obter botões de apontamento
    const botoesContainer = card.querySelector('.apontamento-buttons');
    if (!botoesContainer) {
        console.warn(`Contêiner de botões não encontrado para OS ${ordemId}`);
        return;
    }
    
    // Remover todas as classes de status anteriores
    card.classList.remove('status-setup', 'status-producao', 'status-pausado', 'status-finalizado');
    
    // Mapear o status para classe CSS e configuração de botões
    let statusClass = '';
    let botoesMostrar = [];
    
    switch (statusAtual) {
        case 'Setup em andamento':
            statusClass = 'status-setup';
            botoesMostrar = ['fim_setup'];
            break;
        case 'Setup concluído':
            statusClass = 'status-setup-concluido';
            botoesMostrar = ['inicio_producao'];
            break;
        case 'Produção em andamento':
            statusClass = 'status-producao';
            // Exibir tanto pausa quanto stop durante a produção
            botoesMostrar = ['pausa', 'stop'];
            break;
        case 'Pausado':
            statusClass = 'status-pausado';
            botoesMostrar = ['inicio_producao'];
            break;
        case 'Finalizado':
            statusClass = 'status-finalizado';
            botoesMostrar = [];
            break;
        default: // 'Aguardando'
            statusClass = '';
            botoesMostrar = ['inicio_setup'];
    }
    
    // Adicionar a classe de status
    if (statusClass) card.classList.add(statusClass);
    
    // Atualizar o status visual no card
    let statusIndicador = card.querySelector('.status-indicador');
    if (!statusIndicador) {
        statusIndicador = document.createElement('div');
        statusIndicador.className = 'status-indicador badge';
        const cardHeader = card.querySelector('.kanban-card-header');
        if (cardHeader) {
            cardHeader.appendChild(statusIndicador);
        }
    }
    
    // Definir classe e texto para o indicador de status
    statusIndicador.className = 'status-indicador badge';
    switch (statusClass) {
        case 'status-setup':
            statusIndicador.classList.add('bg-primary');
            statusIndicador.textContent = 'Setup';
            break;
        case 'status-setup-concluido':
            statusIndicador.classList.add('bg-info');
            statusIndicador.textContent = 'Setup Concluído';
            break;
        case 'status-producao':
            statusIndicador.classList.add('bg-success');
            statusIndicador.textContent = 'Produção';
            break;
        case 'status-pausado':
            statusIndicador.classList.add('bg-warning');
            statusIndicador.textContent = 'Pausado';
            break;
        case 'status-finalizado':
            statusIndicador.classList.add('bg-secondary');
            statusIndicador.textContent = 'Finalizado';
            break;
        default:
            statusIndicador.classList.add('bg-light', 'text-dark');
            statusIndicador.textContent = 'Aguardando';
    }
    
    // Ocultar todos os botões primeiro
    const botoes = botoesContainer.querySelectorAll('button');
    botoes.forEach(botao => {
        botao.style.display = 'none';
    });
    
    // Mostrar apenas os botões relevantes para o status atual
    botoesMostrar.forEach(botaoTipo => {
        const botao = botoesContainer.querySelector(`button[data-acao="${botaoTipo}"]`);
        if (botao) botao.style.display = 'inline-block';
    });
    
    // Adicionar ou atualizar o timer de apontamento
    let timerElement = card.querySelector('.apontamento-timer');
    if (!timerElement) {
        timerElement = document.createElement('div');
        timerElement.className = 'apontamento-timer';
        // Adicionar o timer após o indicador de status
        if (statusIndicador.parentNode) {
            statusIndicador.parentNode.insertBefore(timerElement, statusIndicador.nextSibling);
        }
    }
    
    // Se o status for ativo, iniciar o timer (pausado não é ativo)
    if (statusClass === 'status-setup' || statusClass === 'status-producao') {
        iniciarTimerApontamento(ordemId, statusClass);
    } else {
        // Se não for um status ativo, parar o timer e ocultar o elemento
        pararTimerApontamento(ordemId);
        timerElement.style.display = 'none';
    }
    
    console.log(`Status visual atualizado para OS ${ordemId}: ${statusAtual}`);
}

// Função para carregar logs para um card específico
function carregarLogsParaCard(ordemId) {
    fetch(`/apontamento/os/${ordemId}/logs`)
        .then(response => response.json())
        .then(data => {
            if (data.logs && data.logs.length > 0) {
                console.log(`Logs carregados para OS ${ordemId}: ${data.logs.length} registros`);
                // Se a função existir (importada do apontamento-logs.js)
                if (typeof adicionarLogsAoCard === 'function') {
                    adicionarLogsAoCard(ordemId, data.logs);
                }
            } else {
                console.log(`Nenhum log encontrado para OS ${ordemId}`);
            }
        })
        .catch(error => console.error(`Erro ao carregar logs para OS ${ordemId}:`, error));
}

// Função para adicionar indicador visual de operador em um card
function adicionarIndicadorOperador(ordemId, operadorNome, operadorCodigo) {
    // Buscar cartão real, ignorando fantasma
    const allCards = document.querySelectorAll(`[data-ordem-id="${ordemId}"]`);
    let card = null;
    for (const c of allCards) {
        if (!c.classList.contains('fantasma')) {
            card = c;
            break;
        }
    }
    if (!card) return;
    
    // Remover indicador existente se houver
    const indicadorExistente = card.querySelector('.operador-indicator');
    if (indicadorExistente) indicadorExistente.remove();
    
    // Criar novo indicador
    const indicador = document.createElement('div');
    indicador.className = 'operador-indicator mt-2 small';
    indicador.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-user-hard-hat me-1"></i>
            <span>${operadorNome} (${operadorCodigo})</span>
        </div>
    `;
    
    // Adicionar ao card
    const cardBody = card.querySelector('.kanban-card-body');
    if (cardBody) {
        // Adicionar antes dos logs se existirem
        const logs = cardBody.querySelector('.logs-card-summary');
        if (logs) {
            logs.before(indicador);
        } else {
            cardBody.appendChild(indicador);
        }
    }
    
    console.log(`Indicador de operador adicionado para OS ${ordemId}: ${operadorNome}`);
}

// Garantir que a função atualizarStatusCartao seja chamada corretamente
const originalAtualizarStatusCartao = window.atualizarStatusCartao || function() {};

// Remover a interceptação para evitar duplicidade de funções
// Agora usaremos diretamente a função atualizarStatusCartao do HTML que foi melhorada

/**
 * Desabilita os botões de apontamento quando o operador atual for diferente do operador logado
 * @param {number} ordemId - ID da ordem de serviço
 * @param {string} operadorNome - Nome do operador atual
 */
function desabilitarBotoesOperadorDiferente(ordemId, operadorNome) {
    // Buscar cartão real, ignorando fantasma
    const allCards = document.querySelectorAll(`[data-ordem-id="${ordemId}"]`);
    let card = null;
    for (const c of allCards) {
        if (!c.classList.contains('fantasma')) {
            card = c;
            break;
        }
    }
    if (!card) return;
    
    const botoesApontamento = card.querySelectorAll('.apontamento-btn');
    botoesApontamento.forEach(botao => {
        // Desabilitar botões que afetam o status (exceto início de setup/produção)
        if (['fim_setup', 'pausa', 'stop'].includes(botao.getAttribute('data-acao'))) {
            botao.disabled = true;
            botao.setAttribute('title', `Apenas ${operadorNome} pode modificar este apontamento`);
            botao.classList.add('btn-disabled');
        }
    });
    
    // Adicionar aviso visual ao card
    const avisoElement = document.createElement('div');
    avisoElement.className = 'apontamento-aviso-operador mt-1 small text-warning';
    avisoElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Em uso por: ${operadorNome}`;
    
    const cardBody = card.querySelector('.kanban-card-body');
    if (cardBody) {
        const avisoExistente = cardBody.querySelector('.apontamento-aviso-operador');
        if (!avisoExistente) {
            cardBody.appendChild(avisoElement);
        }
    }
}

// Função para iniciar o timer de apontamento
function iniciarTimerApontamento(ordemId, statusClass, startTimeStr = null) {
    const card = document.querySelector(`.kanban-card[data-ordem-id="${ordemId}"]`);
    if (!card) return;
    
    // Buscar o timer no campo de status inferior
    const statusElement = card.querySelector('.status-apontamento');
    let timerElement = card.querySelector(`#timer-${ordemId}`);
    
    if (!timerElement && statusElement) {
        // Se não encontrar o timer, mas encontrar o campo de status, criar um novo timer
        timerElement = document.createElement('span');
        timerElement.className = 'apontamento-timer';
        timerElement.id = `timer-${ordemId}`;
        statusElement.appendChild(timerElement);
    } else if (!timerElement) {
        // Se não encontrar nem o timer nem o campo de status, criar um timer no corpo do card
        timerElement = document.createElement('span');
        timerElement.className = 'apontamento-timer';
        timerElement.id = `timer-${ordemId}`;
        const cardBody = card.querySelector('.kanban-card-body');
        if (cardBody) {
            cardBody.appendChild(timerElement);
        }
    }
    
    // Mostrar o timer
    timerElement.style.display = 'inline-block';
    
    // Parar qualquer timer existente para esta OS
    pararTimerApontamento(ordemId);
    
    // Determinar o tempo de início
    const startTime = startTimeStr ? new Date(startTimeStr) : new Date();
    const startTimestamp = startTime.getTime();
    
    // Salvar o tempo de início no localStorage para persistência local
    try {
        const timerData = JSON.parse(localStorage.getItem('apontamento_timers') || '{}');
        timerData[ordemId] = {
            startTime: startTime.toISOString(),
            startTimestamp: startTimestamp, // Salvar como timestamp para evitar problemas de fuso
            statusClass: statusClass
        };
        localStorage.setItem('apontamento_timers', JSON.stringify(timerData));
    } catch (e) {
        console.error('Erro ao salvar timer no localStorage:', e);
    }
    
    // Iniciar novo timer usando timestamp para evitar problemas de fuso horário
    timers[ordemId] = setInterval(() => {
        const currentTimestamp = new Date().getTime();
        const elapsedTime = Math.max(0, Math.floor((currentTimestamp - startTimestamp) / 1000)); // Garantir que nunca seja negativo
        const hours = Math.floor(elapsedTime / 3600);
        const minutes = Math.floor((elapsedTime % 3600) / 60);
        const seconds = elapsedTime % 60;
        
        if (timerElement) {
            timerElement.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    }, 1000);
}

// Função para parar o timer de apontamento
function pararTimerApontamento(ordemId) {
    if (timers[ordemId]) {
        clearInterval(timers[ordemId]);
        delete timers[ordemId];
    }
}

// Objeto para armazenar os timers ativos
const timers = {};

// Sistema de inicialização coordenada
let _sistemaInicializado = false;

function inicializarSistemaApontamentos() {
    if (_sistemaInicializado) {
        console.debug('Sistema de apontamentos já foi inicializado, ignorando');
        return;
    }
    _sistemaInicializado = true;
    
    console.log('Inicializando sistema de persistência de apontamentos...');
    carregarEstadoApontamentos();
}

// Inicializar ao carregar a página
document.addEventListener('DOMContentLoaded', function() {
    // Pequeno delay para evitar conflitos com outros scripts
    setTimeout(inicializarSistemaApontamentos, 100);
});

// Expor função para inicialização manual
window.inicializarSistemaApontamentos = inicializarSistemaApontamentos;

// Expor função para recarregar estado a partir de outros scripts
window.recarregarEstadoApontamentos = carregarEstadoApontamentos;

// Expor utilitários de coordenação
try { window.markQptTouch = markQptTouch; } catch {}
try { window.shouldSkipQpt = shouldSkipQpt; } catch {}

// Atualiza a "Última qtd" visível no card da OS
window.atualizarUltimaQuantidadeNoCard = function(ordemId, ultimaQuantidade) {
    try {
        const span = document.getElementById(`ultima-qtd-${ordemId}`);
        if (span) {
            const valor = (ultimaQuantidade ?? 0);
            span.textContent = Number.isFinite(Number(valor)) ? valor : '-';
        }
    } catch (e) {
        console.warn('Não foi possível atualizar a última quantidade no card:', e);
    }
}
