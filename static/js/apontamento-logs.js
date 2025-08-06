/**
 * Sistema de logs de apontamento para cartões Kanban
 * Exibe histórico de apontamentos por cartão
 */

// Função para carregar logs de apontamento para uma OS específica
function carregarLogsApontamento(ordemId, container) {
    // Limpar container
    if (container) {
        container.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div> Carregando logs...';
    }
    
    fetch(`/apontamento/os/${ordemId}/logs`)
        .then(response => response.json())
        .then(data => {
            if (container) {
                if (data.logs && data.logs.length > 0) {
                    // Construir HTML para exibição dos logs em uma tabela completa e detalhada
                    let html = '<div class="logs-apontamento">';
                    html += '<div class="table-responsive">';
                    html += '<table class="table table-striped table-hover table-bordered">';
                    html += '<thead class="table-primary">';
                    html += '<tr>';
                    html += '<th>Data/Hora</th>';
                    html += '<th>Ação</th>';
                    html += '<th>Operador</th>';
                    html += '<th>Item</th>';
                    html += '<th>Trabalho</th>';
                    html += '<th>Quantidade</th>';
                    html += '<th>Motivo Pausa</th>';
                    html += '<th>Duração</th>';
                    html += '</tr>';
                    html += '</thead>';
                    html += '<tbody>';
                    
                    data.logs.forEach(log => {
                        // Calcular duração de três formas possíveis:
                        // 1. Usando o campo tempo_decorrido se estiver disponível
                        // 2. Calculando a partir de data_hora e data_fim se ambos estiverem disponíveis
                        // 3. Exibindo '-' se não for possível calcular
                        let duracao = '-';
                        
                        if (log.tempo_decorrido) {
                            // Converter segundos para formato horas e minutos
                            const horas = Math.floor(log.tempo_decorrido / 3600);
                            const minutos = Math.floor((log.tempo_decorrido % 3600) / 60);
                            duracao = `${horas}h ${minutos}min`;
                        } else if (log.data_fim && log.data_hora) {
                            const inicio = new Date(log.data_hora);
                            const fim = new Date(log.data_fim);
                            const diff = Math.abs(fim - inicio);
                            const horas = Math.floor(diff / 3600000);
                            const minutos = Math.floor((diff % 3600000) / 60000);
                            duracao = `${horas}h ${minutos}min`;
                        }
                        
                        html += '<tr>';
                        html += `<td>${formatarDataHora(log.data_hora)}</td>`;
                        html += `<td><span class="badge ${getBadgeClass(log.tipo_acao)}">${log.tipo_acao}</span></td>`;
                        html += `<td>${log.operador_nome || ''} ${log.operador_codigo ? '(' + log.operador_codigo + ')' : ''}</td>`;
                        html += `<td>${log.item_nome || '-'}</td>`;
                        html += `<td>${log.trabalho_nome || '-'}</td>`;
                        html += `<td>${log.quantidade !== null && log.quantidade !== undefined ? log.quantidade : '-'}</td>`;
                        html += `<td>${log.motivo_pausa || '-'}</td>`;
                        html += `<td>${duracao || '-'}</td>`;
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table></div></div>';
                    container.innerHTML = html;
                    
                    // Adicionar resumo estatístico
                    const resumoHtml = criarResumoEstatistico(data.logs);
                    if (resumoHtml) {
                        container.insertAdjacentHTML('afterbegin', resumoHtml);
                    }
                } else {
                    container.innerHTML = '<div class="alert alert-info">Nenhum registro de apontamento encontrado para esta OS.</div>';
                }
            }
            
            // Adicionar logs ao card na visualização Kanban
            adicionarLogsAoCard(ordemId, data.logs);
        })
        .catch(error => {
            console.error('Erro ao carregar logs de apontamento:', error);
            if (container) {
                container.innerHTML = '<div class="alert alert-danger">Erro ao carregar logs de apontamento. Tente novamente mais tarde.</div>';
            }
        });
}

// Função para criar resumo estatístico dos logs
function criarResumoEstatistico(logs) {
    if (!logs || logs.length === 0) return null;
    
    // Contadores
    let totalSetup = 0;
    let totalProducao = 0;
    let totalPausas = 0;
    let totalQuantidade = 0;
    
    // Calcular estatísticas
    logs.forEach(log => {
        if (log.tipo_acao === 'Fim Setup') {
            totalSetup++;
        } else if (log.tipo_acao === 'Fim Produção') {
            totalProducao++;
        } else if (log.tipo_acao === 'Pausa') {
            totalPausas++;
        }
        
        if (log.quantidade) {
            totalQuantidade += parseInt(log.quantidade);
        }
    });
    
    // Criar HTML do resumo
    let html = '<div class="card mb-3">';
    html += '<div class="card-header bg-light">Resumo de Apontamentos</div>';
    html += '<div class="card-body">';
    html += '<div class="row">';
    
    html += '<div class="col-md-3 mb-2">';
    html += '<div class="card bg-light h-100">';
    html += '<div class="card-body text-center">';
    html += '<h3>' + logs.length + '</h3>';
    html += '<p class="mb-0">Total de Registros</p>';
    html += '</div></div></div>';
    
    html += '<div class="col-md-3 mb-2">';
    html += '<div class="card bg-light h-100">';
    html += '<div class="card-body text-center">';
    html += '<h3>' + totalSetup + '</h3>';
    html += '<p class="mb-0">Setups Concluídos</p>';
    html += '</div></div></div>';
    
    html += '<div class="col-md-3 mb-2">';
    html += '<div class="card bg-light h-100">';
    html += '<div class="card-body text-center">';
    html += '<h3>' + totalProducao + '</h3>';
    html += '<p class="mb-0">Produções Concluídas</p>';
    html += '</div></div></div>';
    
    html += '<div class="col-md-3 mb-2">';
    html += '<div class="card bg-light h-100">';
    html += '<div class="card-body text-center">';
    html += '<h3>' + totalQuantidade + '</h3>';
    html += '<p class="mb-0">Peças Produzidas</p>';
    html += '</div></div></div>';
    
    html += '</div></div></div>';
    
    return html;
}

// Função para adicionar logs resumidos ao card do Kanban (desativada - logs exibidos apenas no modal de detalhes)
function adicionarLogsAoCard(ordemId, logs) {
    // Função desativada - logs agora são exibidos apenas no modal de detalhes da OS
    return;
}

// Função para formatar data/hora
function formatarDataHora(dataString) {
    const data = new Date(dataString);
    return data.toLocaleDateString('pt-BR') + ' ' + 
           data.toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'});
}

// Função para formatar data/hora compacta
function formatarDataHoraCompacta(dataString) {
    const data = new Date(dataString);
    const hoje = new Date();
    
    // Se for hoje, mostrar apenas a hora
    if (data.toDateString() === hoje.toDateString()) {
        return data.toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'});
    } else {
        return data.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'});
    }
}

// Função para obter classe de estilo para badge conforme o tipo de ação
function getBadgeClass(tipoAcao) {
    switch (tipoAcao) {
        case 'Início Setup':
            return 'bg-primary';
        case 'Fim Setup':
            return 'bg-success';
        case 'Início Produção':
            return 'bg-warning';
        case 'Pausa Produção':
            return 'bg-secondary';
        case 'Fim Produção':
            return 'bg-danger';
        default:
            return 'bg-info';
    }
}

// Carregar logs para todos os cards visíveis ao inicializar
document.addEventListener('DOMContentLoaded', function() {
    // Pequeno atraso para garantir que os cards já foram carregados
    setTimeout(() => {
        const cards = document.querySelectorAll('.kanban-card');
        cards.forEach(card => {
            const ordemId = card.getAttribute('data-ordem-id');
            if (ordemId) {
                fetch(`/apontamento/os/${ordemId}/logs`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.logs && data.logs.length > 0) {
                            adicionarLogsAoCard(ordemId, data.logs);
                        }
                    })
                    .catch(error => console.error('Erro ao carregar logs para card:', error));
            }
        });
    }, 1000);
});
