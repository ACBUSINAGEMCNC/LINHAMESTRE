// Script para adicionar evento de clique nos botões de número da OS
document.addEventListener('DOMContentLoaded', function() {
    initializeOSButtonClicks();
});

// Reinicializar após drag & drop
document.addEventListener('sortable-drop-complete', function() {
    initializeOSButtonClicks();
});

function initializeOSButtonClicks() {
    document.querySelectorAll('.os-number-btn').forEach(function(btn) {
        if (!btn.classList.contains('click-initialized')) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                const ordemId = this.dataset.ordemId;
                if (ordemId) {
                    abrirDetalhesOS(ordemId);
                }
            });
            btn.classList.add('click-initialized');
        }
    });
}
