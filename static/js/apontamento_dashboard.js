// Apontamento Dashboard: detailed active cards with live timers and analytics
(function() {
  const STATE = {
    lastData: null,
    timerId: null,
    refreshId: null,
    // Mantém o maior valor de quantidade já visto por OS e por trabalho para evitar regressão visual
    // Chaves: `os:<ordem_servico_id>` e `os:<ordem_servico_id>:trab:<trabalho_id|nome|idx>`
    progressCache: new Map()
  };

  // Persistência local por aba/navegador para manter último progresso mesmo após reload
  function lsKey(key) { return `ap_dash_qty:${key}`; }
  function getStoredQty(key) {
    try {
      const v = localStorage.getItem(lsKey(key));
      return v != null ? (parseInt(v, 10) || 0) : 0;
    } catch (_) { return 0; }
  }
  function setStoredQty(key, val) {
    try {
      localStorage.setItem(lsKey(key), String(val || 0));
    } catch (_) { /* noop */ }
  }

  // Normaliza nomes para chaves estáveis (sem acentos, minúsculo, underscores)
  function normalizeKey(s) {
    try {
      return (s || '')
        .toString()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
    } catch (_) {
      return (s || '').toString().trim().toLowerCase();
    }
  }

  // Gera chave estável por trabalho dentro da OS (prefere nome do trabalho)
  function trabKey(st, t, idx) {
    const osId = st?.ordem_servico_id ?? st?.os_id ?? st?.id ?? 'os';
    const nome = t?.trabalho_nome || t?.nome || t?.maquina_nome || t?.tipo_trabalho || '';
    const base = normalizeKey(nome) || (t?.trabalho_id ? `id${t.trabalho_id}` : (t?.id ? `id${t.id}` : `t${idx}`));
    return `os:${osId}:trab:${base}`;
  }

  // Chave estável por OS
  function osKey(st) {
    const osId = st?.ordem_servico_id ?? st?.os_id ?? st?.id ?? 'os';
    return `os:${osId}`;
  }

  function fmtSecs(total) {
    if (total == null || isNaN(total)) return '-';
    total = Math.max(0, parseInt(total, 10));
    const h = Math.floor(total / 3600).toString().padStart(2, '0');
    const m = Math.floor((total % 3600) / 60).toString().padStart(2, '0');
    const s = Math.floor(total % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
  }

  function badge(cls, text) {
    return `<span class="badge bg-${cls}">${text}</span>`;
  }

  function statusBadge(status, isGhost = false) {
    const map = {
      'Setup em andamento': 'info',
      'Produção em andamento': 'success',
      'Pausado': 'warning',
      'Finalizado': 'dark',
      'Fantasma': 'light text-dark'
    };
    const badgeClass = map[status] || 'secondary';
    const ghostIcon = isGhost ? '<i class="fas fa-ghost me-1"></i>' : '';
    return `<span class="badge bg-${badgeClass}">${ghostIcon}${status || 'Desconhecido'}</span>`;
  }

  function perfBadge(valor) {
    const map = {
      'Excelente': 'success',
      'Dentro do esperado': 'primary',
      'Abaixo do esperado': 'danger'
    };
    if (!valor) return '';
    return `<span class="badge bg-${map[valor] || 'secondary'}">${valor}</span>`;
  }

  function parseStart(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }

  function secondsSince(start) {
    if (!start) return 0;
    return Math.floor((Date.now() - start.getTime()) / 1000);
  }

  // Build the detailed card HTML for a single status item (simplified view)
  function buildDetailedCard(st) {
    const statusToClass = (st) => {
      const s = st.status_atual;
      if (s === 'Setup em andamento') return 'status-setup';
      if (s === 'Produção em andamento') return 'status-producao';
      if (s === 'Pausado') return 'status-pausa';
      if (s === 'Finalizado') return 'status-finalizado';
      if (s === 'Fantasma' || st.is_ghost_card) return 'status-fantasma';
      return 'status-neutro';
    };

    const os = st.os_numero || `OS-${st.ordem_servico_id}`;
    const isGhost = st.is_ghost_card === true;
    const ativos = Array.isArray(st.ativos_por_trabalho) ? st.ativos_por_trabalho : [];
    // Se for um cartão fantasma, ainda precisamos verificar status do cartão real
    // mas ainda mantemos o badge específico para cartões fantasma
    const isRunning = (st.cronometro && st.cronometro.tipo === 'producao') || 
                     st.status_atual === 'Produção em andamento' || 
                     (Array.isArray(ativos) && ativos.some(a => a.status === 'Produção em andamento'));
    
    // Para cartões fantasma, mostrar informações específicas
    const ghostInfo = isGhost ? {
      posicao: st.posicao_fila || 1,
      observacoes: st.observacoes || '',
      criadoPor: st.criado_por_nome || '',
      dataCriacao: st.data_criacao ? new Date(st.data_criacao).toLocaleDateString('pt-BR') : ''
    } : null;
    
    // Resumo de contagens por status (fallback se backend não enviar)
    const resumo = st.resumo_status || (() => {
      const c = { setup: 0, pausado: 0, producao: 0 };
      ativos.forEach(a => {
        const s = (a.status || '').toLowerCase();
        if (s.includes('setup')) c.setup++;
        else if (s.includes('pausado')) c.pausado++;
        else if (s.includes('produção') || s.includes('producao')) c.producao++;
      });
      return c;
    })();

    const total = parseInt(st.quantidade_total ?? 0, 10) || 0;
    let ultima = parseInt(st.ultima_quantidade ?? 0, 10) || 0;
    // Progresso da OS não deve regredir: usar maior entre servidor e cache
    const keyOS = osKey(st);
    const cachedMemOS = STATE.progressCache.get(keyOS) || 0;
    const cachedLocalOS = getStoredQty(keyOS) || 0;
    ultima = Math.max(ultima, cachedMemOS, cachedLocalOS);
    STATE.progressCache.set(keyOS, ultima);
    setStoredQty(keyOS, ultima);
    const pct = total > 0 ? Math.max(0, Math.min(100, Math.round((ultima / total) * 100))) : 0;

    const imgMain = st.item_imagem_path ? `<img src="${st.item_imagem_path}" alt="Imagem do item" class="rounded border me-2 ${isRunning ? 'thumb-running' : ''}" style="width:80px;height:80px;object-fit:cover;">` : '';
    const clientes = Array.isArray(st.clientes_quantidades)
      ? st.clientes_quantidades
      : (st.cliente_nome ? [{ cliente_nome: st.cliente_nome, quantidade: total }] : []);
    const clientesHtml = clientes.length
      ? `<div class="small text-muted">${clientes.map(c => `${c.cliente_nome}: ${parseInt(c.quantidade ?? 0, 10) || 0}`).join(' • ')}</div>`
      : '';

    const trabs = Array.isArray(st.trabalhos_do_item) ? st.trabalhos_do_item : [];
    const statusBarClass = (s) => {
      s = (s || '').toLowerCase();
      if (s.includes('setup')) return 'bg-info';
      if (s.includes('paus')) return 'bg-warning';
      if (s.includes('produ')) return 'bg-success';
      if (s.includes('final')) return 'bg-dark';
      return 'bg-secondary';
    };
    const trabalhosHtml = trabs.map((t, idx) => {
      // Quantidade não deve regredir: usar o maior entre servidor e cache
      let u = parseInt(t.ultima_quantidade ?? 0, 10) || 0;
      const cacheKey = trabKey(st, t, idx);
      const cachedMem = STATE.progressCache.get(cacheKey) || 0;
      const cachedLocal = getStoredQty(cacheKey) || 0;
      u = Math.max(u, cachedMem, cachedLocal);
      STATE.progressCache.set(cacheKey, u);
      setStoredQty(cacheKey, u);
      const pctT = total > 0 ? Math.max(0, Math.min(100, Math.round((u / total) * 100))) : 0;
      const barCls = statusBarClass(t.status);
      const nameKey = normalizeKey(t.trabalho_nome || 'Serviço');
      return `
        <div class="mb-3" data-trab-name-key="${nameKey}" data-trab-id="${t.trabalho_id ?? ''}">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <div class="fw-semibold" data-trab-name="${t.trabalho_nome || 'Serviço'}">${t.trabalho_nome || 'Serviço'}</div>
            <div class="small text-muted">${t.status || ''}</div>
          </div>
          <div class="progress" style="height: 10px;">
            <div class="progress-bar ${barCls}" data-progress-bar="1" role="progressbar" style="width: ${pctT}%;" aria-valuenow="${pctT}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
          <div class="d-flex justify-content-between small text-muted mt-1">
            <div class="ultima-qtd" data-ultima-qtd="${u}" data-total="${total}">Última qtd: ${u} / ${total} (${pctT}%)</div>
            <div class="d-flex gap-2">
              <span>Setup: ${fmtSecs(t.tempo_setup_utilizado)}</span>
              <span>Pausas: ${fmtSecs(t.tempo_pausas_utilizado)}</span>
              <span>Rodando: ${fmtSecs(t.tempo_producao_utilizado)}</span>
            </div>
          </div>
        </div>`;
    }).join('');
    return `
      <div class="card mb-3 ${statusToClass(st)}" data-os-id="${st.ordem_servico_id ?? st.os_id ?? st.id}">
        <div class="card-header">
          <div class="row align-items-center">
            <div class="col-4 d-flex align-items-center">
              ${imgMain}
              <div>
                <div class="fw-bold">${os}</div>
                <div class="small text-muted">${st.item_codigo || ''} ${st.item_nome || ''}</div>
                <div class="small">
                  <span class="text-muted">Total:</span> <span class="fw-bold">${total}</span>
                </div>
                ${clientesHtml}
              </div>
            </div>
            <div class="col-4 text-center">
              <!-- Nome da lista removido - agora usamos agrupamento por máquina -->
            </div>
            <div class="col-4 text-end">
              ${statusBadge(st.status_atual, isGhost)}
              ${isGhost ? `<div class="small text-muted mt-1">Posição: ${ghostInfo.posicao}</div>` : ''}
            </div>
          </div>
        </div>
        <div class="card-body">
          ${isGhost ? `
            <div class="alert alert-light border-2" style="border-left: 4px solid #6c757d;">
              <div class="row">
                <div class="col-md-6">
                  <div class="mb-2">
                    <i class="fas fa-ghost me-2"></i>
                    <strong>Cartão Fantasma</strong>
                  </div>
                  ${ghostInfo.observacoes ? `<div class="small"><strong>Observações:</strong> ${ghostInfo.observacoes}</div>` : ''}
                  ${ghostInfo.criadoPor ? `<div class="small text-muted">Criado por: ${ghostInfo.criadoPor}</div>` : ''}
                  ${ghostInfo.dataCriacao ? `<div class="small text-muted">Data: ${ghostInfo.dataCriacao}</div>` : ''}
                </div>
                <div class="col-md-6">
                  <div class="small text-muted">
                    <div><strong>OS Original:</strong> ${os}</div>
                    <div><strong>Posição na fila:</strong> ${ghostInfo.posicao}</div>
                    ${st.trabalho_nome ? `<div><strong>Trabalho:</strong> ${st.trabalho_nome}</div>` : ''}
                  </div>
                </div>
              </div>
            </div>
          ` : trabalhosHtml || '<div class="small text-muted">Sem serviços cadastrados para o item.</div>'}
        </div>
        <div class="card-footer d-flex gap-2">
          ${isGhost ? `` : `
            <button class="btn btn-outline-primary btn-sm" onclick="verLogs(${st.ordem_servico_id})"><i class="fas fa-history"></i> Logs</button>
            <button class="btn btn-outline-secondary btn-sm" onclick="verDetalhes(${st.ordem_servico_id})"><i class="fas fa-eye"></i> Detalhes</button>
          `}
        </div>
      </div>`;
  }

  function renderSummary(data) {
    const list = data.status_ativos || [];
    const total = list.length;
    const emSetup = list.filter(x => (x.cronometro && x.cronometro.tipo === 'setup') || x.status_atual === 'Setup em andamento').length;
    const pausados = list.filter(x => (x.cronometro && x.cronometro.tipo === 'pausa') || x.status_atual === 'Pausado' || (Array.isArray(x.ativos_por_trabalho) && x.ativos_por_trabalho.some(a => a.status === 'Pausado'))).length;
    const emProducao = list.filter(x => (x.cronometro && x.cronometro.tipo === 'producao') || x.status_atual === 'Produção em andamento').length;

    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };
    setText('total-ativos', total);
    setText('em-setup', emSetup);
    setText('pausados', pausados);
    setText('em-producao', emProducao);
  }

  function renderCards(data) {
    const container = document.getElementById('cards-ativos');
    if (!container) return;

    const list = data.status_ativos || [];
    console.log('Renderizando cartões:', list.length, 'itens recebidos');
    
    // Mapear ordens de serviço que tem ativos por trabalho para depois atualizar status
    const ordemIdsComAtivos = new Map();

    // Preparar conjunto de chaves presentes para limpeza do cache ao final
    const presentKeys = new Set();
    list.forEach(st => {
      if (st && (st.ordem_servico_id != null || st.os_id != null || st.id != null)) {
        presentKeys.add(osKey(st));
        const trabs = Array.isArray(st.trabalhos_do_item) ? st.trabalhos_do_item : [];
        trabs.forEach((t, idx) => {
          presentKeys.add(trabKey(st, t, idx));
        });
        
        // Coletar ordem e ativos por trabalho para atualização de status
        const ordemId = st.ordem_servico_id ?? st.os_id ?? st.id;
        if (ordemId && Array.isArray(st.ativos_por_trabalho)) {
          ordemIdsComAtivos.set(ordemId, st.ativos_por_trabalho);
        }
      }
    });

    // Canonicalize machine names using dropdown options (case-insensitive)
    const selLista = document.getElementById('filter-lista');
    const canonMap = new Map(
      Array.from(selLista?.options || [])
        .map(o => [String(o.value || '').trim().toLowerCase(), o.value])
        .filter(([k, v]) => v && v !== 'Todas')
    );

    // Group by lista_kanban (nome da máquina), using canonical name when available
    const groupsByMachine = new Map();
    list.forEach(st => {
      const raw = (st.lista_kanban || 'Sem Máquina').toString().trim();
      const maquina = canonMap.get(raw.toLowerCase()) || raw;
      if (!groupsByMachine.has(maquina)) {
        groupsByMachine.set(maquina, []);
      }
      groupsByMachine.get(maquina).push(st);
    });

    console.log('Grupos por máquina:', Array.from(groupsByMachine.keys()));

    // Determinar se há filtros por múltiplas listas selecionadas
    let selecionadas = [];
    if (selLista) {
      const opts = Array.from(selLista.selectedOptions || []).map(o => o.value);
      selecionadas = opts.filter(v => v && v !== 'Todas');
    }

    let todasMaquinas;
    if (selecionadas.length > 0) {
      // Filtrar para renderizar apenas as máquinas selecionadas (existentes nos dados)
      todasMaquinas = selecionadas.filter(m => groupsByMachine.has(m));
    } else {
      // Sem filtro: buscar máquinas conhecidas no dropdown e também as presentes nos dados
      const maquinasConhecidas = Array.from(selLista?.options || [])
        .map(o => o.value)
        .filter(v => v && v !== 'Todas');
      const maquinasDosDados = Array.from(groupsByMachine.keys());
      todasMaquinas = Array.from(new Set([...maquinasConhecidas, ...maquinasDosDados]));
      // Ordenar conforme a ordem do dropdown; desconhecidas vão para o final em ordem alfabética
      const ordem = new Map(todasMaquinas.map((m, idx) => [m, maquinasConhecidas.indexOf(m) === -1 ? 1e6 + idx : maquinasConhecidas.indexOf(m)]));
      todasMaquinas.sort((a, b) => (ordem.get(a) - ordem.get(b)) || a.localeCompare(b));
    }
    
    // Build HTML for each machine
    const groupSections = [];
    todasMaquinas.forEach(maquina => {
      const items = groupsByMachine.get(maquina) || [];

      // Funções auxiliares para ranking de status e posição numérica
      const statusOrder = {
        'Produção em andamento': 1,
        'Setup em andamento': 2,
        'Pausado': 3,
        'Aguardando': 4
      };
      const getStatusRank = (s) => statusOrder[s] || 5;
      const getPos = (it) => {
        const p = parseInt(it?.posicao ?? it?.posicao_fila ?? 0, 10);
        return Number.isFinite(p) ? p : 0;
      };

      // Escolher principal pelo melhor status, desempate por menor posição
      let principal = null;
      if (items.length > 0) {
        principal = items.reduce((best, it) => {
          if (!best) return it;
          const rb = getStatusRank(best.status_atual);
          const ri = getStatusRank(it.status_atual);
          if (ri !== rb) return ri < rb ? it : best;
          const pb = getPos(best);
          const pi = getPos(it);
          return pi < pb ? it : best;
        }, null);
      }

      // Restante da fila ordenada por posição (desempate por status rank)
      const fila = principal
        ? items.filter(it => it !== principal).sort((a, b) => (getPos(a) - getPos(b)) || (getStatusRank(a.status_atual) - getStatusRank(b.status_atual)))
        : [];
      const isRunningMachine = items.some(x => (x.cronometro && x.cronometro.tipo === 'producao') || x.status_atual === 'Produção em andamento' || (Array.isArray(x.ativos_por_trabalho) && x.ativos_por_trabalho.some(a => a.status === 'Produção em andamento')));
      
      // Informações da máquina (cor e tipo do primeiro item ou padrões)
      const cor = principal?.lista_cor || '';
      const tipo = principal?.lista_tipo || '';

      // Cartão principal ou placeholder
      const cartaoPrincipalHTML = principal ? 
        buildDetailedCard(principal) : 
        `<div class="card border-secondary">
           <div class="card-body text-center text-muted">
             <i class="fas fa-inbox fa-2x mb-2"></i>
             <div>Sem cartão ativo</div>
           </div>
         </div>`;

      // Fila ou placeholder (com miniaturas)
      const filaHTML = fila.length > 0 ? (
        `<div class="mt-3">
           <div class="fw-semibold mb-2"><i class="fas fa-list me-1"></i>Na fila (${fila.length})</div>
           <ul class="list-group">
             ${fila.map(it => {
               const itRunning = (it.cronometro && it.cronometro.tipo === 'producao') || it.status_atual === 'Produção em andamento' || (Array.isArray(it.ativos_por_trabalho) && it.ativos_por_trabalho.some(a => a.status === 'Produção em andamento'));
               const imgFila = it.item_imagem_path ? `<img src="${it.item_imagem_path}" alt="Imagem" class="rounded border me-2 ${itRunning ? 'thumb-running' : ''}" style="width:36px;height:36px;object-fit:cover;">` : '';
               // Quantidade da fila também não deve regredir: cache por OS
              const keyOSFila = osKey(it);
              let u = parseInt(it.ultima_quantidade ?? 0, 10) || 0;
              const cachedMem = STATE.progressCache.get(keyOSFila) || 0;
              const cachedLocal = getStoredQty(keyOSFila) || 0;
              u = Math.max(u, cachedMem, cachedLocal);
              STATE.progressCache.set(keyOSFila, u);
              setStoredQty(keyOSFila, u);
                return `<li class="list-group-item d-flex justify-content-between align-items-center">` +
                  `<div class="d-flex align-items-center">` +
                    `${imgFila}` +
                    `<div>` +
                      `<div class="fw-medium">${it.os_numero || ''}</div>` +
                     `<div class="small text-muted">${(it.item_codigo || '')} ${(it.item_nome || '')}</div>` +
                   `</div>` +
                 `</div>` +
                 `<div class="text-end">` +
                   `<span class="badge bg-secondary rounded-pill">Qtde: ${u}</span>` +
                   `<div class="small text-muted mt-1">${it.status_atual || 'Aguardando'}</div>` +
                 `</div>` +
               `</li>`;
             }).join('')}
           </ul>
         </div>`
      ) : (
        `<div class="mt-3">
           <div class="fw-semibold mb-2"><i class="fas fa-list me-1"></i>Na fila</div>
           <div class="text-center text-muted py-2 border rounded">
             <i class="fas fa-inbox me-1"></i>Sem cartões na fila
           </div>
         </div>`
      );

      groupSections.push(`
        <div class="mb-4 p-2 border rounded">
          <div class="d-flex align-items-center mb-3 border-bottom pb-2">
            <div class="h4 m-0">${maquina}${isRunningMachine ? ' <span class="machine-running-dot" title="Em produção"></span>' : ''}</div>
            ${cor ? `<span class="ms-2 badge" style="background-color:${cor};">&nbsp;</span>` : ''}
            ${tipo ? `<span class="ms-2 text-muted">(${tipo})</span>` : ''}
          </div>
          ${cartaoPrincipalHTML}
          ${filaHTML}
        </div>
      `);
    });

    // Se não há cartões, mostrar mensagem
    if (groupSections.length === 0) {
      container.innerHTML = `<div class=\"text-center text-muted py-3\">Nenhum cartão ativo</div>`;
    } else {
      container.innerHTML = `<div class=\"d-flex flex-column\">${groupSections.join('')}</div>`;
    }
    
    console.log('Renderizadas', todasMaquinas.length, 'máquinas:', todasMaquinas.join(', '));

    // Limpar entradas de cache que não pertencem mais ao conjunto presente
    try {
      for (const key of STATE.progressCache.keys()) {
        if (!presentKeys.has(key)) STATE.progressCache.delete(key);
      }
    } catch (_) { /* noop */ }
    
    // Atualizar chips de status para cada OS que tem ativos
    if (ordemIdsComAtivos.size > 0) {
      console.debug(`[CHIPS] Atualizando status de ${ordemIdsComAtivos.size} cartões após renderização`);
      // Dar tempo para o DOM ser atualizado antes de processar os status
      setTimeout(() => {
        ordemIdsComAtivos.forEach((ativos, ordemId) => {
          renderizarChipsStatus(ordemId, ativos);
        });
      }, 100);
    }
  }

  function tickTimers() {
    const els = document.querySelectorAll('[data-crono-start]');
    els.forEach(el => {
      const iso = el.getAttribute('data-crono-start');
      if (!iso) return;
      const start = new Date(iso);
      if (isNaN(start.getTime())) return;
      el.textContent = fmtSecs(secondsSince(start));
    });
  }

  // Reset any timer elements by removing their data-crono-start attribute
  function resetTimerElements(root) {
    try {
      const scope = root ? root : document;
      const timers = scope.querySelectorAll('[data-crono-start]');
      timers.forEach(t => {
        try { t.removeAttribute('data-crono-start'); } catch (_) { /* noop */ }
        try { t.textContent = '00:00:00'; } catch (_) { /* noop */ }
      });
    } catch (_) { /* noop */ }
  }

  // Função para renderizar chips de status para todos os cartões associados a uma OS
  function renderizarChipsStatus(ordemId, ativosLista) {
    // Buscar TODOS os cartões com essa ordem (reais e fantasmas) - usar data-os-id no dashboard
    const allCards = document.querySelectorAll(`[data-os-id="${ordemId}"]`);
    console.debug(`[CHIPS] Dashboard - Encontrados ${allCards.length} cartões para OS ${ordemId}`);
    
    if (allCards.length === 0) {
      console.debug(`[CHIPS] Dashboard - Nenhum cartão encontrado para OS ${ordemId}`);
      return;
    }

    // Garantir que ativosLista seja sempre um array válido
    if (!Array.isArray(ativosLista)) {
      console.debug(`[CHIPS] ativosLista não é array para OS ${ordemId}, inicializando vazio`);
      ativosLista = [];
    }
    
    // Extrair status e aplicar para todos os cartões da OS
    const statusInfo = determinarStatusAtivos(ativosLista);
    
    // Aplicar status em cada cartão (real ou fantasma)
    for (const card of allCards) {
      const isGhostCard = card.classList.contains('fantasma');
      
      // Encontrar container de status no cartão
      let statusContainer = card.querySelector('.card-header .col-4.text-end');
      if (!statusContainer) {
        console.debug(`[CHIPS] Container de status não encontrado para cartão da OS ${ordemId}`);
        continue;
      }
      
      // Atualizar status com badges apropriados
      let statusHTML = '';
      
      if (isGhostCard) {
        // Para cartões fantasma, mostrar badge fantasma mas também o status atual
        statusHTML = `<span class="badge bg-light text-dark"><i class="fas fa-ghost me-1"></i>Fantasma</span>`;
        if (statusInfo.emProducao) {
          statusHTML += ` <span class="badge bg-success">Produção</span>`;
        } else if (statusInfo.emSetup) {
          statusHTML += ` <span class="badge bg-info">Setup</span>`;
        } else if (statusInfo.pausado) {
          statusHTML += ` <span class="badge bg-warning">Pausado</span>`;
        }
      } else {
        // Para cartões reais, mostrar badge adequado ao status atual
        if (statusInfo.emProducao) {
          statusHTML = `<span class="badge bg-success">Produção em andamento</span>`;
        } else if (statusInfo.emSetup) {
          statusHTML = `<span class="badge bg-info">Setup em andamento</span>`;
        } else if (statusInfo.pausado) {
          statusHTML = `<span class="badge bg-warning">Pausado</span>`;
        } else {
          statusHTML = `<span class="badge bg-secondary">Aguardando</span>`;
        }
      }
      
      // Atualizar os chips de status no cartão
      const firstChild = statusContainer.firstChild;
      if (firstChild && firstChild.tagName === 'SPAN' && firstChild.classList.contains('badge')) {
        // Substituir primeiro badge existente
        firstChild.outerHTML = statusHTML;
      } else {
        // Adicionar no início do container
        statusContainer.innerHTML = statusHTML + statusContainer.innerHTML;
      }
    }
  }
  
  // Função auxiliar para determinar status agregado dos ativos por trabalho
  function determinarStatusAtivos(ativosLista) {
    const result = {
      emProducao: false,
      emSetup: false,
      pausado: false
    };
    
    if (!Array.isArray(ativosLista)) return result;
    
    // Verificar todos os itens ativos para determinar status agregado
    for (const ativo of ativosLista) {
      const status = (ativo.status || '').toLowerCase();
      if (status.includes('produ')) {
        result.emProducao = true;
      } else if (status.includes('setup')) {
        result.emSetup = true;
      } else if (status.includes('paus')) {
        result.pausado = true;
      }
    }
    
    return result;
  }

  // Handle stop broadcasts coming from other tabs to immediately stop timers on the dashboard
  function handleBroadcastStop(payload) {
    try {
      if (payload && payload.osId != null) {
        // Try to scope the reset to the specific OS card when possible
        const card = document.querySelector(`.card[data-os-id="${payload.osId}"]`) || document.querySelector(`[data-os-id="${payload.osId}"]`);
        if (card) {
          resetTimerElements(card);
        } else {
          resetTimerElements(null);
        }
      } else {
        // Fallback: clear all timers
        resetTimerElements(null);
      }
      
      // Refresh data to reflect latest statuses and prevent stale UI
      try { fetchAndRender(); } catch (_) { /* noop */ }
    } catch (e) {
      console.debug('Falha ao resetar timers do dashboard no stop broadcast:', e);
    }
  }

  function onStorage(ev) {
    if (!ev || ev.key !== 'apontamento_broadcast') return;
    let payload = null;
    try {
      payload = JSON.parse(ev.newValue || 'null');
    } catch (_) { payload = null; }
    if (!payload || typeof payload !== 'object') return;
    if (payload.type === 'stop') {
      handleBroadcastStop(payload);
    }
  }

  async function fetchAndRender() {
    try {
      // Read filters from UI
      const selLista = document.getElementById('filter-lista');
      const selStatus = document.getElementById('filter-status');
      
      // Aplicar filtros (lista múltipla; status múltiplo)
      let listaParam = null;
      if (selLista) {
        const selectedListas = Array.from(selLista.selectedOptions || []).map(o => o.value);
        const cleanedListas = selectedListas.filter(v => v && v !== 'Todas');
        if (cleanedListas.length > 0) {
          listaParam = cleanedListas.join(',');
        }
      }
      let statusParam = null;
      if (selStatus) {
        const selected = Array.from(selStatus.selectedOptions || []).map(o => o.value);
        const cleaned = selected.filter(v => v && v !== 'Todos');
        if (cleaned.length > 0) {
          statusParam = cleaned.join(',');
        }
      }

      const params = new URLSearchParams();
      if (listaParam) params.set('lista', listaParam);
      if (statusParam) params.set('status', statusParam);
      
      console.log('Aplicando filtros:', { lista: listaParam, status: statusParam });

      const url = params.toString() ? `/apontamento/status-ativos?${params.toString()}` : '/apontamento/status-ativos';
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      STATE.lastData = data;
      renderSummary(data);
      renderCards(data);
    } catch (e) {
      console.error('Falha ao carregar status-ativos', e);
    }
  }

  function init() {
    // Restaurar seleção da lista Kanban, se existir
    try {
      // Suporte legado (chave antiga) e nova chave para múltiplas listas
      const savedListaLegacy = localStorage.getItem('dashboard_lista_kanban');
      const savedListasCsv = localStorage.getItem('dashboard_listas_kanban');
      const selLista = document.getElementById('filter-lista');
      if (selLista) {
        if (savedListasCsv) {
          const values = savedListasCsv.split(',').map(s => s.trim()).filter(Boolean);
          const options = Array.from(selLista.options);
          options.forEach(o => { o.selected = values.includes(o.value); });
        } else if (savedListaLegacy) {
          // Migrar seleção única antiga
          const exists = Array.from(selLista.options).some(o => o.value === savedListaLegacy);
          if (exists) {
            Array.from(selLista.options).forEach(o => { o.selected = (o.value === savedListaLegacy); });
          }
        }
      }
    } catch (e) { /* noop */ }

    fetchAndRender();
    if (STATE.timerId) clearInterval(STATE.timerId);
    STATE.timerId = setInterval(tickTimers, 1000);
    if (STATE.refreshId) clearInterval(STATE.refreshId);
    STATE.refreshId = setInterval(() => { if (!document.hidden) fetchAndRender(); }, 10000);

    // Listen to cross-tab stop broadcasts to immediately clear any running timers on the dashboard
    try { window.addEventListener('storage', onStorage); } catch (_) { /* noop */ }

    // Wire up filter change events
    document.getElementById('filter-lista')?.addEventListener('change', function(e) {
      try {
        const sel = e.target;
        const selected = Array.from(sel.selectedOptions || []).map(o => o.value).filter(v => v && v !== 'Todas');
        // Persistir como CSV múltiplo (nova chave)
        if (selected.length > 0) {
          localStorage.setItem('dashboard_listas_kanban', selected.join(','));
        } else {
          localStorage.removeItem('dashboard_listas_kanban');
        }
      } catch (err) { /* noop */ }
      fetchAndRender();
    });
    document.getElementById('filter-status')?.addEventListener('change', fetchAndRender);
    document.getElementById('btn-clear-filters')?.addEventListener('click', function() {
      const listaFilter = document.getElementById('filter-lista');
      const statusFilter = document.getElementById('filter-status');
      if (listaFilter) {
        // Limpar múltiplas seleções e selecionar 'Todas' se existir
        Array.from(listaFilter.options).forEach(o => o.selected = false);
        const optTodas = Array.from(listaFilter.options).find(o => o.value === 'Todas');
        if (optTodas) optTodas.selected = true;
        try {
          localStorage.removeItem('dashboard_listas_kanban');
          localStorage.setItem('dashboard_lista_kanban', 'Todas');
        } catch (e) { /* noop */ }
      }
      if (statusFilter) {
        Array.from(statusFilter.options).forEach(o => o.selected = false);
        const optTodos = Array.from(statusFilter.options).find(o => o.value === 'Todos');
        if (optTodos) optTodos.selected = true;
      }
      fetchAndRender();
    });
  }

  // Expose init and other useful functions
  window.ApontamentoDashboard = { init };
  window.renderizarChipsStatus = renderizarChipsStatus;
})();
