// Arquivo JavaScript personalizado para o sistema ACB Usinagem CNC

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips do Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Inicializar popovers do Bootstrap
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Função para mostrar feedback visual após ações
    window.showToast = function(message, type = 'success') {
        const toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            const newContainer = document.createElement('div');
            newContainer.className = 'toast-container';
            document.body.appendChild(newContainer);
        }

        const toastId = 'toast-' + Date.now();
        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <strong class="me-auto">${type === 'success' ? 'Sucesso' : 'Aviso'}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Fechar"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;

        const container = document.querySelector('.toast-container');
        container.insertAdjacentHTML('beforeend', toastHTML);

        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 5000 });
        toast.show();

        // Remover o toast do DOM após ser escondido
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
    };

    // Interceptar envios de formulário para mostrar feedback
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            // Mostrar loader
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                const originalText = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processando...';
                
                // Restaurar botão após envio (para casos de validação no cliente)
                setTimeout(() => {
                    if (submitBtn.disabled) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = originalText;
                    }
                }, 5000);
            }
        });
    });

    // Melhorar interação com tabelas
    document.querySelectorAll('.table-hover tr').forEach(row => {
        row.addEventListener('click', function(e) {
            // Ignorar clique se for em um botão ou link
            if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON' || 
                e.target.closest('a') || e.target.closest('button')) {
                return;
            }
            
            // Verificar se há um link de edição na linha
            const editLink = this.querySelector('a.btn-primary');
            if (editLink) {
                window.location.href = editLink.href;
            }
        });
    });

    // Melhorar interação com campos de formulário
    document.querySelectorAll('.form-control, .form-select').forEach(field => {
        // Adicionar classe quando o campo está em foco
        field.addEventListener('focus', function() {
            this.closest('.mb-3')?.classList.add('focused');
        });
        
        // Remover classe quando o campo perde o foco
        field.addEventListener('blur', function() {
            this.closest('.mb-3')?.classList.remove('focused');
        });
    });

    // Melhorar interação com checkboxes e switches
    document.querySelectorAll('.form-check-input').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            // Habilitar/desabilitar campos relacionados
            const target = document.getElementById(this.dataset.target);
            if (target) {
                target.disabled = !this.checked;
                if (this.checked) {
                    target.focus();
                }
            }
        });
    });

    // Adicionar confirmação para ações destrutivas
    document.querySelectorAll('[data-confirm]').forEach(element => {
        element.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
                return false;
            }
        });
    });

    // Melhorar navegação em dispositivos móveis
    if (window.innerWidth < 768) {
        // Adicionar comportamento de swipe para o Kanban
        const kanbanContainer = document.querySelector('.kanban-container');
        if (kanbanContainer) {
            let startX;
            let scrollLeft;

            kanbanContainer.addEventListener('touchstart', function(e) {
                startX = e.touches[0].pageX - kanbanContainer.offsetLeft;
                scrollLeft = kanbanContainer.scrollLeft;
            });

            kanbanContainer.addEventListener('touchmove', function(e) {
                if (!startX) return;
                const x = e.touches[0].pageX - kanbanContainer.offsetLeft;
                const walk = (x - startX) * 2; // Velocidade do scroll
                kanbanContainer.scrollLeft = scrollLeft - walk;
            });

            kanbanContainer.addEventListener('touchend', function() {
                startX = null;
            });
        }

        // Adicionar botão para voltar ao topo
        const backToTopBtn = document.createElement('button');
        backToTopBtn.className = 'btn btn-primary btn-sm position-fixed';
        backToTopBtn.style.bottom = '20px';
        backToTopBtn.style.right = '20px';
        backToTopBtn.style.zIndex = '1000';
        backToTopBtn.innerHTML = '<i class="fas fa-arrow-up"></i>';
        backToTopBtn.addEventListener('click', function() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        document.body.appendChild(backToTopBtn);

        // Mostrar/ocultar botão com base na posição do scroll
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                backToTopBtn.style.display = 'block';
            } else {
                backToTopBtn.style.display = 'none';
            }
        });
    }

    // Inicializar Select2 se estiver disponível
    if (typeof $.fn.select2 !== 'undefined') {
        $('.select2').select2({
            width: '100%',
            placeholder: 'Selecione uma opção',
            allowClear: true
        });
    }

    // Inicializar DataTables se estiver disponível
    if (typeof $.fn.DataTable !== 'undefined') {
        $('.datatable').DataTable({
            language: {
                url: '//cdn.datatables.net/plug-ins/1.11.5/i18n/pt-BR.json'
            },
            responsive: true,
            stateSave: true
        });
    }
});

// Função para atualizar campos dinâmicos com base em seleções
function updateDynamicFields(sourceId, targetId, url) {
    const sourceElement = document.getElementById(sourceId);
    const targetElement = document.getElementById(targetId);
    
    if (!sourceElement || !targetElement) return;
    
    sourceElement.addEventListener('change', function() {
        const selectedValue = this.value;
        if (!selectedValue) {
            // Limpar e desabilitar o campo alvo
            targetElement.innerHTML = '<option value="">Selecione</option>';
            targetElement.disabled = true;
            return;
        }
        
        // Mostrar loader
        targetElement.disabled = true;
        targetElement.innerHTML = '<option value="">Carregando...</option>';
        
        // Fazer requisição AJAX
        fetch(`${url}/${selectedValue}`)
            .then(response => response.json())
            .then(data => {
                targetElement.innerHTML = '<option value="">Selecione</option>';
                data.forEach(item => {
                    const option = document.createElement('option');
                    option.value = item.id;
                    option.textContent = item.nome;
                    targetElement.appendChild(option);
                });
                targetElement.disabled = false;
            })
            .catch(error => {
                console.error('Erro ao carregar dados:', error);
                targetElement.innerHTML = '<option value="">Erro ao carregar</option>';
                targetElement.disabled = true;
            });
    });
}

// Função para adicionar itens dinamicamente em tabelas
function addDynamicTableRow(tableId, data, template) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const tbody = table.querySelector('tbody');
    const newRow = document.createElement('tr');
    
    // Usar template string para gerar o HTML da linha
    newRow.innerHTML = eval('`' + template + '`');
    
    tbody.appendChild(newRow);
    
    // Adicionar evento para remover a linha
    newRow.querySelector('.btn-remove').addEventListener('click', function() {
        tbody.removeChild(newRow);
    });
}
