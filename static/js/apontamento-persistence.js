/**
 * Sistema de persistência para apontamentos
 * Garante que os apontamentos ativos não sejam perdidos ao recarregar a página
 */

// Função para carregar o estado dos apontamentos ao iniciar a página
function carregarEstadoApontamentos() {
    console.log('Carregando estado dos apontamentos...');
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
            if (data.status_ativos && data.status_ativos.length > 0) {
                console.log(`Encontrados ${data.status_ativos.length} apontamentos ativos`); 
                data.status_ativos.forEach(status => {
                    // Usar ordem_servico_id em vez de ordem_id (que não existe no modelo)
                    const ordemId = status.ordem_servico_id;
                    const statusAtual = status.status_atual;
                    
                    console.log(`Restaurando status para OS ${ordemId}: ${statusAtual}`);
                    
                    // Atualizar visualmente o card com o status atual
                    // Usar a função atualizarStatusCartao do HTML que foi melhorada
                    atualizarStatusCartao(ordemId, statusAtual);
                    
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
                    
                    // Iniciar timer com o tempo real do backend
                    if (status.inicio_acao && (status.status_atual === 'Setup em andamento' || 
                                              status.status_atual === 'Produção em andamento' || 
                                              status.status_atual === 'Pausado')) {
                        iniciarTimerApontamento(ordemId, status.status_atual, status.inicio_acao);
                    }
                });
                
                console.log('Estado dos apontamentos restaurado com sucesso!');
            } else {
                console.log('Nenhum apontamento ativo encontrado.');
            }
        })
        .catch(error => {
            console.error('Erro ao carregar estado dos apontamentos:', error);
            // Tentar novamente após 3 segundos em caso de falha
            setTimeout(carregarEstadoApontamentos, 3000);
        });
}

// Função para atualizar completamente o status visual de um card
function atualizarStatusCartaoCompleto(ordemId, statusAtual) {
    const card = document.querySelector(`.kanban-card[data-ordem-id="${ordemId}"]`);
    if (!card) {
        console.warn(`Card não encontrado para OS ${ordemId}`);
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
            botoesMostrar = ['pausa', 'fim_producao'];
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
    
    // Se o status for ativo, iniciar o timer
    if (statusClass === 'status-setup' || statusClass === 'status-producao' || statusClass === 'status-pausado') {
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
    const card = document.querySelector(`.kanban-card[data-ordem-id="${ordemId}"]`);
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
    const card = document.querySelector(`.kanban-card[data-ordem-id="${ordemId}"]`);
    if (!card) return;
    
    const botoesApontamento = card.querySelectorAll('.apontamento-btn');
    botoesApontamento.forEach(botao => {
        // Desabilitar botões que afetam o status (exceto início de setup/produção)
        if (['fim_setup', 'pausa', 'fim_producao'].includes(botao.getAttribute('data-acao'))) {
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

// Inicializar ao carregar a página
document.addEventListener('DOMContentLoaded', function() {
    console.log('Inicializando sistema de persistência de apontamentos...');
    carregarEstadoApontamentos();
});
