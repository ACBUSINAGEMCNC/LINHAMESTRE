from app import create_app
from models import db, KanbanLista
from sqlalchemy import text

app = create_app()
app.app_context().push()

# Usar SQL direto para evitar audit_before_flush
print('Verificando e criando listas Entrada e Expedição...')

# Verificar se Entrada existe
result = db.session.execute(text("SELECT id, nome FROM kanban_lista WHERE nome = 'Entrada'"))
entrada = result.fetchone()
if not entrada:
    print('Criando lista: Entrada')
    db.session.execute(text("""
        INSERT INTO kanban_lista (nome, ordem, ativa, cor, data_criacao, data_atualizacao)
        VALUES ('Entrada', 0, true, '#28a745', NOW(), NOW())
    """))
else:
    print(f'Lista Entrada já existe (id={entrada[0]})')

# Verificar se Expedição existe
result = db.session.execute(text("SELECT id, nome FROM kanban_lista WHERE nome = 'Expedição'"))
expedicao = result.fetchone()
if not expedicao:
    print('Criando lista: Expedição')
    db.session.execute(text("""
        INSERT INTO kanban_lista (nome, ordem, ativa, cor, data_criacao, data_atualizacao)
        VALUES ('Expedição', 1000, true, '#dc3545', NOW(), NOW())
    """))
else:
    print(f'Lista Expedição já existe (id={expedicao[0]})')

# Reordenar listas existentes
print('\nReordenando listas...')
# Primeiro, definir ordem para Entrada e Expedição
db.session.execute(text("UPDATE kanban_lista SET ordem = 0 WHERE nome = 'Entrada'"))
db.session.execute(text("UPDATE kanban_lista SET ordem = 1000 WHERE nome = 'Expedição'"))

# Reordenar outras listas sequencialmente
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
