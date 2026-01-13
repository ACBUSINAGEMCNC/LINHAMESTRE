// Script para habilitar arrastar e soltar no Kanban usando Sortable.js
document.addEventListener('DOMContentLoaded', function() {
    console.log('Inicializando Sortable.js para o Kanban');
    
    // Inicializa o Sortable.js para cada coluna do kanban
    document.querySelectorAll('.kanban-column-body').forEach(function(columnBody) {
        new Sortable(columnBody, {
            group: 'kanban-columns',
            animation: 200, // Animação mais suave
            easing: 'cubic-bezier(0.25, 0.8, 0.25, 1)', // Easing mais natural
            delay: 0,
            delayOnTouchOnly: false,
            touchStartThreshold: 5, // Menos sensível para evitar arrastar acidental
            dragClass: 'sortable-drag',
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            forceFallback: false, // Usar comportamento nativo quando possível
            fallbackClass: 'sortable-fallback',
            fallbackOnBody: true,
            swapThreshold: 0.5, // Threshold mais responsivo
            invertSwap: true, // Melhor experiência ao trocar posições
            preventOnFilter: true,
            // Simplificar filtros - apenas elementos realmente necessários
            filter: '.btn, button, .dropdown, input, select, textarea, a[href]',
            draggable: '.kanban-card, .kanban-card.fantasma',
            onStart: function(evt) {
                console.log('Início do arrasto', evt.item.dataset.ordemId);
                document.body.style.cursor = 'grabbing';
                document.body.classList.add('sorting');
                // Adicionar classe visual ao cartão
                evt.item.classList.add('is-dragging');
                // Esconder dropdowns abertos
                document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
            },
            onEnd: function(evt) {
                console.log('Fim do arrasto', evt.item.dataset.ordemId || evt.item.dataset.cartaoId);
                document.body.style.cursor = 'default';
                document.body.classList.remove('sorting');
                evt.item.classList.remove('is-dragging');
                
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
                            // Mostrar feedback visual
                            evt.item.style.opacity = '0.5';
                            setTimeout(() => window.location.reload(), 200);
                        } else {
                            console.error('❌ DRAG Erro ao mover cartão fantasma:', data.message);
                            // Reverter posição com animação
                            evt.item.style.transition = 'all 0.3s ease';
                            evt.from.appendChild(evt.item);
                            setTimeout(() => evt.item.style.transition = '', 300);
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
                                // Feedback visual antes de recarregar
                                evt.item.style.opacity = '0.5';
                                setTimeout(() => window.location.reload(), 200);
                            } else {
                                // Reverter em caso de erro
                                evt.from.appendChild(evt.item);
                            }
                        })
                        .catch(error => {
                            console.error('Erro ao mover:', error);
                            evt.from.appendChild(evt.item);
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
