/**
 * Funções JavaScript para a página de Pedidos - Geração de Material
 */

// Função para exibir modal de confirmação
function mostrarModalConfirmacao(mensagem, acaoConfirmada) {
    // Criar o modal se ele não existir
    if ($('#modalConfirmacao').length === 0) {
        $('body').append(`
            <div class="modal fade" id="modalConfirmacao" tabindex="-1" aria-labelledby="modalConfirmacaoTitulo" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="modalConfirmacaoTitulo">Confirmação</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
                        </div>
                        <div class="modal-body" id="modalConfirmacaoCorpo">
                            <!-- Conteúdo dinâmico será inserido aqui -->
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-primary" id="btnConfirmarAcao">Confirmar</button>
                        </div>
                    </div>
                </div>
            </div>
        `);
    }
    
    // Definir a mensagem
    $('#modalConfirmacaoCorpo').text(mensagem);
    
    // Remover eventos antigos e adicionar novo
    $('#btnConfirmarAcao').off('click').on('click', function() {
        $('#modalConfirmacao').modal('hide');
        acaoConfirmada();
    });
    
    // Mostrar o modal
    var modalEl = document.getElementById('modalConfirmacao');
    var modalInstance = new bootstrap.Modal(modalEl);
    modalInstance.show();
}

// Função auxiliar para obter IDs dos pedidos selecionados (filtrando cancelados)
function getPedidosSelecionados() {
    var selecionados = [];
    var pedidosCanceladosNomes = [];
    
    $(".pedido-checkbox:checked").each(function() {
        var tr = $(this).closest("tr");
        var status = (tr.data("status") || tr.find(".status-badge").text().trim()).toLowerCase();
        var pedidoId = $(this).val();
        
        if (status === "cancelado") {
            var nomeCliente = tr.find("td:nth-child(2)").text().trim();
            pedidosCanceladosNomes.push(nomeCliente || `ID ${pedidoId}`);
        } else {
            selecionados.push(pedidoId);
        }
    });
    
    if (pedidosCanceladosNomes.length > 0) {
        var alertMsg = "Atenção! Os seguintes pedidos cancelados foram ignorados: " + pedidosCanceladosNomes.join(", ");
        if (typeof showToast === "function") {
            showToast(alertMsg, "warning");
        } else {
            alert(alertMsg);
        }
    }
    
    return selecionados;
}

// Atualiza a visibilidade do botão com base nas seleções e destaca pedidos já com número de material
function atualizarVisibilidadeBotao() {
    const checkboxesSelecionados = document.querySelectorAll('input[name="checkPedido"]:checked');
    const botaoGerar = document.getElementById('btnGerarPedidoMaterial');
    
    if (checkboxesSelecionados.length > 0) {
        botaoGerar.classList.remove('d-none');
    } else {
        botaoGerar.classList.add('d-none');
    }
    
    // Atualiza contador
    const contador = document.getElementById('contadorPedidosSelecionados');
    if (contador) {
        contador.textContent = checkboxesSelecionados.length;
    }
    
    // Destaca pedidos que já têm número de pedido de material
    document.querySelectorAll('input[name="checkPedido"]').forEach(checkbox => {
        const row = checkbox.closest('tr');
        const numeroPedidoMaterial = row.querySelector('td[data-numero-pedido-material]');
        
        if (numeroPedidoMaterial && numeroPedidoMaterial.getAttribute('data-numero-pedido-material')) {
            // Adiciona classe para destacar visualmente
            row.classList.add('table-warning');
            
            // Adiciona tooltip no checkbox
            checkbox.setAttribute('title', 'Este pedido já tem um Pedido de Material associado. Selecionar novamente criará um sufixo incremental.');
            
            // Opcional: Adiciona um ícone de aviso
            const label = checkbox.closest('label');
            if (label && !label.querySelector('.material-warning-icon')) {
                const icon = document.createElement('i');
                icon.className = 'fas fa-exclamation-triangle text-warning ms-1 material-warning-icon';
                icon.style.fontSize = '0.8rem';
                label.appendChild(icon);
            }
        }
    });
}

