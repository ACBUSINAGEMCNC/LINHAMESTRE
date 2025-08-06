# Kanban Board Protection – Task Checklist

- [x] Identificar nomes das listas protegidas: **Entrada** (primeira) e **Expedição** (última)
- [x] Verificar fluxo de criação de OS em `routes/pedidos.py` para garantir status inicial "Entrada"
- [x] Verificar fluxo de finalização de OS em `routes/kanban.py` (`finalizar_kanban`) para garantir status "Expedição"
- [x] Implementar constantes `PROTECTED_LISTS` e bloqueios de criação/edição/exclusão/reordenação no back-end (`routes/kanban.py`)
- [x] Ocultar/Desabilitar botões de **editar** e **excluir** para listas protegidas em `templates/kanban/gerenciar_listas.html`
- [x] Impedir que SortableJS permita arrastar listas protegidas (front-end script em `gerenciar_listas.html`)
- [x] Ocultar opções de movimentar cartões para **Entrada** ou **Expedição** nos dropdowns de cada card (template `kanban/index.html`)
- [ ] Testar CRUD de listas e movimentação de cartões, garantindo que mensagens de erro apareçam quando apropriado
- [ ] Atualizar documentação/README com comportamento de listas protegidas

*Atualize esta lista conforme as etapas forem concluídas.*
