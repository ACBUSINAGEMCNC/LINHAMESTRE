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

  // Build the existing detailed card HTML for a single status item
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
    const an = st.analytics || {};
    const tempoSetupEst = an.tempo_setup_estimado != null ? fmtSecs(an.tempo_setup_estimado) : '-';
    const tempoSetupUtil = an.tempo_setup_utilizado != null ? fmtSecs(an.tempo_setup_utilizado) : '-';
    const tempoPecaEst = an.tempo_peca_estimado != null ? `${an.tempo_peca_estimado}s` : '-';
    const mediaSegPeca = an.media_seg_por_peca != null ? `${an.media_seg_por_peca}s` : '-';
    const tempoProdUtil = an.tempo_producao_utilizado != null ? fmtSecs(an.tempo_producao_utilizado) : '-';
    const tempoPausas = an.tempo_pausas_utilizado != null ? fmtSecs(an.tempo_pausas_utilizado) : '-';

    const ativos = Array.isArray(st.ativos_por_trabalho) ? st.ativos_por_trabalho : [];
    const ativosHTML = ativos.map(a => {
      const tipo = (a.status === 'Setup em andamento') ? 'setup' : (a.status === 'Pausado' ? 'pausa' : 'producao');
      const startISO = a.inicio_acao || '';
      const start = startISO ? parseStart(startISO) : null;
      const tNow = start ? fmtSecs(secondsSince(start)) : '--:--:--';

      const anT = a.analytics || {};
      const tempoSetupEstT = anT.tempo_setup_estimado != null ? fmtSecs(anT.tempo_setup_estimado) : '-';
      const tempoSetupUsoT = anT.tempo_setup_utilizado != null ? fmtSecs(anT.tempo_setup_utilizado) : '-';
      const tempoPecaEstT = anT.tempo_peca_estimado != null ? `${anT.tempo_peca_estimado}s` : '-';
      const mediaSegPecaT = anT.media_seg_por_peca != null ? `${anT.media_seg_por_peca}s` : '-';
      const tempoProdUsoT = anT.tempo_producao_utilizado != null ? fmtSecs(anT.tempo_producao_utilizado) : '-';
      const tempoPausasT = anT.tempo_pausas_utilizado != null ? fmtSecs(anT.tempo_pausas_utilizado) : '-';

      const metricsTHTML = `
        <div class="mt-2 d-flex flex-wrap gap-2 align-items-center">
          <span class="badge rounded-pill bg-secondary"><i class="fas fa-cogs me-1"></i> Setup Est.: ${tempoSetupEstT}</span>
          <span class="badge rounded-pill bg-info text-dark"><i class="fas fa-wrench me-1"></i> Setup Usado: ${tempoSetupUsoT} ${perfBadge(anT.setup_status)}</span>
          <span class="badge rounded-pill bg-primary"><i class="fas fa-gauge-high me-1"></i> Pç Est.: ${tempoPecaEstT}</span>
          <span class="badge rounded-pill bg-success"><i class="fas fa-stopwatch me-1"></i> Média/pç: ${mediaSegPecaT} ${perfBadge(anT.producao_status)}</span>
          <span class="badge rounded-pill bg-dark"><i class="fas fa-clock me-1"></i> Prod. Usado: ${tempoProdUsoT}</span>
          <span class="badge rounded-pill bg-warning text-dark"><i class="fas fa-pause me-1"></i> Pausas: ${tempoPausasT}</span>
        </div>`;

      return `
        <div class="border rounded p-2 mb-2 trabalho-item ti-${tipo}">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <div class="fw-semibold">${a.item_codigo || ''} ${a.item_nome || ''}</div>
              <div class="text-muted small">${a.trabalho_nome || ''}</div>
            </div>
            <div class="text-end">
              ${statusBadge(a.status)}
            </div>
          </div>
          <div class="d-flex flex-wrap align-items-center gap-3 mt-2">
            <div class="display-6 fw-bold m-0" data-crono-start="${start ? start.toISOString() : ''}" data-crono-tipo="${tipo}">${tNow}</div>
            <div class="small text-muted">Início: ${startISO ? new Date(startISO).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : '-'}</div>
            <div class="small"><span class="text-muted">Últ. Qtde:</span> ${a.ultima_quantidade ?? 0}</div>
            ${a.motivo_pausa ? `<div class="small text-warning"><i class="fas fa-exclamation-triangle"></i> ${a.motivo_pausa}</div>` : ''}
          </div>
          ${metricsTHTML}
        </div>`;
    }).join('');

    const listName = (st.lista_kanban || '').toString().toUpperCase();
    return `
      <div class="card mb-3 ${statusToClass(st)}">
        <div class="card-header">
          <div class="row align-items-center">
            <div class="col-4">
              <div class="fw-bold">${os}</div>
              <div class="small text-muted">${st.item_codigo || ''} ${st.item_nome || ''}</div>
            </div>
            <div class="col-4 text-center">
              ${listName ? `<div class=\"kanban-list-name\">${listName}</div>` : ''}
            </div>
            <div class="col-4 text-end">
              ${statusBadge(st.status_atual)}
            </div>
          </div>
        </div>
        <div class="card-body">
          ${ativos.length ? (`<div class=\"mt-2\"><div class=\"fw-semibold mb-2\">Ativos por Trabalho</div>${ativosHTML}</div>`) : ''}
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
    if (list.length === 0) {
      container.innerHTML = `<div class=\"text-center text-muted py-3\">Nenhum cartão ativo</div>`;
      return;
    }

    // Group by lista_tipo, excluding 'Outros'
    const groups = new Map();
    const leftovers = [];
    list.forEach(st => {
      const tipo = st.lista_tipo;
      if (tipo && tipo !== 'Outros') {
        if (!groups.has(tipo)) groups.set(tipo, []);
        groups.get(tipo).push(st);
      } else {
        leftovers.push(st);
      }
    });

    // Build HTML for groups
    const groupSections = [];
    groups.forEach((items, tipo) => {
      if (!items.length) return;
      const principal = items[0];
      const fila = items.slice(1);
      const cor = principal.lista_cor || '';

      const filaHTML = fila.length ? (
        `<div class=\"mt-2\">
           <div class=\"fw-semibold mb-2\">Na fila</div>
           <ul class=\"list-group\">
             ${fila.map(it => `<li class=\"list-group-item d-flex justify-content-between align-items-center\">` +
               `<span>${(it.item_codigo || '')} ${(it.item_nome || '')}</span>` +
               `<span class=\"badge bg-secondary rounded-pill\">Qtde: ${it.ultima_quantidade ?? 0}</span>` +
             `</li>`).join('')}
           </ul>
         </div>`
      ) : '';

      groupSections.push(`
        <div class=\"mb-4\">
          <div class=\"d-flex align-items-center mb-2\">
            <div class=\"h5 m-0\">${tipo}</div>
            ${cor ? `<span class=\"ms-2 badge\" style=\"background-color:${cor};\">&nbsp;</span>` : ''}
          </div>
          ${buildDetailedCard(principal)}
          ${filaHTML}
        </div>
      `);
    });

    // Build HTML for leftovers as individual detailed cards
    const leftoversHTML = leftovers.map(st => buildDetailedCard(st)).join('');

    container.innerHTML = `<div class=\"d-flex flex-column\">${groupSections.join('')}${leftoversHTML}</div>`;
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
      const res = await fetch('/apontamento/status-ativos', { cache: 'no-store' });
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
  }

  // Expose init
  window.ApontamentoDashboard = { init };
})();
