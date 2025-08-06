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
            handle: '.drag-handle', // Usar apenas a alça para arrastar
            forceFallback: true, // Modo fallback para melhor controle
            fallbackClass: 'sortable-fallback',
            fallbackOnBody: true, 
            swapThreshold: 0.65,
            preventOnFilter: true,
            filter: '.no-drag, .document-icons, .document-container, .pdf-container, .cnc-container',
            draggable: '.kanban-card',
            onStart: function(evt) {
                console.log('Início do arrasto', evt.item.dataset.ordemId);
                document.body.style.cursor = 'grabbing';
                // Adiciona classe para prevenir seleção de texto
                document.body.classList.add('sorting');
            },
            onEnd: function(evt) {
                console.log('Fim do arrasto', evt.item.dataset.ordemId);
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
                
                // Se o item foi movido para outra coluna
                if (evt.from !== evt.to) {
                    // Obter ID da ordem e nova lista
                    const ordemId = evt.item.dataset.ordemId;
                    const novaLista = evt.to.dataset.lista;
                    
                    console.log(`Movendo item ${ordemId} para ${novaLista}`);
                    
                    // Atualizar no servidor
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
                            // Recarregar para atualizar contadores
                            setTimeout(() => window.location.reload(), 300);
                        }
                    });
                }
            }
        });
    });
});
