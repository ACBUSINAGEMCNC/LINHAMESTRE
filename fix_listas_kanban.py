from app import create_app
from models import db, KanbanLista
from sqlalchemy import text

app = create_app()
app.app_context().push()

# Forçar ordem correta para Entrada e Expedição
print('Corrigindo ordem das listas protegidas...')

# Entrada sempre deve ser ordem=0
db.session.execute(text("UPDATE kanban_lista SET ordem = 0 WHERE nome = 'Entrada'"))
print('Entrada definida para ordem=0')

# Expedição sempre deve ser ordem=1000
db.session.execute(text("UPDATE kanban_lista SET ordem = 1000 WHERE nome = 'Expedição'"))
print('Expedição definida para ordem=1000')

# Reordenar outras listas sequencialmente (1, 2, 3, ...)
result = db.session.execute(text("SELECT id FROM kanban_lista WHERE nome NOT IN ('Entrada', 'Expedição') ORDER BY id"))
lista_ids = [row[0] for row in result]
for i, lista_id in enumerate(lista_ids, start=1):
    db.session.execute(text(f"UPDATE kanban_lista SET ordem = {i} WHERE id = {lista_id}"))

db.session.commit()

# Verificar resultado
result = db.session.execute(text("SELECT id, nome, ordem FROM kanban_lista ORDER BY ordem"))
print(f'\nListas após a correção:')
for row in result:
    print(f'  {row[0]}: {row[1]} (ordem={row[2]})')

print('\nListas corrigidas com sucesso!')
