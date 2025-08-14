// Apontamento Dashboard: detailed active cards with live timers and analytics
(function() {
  const STATE = {
    lastData: null,
    timerId: null,
    refreshId: null
  };

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

  function statusBadge(status) {
    const map = {
      'Setup em andamento': 'info',
      'Produção em andamento': 'success',
      'Pausado': 'warning',
      'Finalizado': 'dark'
    };
    return badge(map[status] || 'secondary', status || 'Desconhecido');
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
      return 'status-neutro';
    };

    const os = st.os_numero || `OS-${st.ordem_servico_id}`;
    const ativos = Array.isArray(st.ativos_por_trabalho) ? st.ativos_por_trabalho : [];
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
    const ultima = parseInt(st.ultima_quantidade ?? 0, 10) || 0;
    const pct = total > 0 ? Math.max(0, Math.min(100, Math.round((ultima / total) * 100))) : 0;

    const imgMain = st.item_imagem_path ? `<img src="${st.item_imagem_path}" alt="Imagem do item" class="rounded border me-2" style="width:80px;height:80px;object-fit:cover;">` : '';
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
    const trabalhosHtml = trabs.map(t => {
      const u = parseInt(t.ultima_quantidade ?? 0, 10) || 0;
      const pctT = total > 0 ? Math.max(0, Math.min(100, Math.round((u / total) * 100))) : 0;
      const barCls = statusBarClass(t.status);
      return `
        <div class="mb-3">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <div class="fw-semibold">${t.trabalho_nome || 'Serviço'}</div>
            <div class="small text-muted">${t.status || ''}</div>
          </div>
          <div class="progress" style="height: 10px;">
            <div class="progress-bar ${barCls}" role="progressbar" style="width: ${pctT}%;" aria-valuenow="${pctT}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
          <div class="d-flex justify-content-between small text-muted mt-1">
            <div>Última qtd: ${u} / ${total} (${pctT}%)</div>
            <div class="d-flex gap-2">
              <span>Setup: ${fmtSecs(t.tempo_setup_utilizado)}</span>
              <span>Pausas: ${fmtSecs(t.tempo_pausas_utilizado)}</span>
              <span>Rodando: ${fmtSecs(t.tempo_producao_utilizado)}</span>
            </div>
          </div>
        </div>`;
    }).join('');
    return `
      <div class="card mb-3 ${statusToClass(st)}">
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
              ${statusBadge(st.status_atual)}
            </div>
          </div>
        </div>
        <div class="card-body">
          ${trabalhosHtml || '<div class="small text-muted">Sem serviços cadastrados para o item.</div>'}
        </div>
        <div class="card-footer d-flex gap-2">
          <button class="btn btn-outline-primary btn-sm" onclick="verLogs(${st.ordem_servico_id})"><i class="fas fa-history"></i> Logs</button>
          <button class="btn btn-outline-secondary btn-sm" onclick="verDetalhes(${st.ordem_servico_id})"><i class="fas fa-eye"></i> Detalhes</button>
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

    // Buscar máquinas a partir do dropdown (todas as listas conhecidas) e dos dados para garantir exibição completa
    const maquinasConhecidas = Array.from(selLista?.options || [])
      .map(o => o.value)
      .filter(v => v && v !== 'Todas');
    const maquinasDosDados = Array.from(groupsByMachine.keys());
    const todasMaquinas = Array.from(new Set([...maquinasConhecidas, ...maquinasDosDados]));
    // Ordenar conforme a ordem do dropdown; desconhecidas vão para o final em ordem alfabética
    const ordem = new Map(todasMaquinas.map((m, idx) => [m, maquinasConhecidas.indexOf(m) === -1 ? 1e6 + idx : maquinasConhecidas.indexOf(m)]));
    todasMaquinas.sort((a, b) => (ordem.get(a) - ordem.get(b)) || a.localeCompare(b));
    
    // Build HTML for each machine
    const groupSections = [];
    todasMaquinas.forEach(maquina => {
      const items = groupsByMachine.get(maquina) || [];
      
      // Ordenar por status: Em Produção primeiro, depois Setup, Pausado, Aguardando
      items.sort((a, b) => {
        const statusOrder = {
          'Produção em andamento': 1,
          'Setup em andamento': 2,
          'Pausado': 3,
          'Aguardando': 4
        };
        return (statusOrder[a.status_atual] || 5) - (statusOrder[b.status_atual] || 5);
      });

      const principal = items.length > 0 ? items[0] : null;
      const fila = items.length > 1 ? items.slice(1) : [];
      
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
               const imgFila = it.item_imagem_path ? `<img src="${it.item_imagem_path}" alt="Imagem" class="rounded border me-2" style="width:36px;height:36px;object-fit:cover;">` : '';
               return `<li class="list-group-item d-flex justify-content-between align-items-center">` +
                 `<div class="d-flex align-items-center">` +
                   `${imgFila}` +
                   `<div>` +
                     `<div class="fw-medium">${it.os_numero || ''}</div>` +
                     `<div class="small text-muted">${(it.item_codigo || '')} ${(it.item_nome || '')}</div>` +
                   `</div>` +
                 `</div>` +
                 `<div class="text-end">` +
                   `<span class="badge bg-secondary rounded-pill">Qtde: ${it.ultima_quantidade ?? 0}</span>` +
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
            <div class="h4 m-0">${maquina}</div>
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

  async function fetchAndRender() {
    try {
      // Read filters from UI
      const selLista = document.getElementById('filter-lista');
      const selStatus = document.getElementById('filter-status');
      
      // Aplicar filtros apenas se forem diferentes de "Todas" ou "Todos"
      const lista = selLista && selLista.value && selLista.value !== 'Todas' ? selLista.value : null;
      const status = selStatus && selStatus.value && selStatus.value !== 'Todos' ? selStatus.value : null;

      const params = new URLSearchParams();
      if (lista) params.set('lista', lista);
      if (status) params.set('status', status);
      
      console.log('Aplicando filtros:', { lista, status });

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
    fetchAndRender();
    if (STATE.timerId) clearInterval(STATE.timerId);
    STATE.timerId = setInterval(tickTimers, 1000);
    if (STATE.refreshId) clearInterval(STATE.refreshId);
    STATE.refreshId = setInterval(() => { if (!document.hidden) fetchAndRender(); }, 10000);

    // Wire up filter change events
    document.getElementById('filter-lista')?.addEventListener('change', fetchAndRender);
    document.getElementById('filter-status')?.addEventListener('change', fetchAndRender);
    document.getElementById('btn-clear-filters')?.addEventListener('click', function() {
      const listaFilter = document.getElementById('filter-lista');
      const statusFilter = document.getElementById('filter-status');
      if (listaFilter) listaFilter.value = 'Todas';
      if (statusFilter) statusFilter.value = 'Todos';
      fetchAndRender();
    });
  }

  // Expose init
  window.ApontamentoDashboard = { init };
})();
