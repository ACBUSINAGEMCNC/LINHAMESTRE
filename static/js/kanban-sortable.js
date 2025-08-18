// Script para habilitar arrastar e soltar no Kanban usando Sortable.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('Inicializando Sortable.js para o Kanban');
    
    // Inicializa o Sortable.js para cada coluna do kanban
    document.querySelectorAll('.kanban-column-body').forEach(function(columnBody) {
        new Sortable(columnBody, {
            group: 'kanban-columns', // Permite arrastar entre colunas
            animation: 150, // Duração da animação
            easing: 'cubic-bezier(0.2, 1, 0.1, 1)', // Easing suave
            delay: 0, // Sem delay para resposta imediata
            delayOnTouchOnly: false, // Sem delay em toque
            touchStartThreshold: 1, // Alta sensibilidade
            dragClass: 'sortable-drag',
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            // Removido o handle: agora o cartão inteiro é arrastável (estilo Trello)
            forceFallback: true, // Modo fallback para melhor controle
            fallbackClass: 'sortable-fallback',
            fallbackOnBody: true, 
            swapThreshold: 0.65,
            preventOnFilter: true,
            // Impede arrastar quando clicando em elementos interativos dentro do cartão
            filter: '.no-drag, .document-icons, .document-container, .pdf-container, .cnc-container, .apontamento-buttons, .btn, button, .dropdown, .dropdown-menu, input, select, textarea, a, [data-bs-toggle]',
            draggable: '.kanban-card, .kanban-card.fantasma',
            onStart: function(evt) {
                console.log('Início do arrasto', evt.item.dataset.ordemId);
                document.body.style.cursor = 'grabbing';
                // Adiciona classe para prevenir seleção de texto
                document.body.classList.add('sorting');
            },
            onEnd: function(evt) {
                console.log('Fim do arrasto', evt.item.dataset.ordemId || evt.item.dataset.cartaoId);
                document.body.style.cursor = 'default';
                document.body.classList.remove('sorting');
                
                // Disparar evento personalizado para reinicializar os eventos do cartão
                document.dispatchEvent(new CustomEvent('sortable-drop-complete', {
                    detail: {
                        item: evt.item,
                        from: evt.from,
                        to: evt.to
                    }
                }));
                
                // Verificar se é cartão fantasma ou cartão normal
                const isGhostCard = evt.item.classList.contains('fantasma');
                
                if (isGhostCard) {
                    // Lógica para cartões fantasma
                    const cartaoId = evt.item.dataset.cartaoId;
                    const novaLista = evt.to.dataset.lista;
                    const novaPosicao = Array.from(evt.to.children).indexOf(evt.item) + 1;
                    
                    console.log(`🎯 DRAG & DROP: Movendo cartão fantasma ${cartaoId} para lista ${novaLista}, posição ${novaPosicao}`);
                    console.log('🎯 Elemento arrastado:', evt.item);
                    console.log('🎯 Lista origem:', evt.from.dataset.lista);
                    console.log('🎯 Lista destino:', evt.to.dataset.lista);
                    
                    // Criar FormData para enviar os dados
                    const formData = new FormData();
                    formData.append('cartao_id', cartaoId);
                    formData.append('nova_lista', novaLista);
                    formData.append('nova_posicao', novaPosicao);
                    
                    console.log('🎯 Dados a enviar:', Object.fromEntries(formData));
                    
                    fetch('/cartao-fantasma/mover', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => {
                        console.log('📡 DRAG Status da resposta:', response.status, response.statusText);
                        return response.text().then(text => {
                            console.log('📡 DRAG Texto bruto da resposta:', text);
                            try {
                                return JSON.parse(text);
                            } catch (e) {
                                console.error('❌ DRAG Erro ao fazer parse JSON:', e);
                                throw new Error('Resposta não é JSON válido: ' + text);
                            }
                        });
                    })
                    .then(data => {
                        console.log('📡 DRAG Dados parseados:', data);
                        if (data.success) {
                            console.log('✅ DRAG Cartão fantasma movido com sucesso');
                            setTimeout(() => window.location.reload(), 300);
                        } else {
                            console.error('❌ DRAG Erro ao mover cartão fantasma:', data.message);
                            // Reverter posição em caso de erro
                            evt.from.appendChild(evt.item);
                        }
                    })
                    .catch(error => {
                        console.error('❌ DRAG Erro na requisição:', error);
                        // Reverter posição em caso de erro
                        evt.from.appendChild(evt.item);
                    });
                } else {
                    // Lógica para cartões normais
                    const ordemId = evt.item.dataset.ordemId;
                    const novaLista = evt.to.dataset.lista;
                    const novaPosicao = Array.from(evt.to.children).indexOf(evt.item) + 1;
                    
                    if (evt.from !== evt.to) {
                        // Mudou de coluna - mover para nova lista
                        console.log(`Movendo item ${ordemId} para ${novaLista}`);
                        
                        fetch('/kanban/mover', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded'
                            },
                            body: `ordem_id=${ordemId}&nova_lista=${novaLista}`
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                console.log('Movimento salvo com sucesso');
                                setTimeout(() => window.location.reload(), 300);
                            }
                        });
                    } else {
                        // Reordenou dentro da mesma lista - salvar nova posição
                        console.log(`Reordenando item ${ordemId} para posição ${novaPosicao} na lista ${novaLista}`);
                        
                        fetch('/kanban/reordenar', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded'
                            },
                            body: `ordem_id=${ordemId}&nova_posicao=${novaPosicao}&lista=${novaLista}`
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                console.log('Reordenação salva com sucesso');
                            } else {
                                console.error('Erro ao salvar reordenação:', data.message);
                                // Reverter em caso de erro
                                evt.from.appendChild(evt.item);
                            }
                        })
                        .catch(error => {
                            console.error('Erro na requisição de reordenação:', error);
                            // Reverter em caso de erro
                            evt.from.appendChild(evt.item);
                        });
                    }
                }
            }
        });
    });
});