// Função para gerar pedido de material
function gerarPedidoMaterial() {
    var pedidosSelecionados = getPedidosSelecionados();
    
    if (pedidosSelecionados.length === 0) {
        alert("Selecione pelo menos um pedido válido (não cancelado) marcando os checkboxes.");
        return;
    }
    
    var mensagem = "Tem certeza que deseja gerar Pedido de Material para " + pedidosSelecionados.length + " pedido(s) selecionado(s)?";
    
    mostrarModalConfirmacao(mensagem, function() {
        // Mostra indicador de loading
        $("body").append("<div id='overlay' style='position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;'><div class='spinner-border text-light' role='status'><span class='sr-only'>Processando...</span></div></div>");
        
        console.log("Gerando pedido de material para os seguintes IDs:", pedidosSelecionados);
        
        // Criar formulário manualmente para garantir que funcione
        var form = document.createElement("form");
        form.method = "POST";
        form.action = "/pedidos/gerar-pedido-material-multiplo";
        
        // Adicionar token CSRF se disponível
        var csrfToken = $("meta[name='csrf-token']").attr("content") || $("#csrf_token").val();
        if (csrfToken) {
            var csrfInput = document.createElement("input");
            csrfInput.type = "hidden";
            csrfInput.name = "csrf_token";
            csrfInput.value = csrfToken;
            form.appendChild(csrfInput);
        }
        
        // Adicionar cada pedido selecionado como input hidden
        pedidosSelecionados.forEach(function(pedidoId) {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = "pedidos[]";
            input.value = pedidoId;
            form.appendChild(input);
        });
        
        // Adicionar o formulário ao documento e enviar
        document.body.appendChild(form);
        form.submit();
    });
}

// Configurar event handlers quando o documento estiver pronto
$(document).ready(function() {
    // Ativar a seleção ao clicar na linha (exceto em elementos interativos)
    $("#pedidosTable tbody").on("click", "tr", function(e) {
        if (!$(e.target).is("input.pedido-checkbox, button, a, .btn, i") && 
            !$(e.target).closest("button, a, .btn, .dropdown-toggle, .form-check").length) {
            var checkbox = $(this).find(".pedido-checkbox");
            checkbox.prop("checked", !checkbox.prop("checked"));
        }
    });

    // Selecionar/deselecionar todos (checkbox no thead)
    $("#selectAll").on("change", function() {
        var isChecked = $(this).prop("checked");
        $(".pedido-checkbox").prop("checked", isChecked);
    });

    // Garantir que clicar no checkbox da linha não propague para a linha (evita desmarcar)
    $("#pedidosTable tbody").on("click", ".pedido-checkbox", function(e) {
        e.stopPropagation();
    });

    // Prevenir seleção de linha ao clicar em botões/dropdowns dentro da linha
    $("#pedidosTable tbody").on("click", ".table-actions .btn, .dropdown-toggle", function(e) {
        e.stopPropagation();
    });
    
    // Configurar botão para gerar pedido de material
    $("#btn-gerar-pedido-material").on("click", gerarPedidoMaterial);
    
    // Configurar botão para gerar OS
    $("#btn-gerar-os").on("click", function() {
        var pedidosSelecionados = getPedidosSelecionados();
        
        if (pedidosSelecionados.length === 0) {
            alert("Selecione pelo menos um pedido válido (não cancelado) marcando os checkboxes.");
            return;
        }
        
        var mensagem = "Tem certeza que deseja gerar Ordem de Serviço para " + pedidosSelecionados.length + " pedido(s) selecionado(s)?";
        
        mostrarModalConfirmacao(mensagem, function() {
            // Mostra indicador de loading
            $("body").append("<div id='overlay' style='position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; justify-content: center; align-items: center;'><div class='spinner-border text-light' role='status'><span class='sr-only'>Processando...</span></div></div>");
            
            // Criar formulário
            var form = document.createElement("form");
            form.method = "POST";
            form.action = "/pedidos/gerar-os-multipla";
            
            // Adicionar token CSRF se disponível
            var csrfToken = $("meta[name='csrf-token']").attr("content") || $("#csrf_token").val();
            if (csrfToken) {
                var csrfInput = document.createElement("input");
                csrfInput.type = "hidden";
                csrfInput.name = "csrf_token";
                csrfInput.value = csrfToken;
                form.appendChild(csrfInput);
            }
            
            // Adicionar cada pedido selecionado como input hidden
            pedidosSelecionados.forEach(function(pedidoId) {
                var input = document.createElement("input");
                input.type = "hidden";
                input.name = "pedidos[]";
                input.value = pedidoId;
                form.appendChild(input);
            });
            
            // Adicionar o formulário ao documento e enviar
            document.body.appendChild(form);
            form.submit();
        });
    });
});
