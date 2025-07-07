#!/usr/bin/env python3
"""
Script de migração para popular as listas Kanban no banco de dados
"""

from app import create_app
from models import db, KanbanLista

def migrate_kanban_lists():
    """Migra as listas Kanban hardcoded para o banco de dados"""
    
    # Listas padrão com suas configurações
    listas_padrao = [
        {'nome': 'Entrada', 'tipo_servico': 'Outros', 'cor': '#28a745', 'ordem': 1},
        {'nome': 'Serra', 'tipo_servico': 'Serra', 'cor': '#dc3545', 'ordem': 2},
        {'nome': 'Cortado a Distribuir', 'tipo_servico': 'Serra', 'cor': '#fd7e14', 'ordem': 3},
        {'nome': 'Mazak', 'tipo_servico': 'Torno CNC', 'cor': '#007bff', 'ordem': 4},
        {'nome': 'GLM240', 'tipo_servico': 'Torno CNC', 'cor': '#007bff', 'ordem': 5},
        {'nome': 'Glory', 'tipo_servico': 'Torno CNC', 'cor': '#007bff', 'ordem': 6},
        {'nome': 'Doosan', 'tipo_servico': 'Torno CNC', 'cor': '#007bff', 'ordem': 7},
        {'nome': 'Tesla', 'tipo_servico': 'Torno CNC', 'cor': '#007bff', 'ordem': 8},
        {'nome': 'Torno Manual', 'tipo_servico': 'Manual', 'cor': '#6f42c1', 'ordem': 9},
        {'nome': 'Fresa Manual', 'tipo_servico': 'Manual', 'cor': '#6f42c1', 'ordem': 10},
        {'nome': 'Rebarbagem', 'tipo_servico': 'Manual', 'cor': '#6f42c1', 'ordem': 11},
        {'nome': 'Parada Próxima Etapa', 'tipo_servico': 'Outros', 'cor': '#ffc107', 'ordem': 12},
        {'nome': 'D800 / D800 Plus', 'tipo_servico': 'Centro de Usinagem', 'cor': '#20c997', 'ordem': 13},
        {'nome': 'Glory1000', 'tipo_servico': 'Centro de Usinagem', 'cor': '#20c997', 'ordem': 14},
        {'nome': 'Montagem Modelo', 'tipo_servico': 'Outros', 'cor': '#6c757d', 'ordem': 15},
        {'nome': 'Serviço Terceiro', 'tipo_servico': 'Terceiros', 'cor': '#e83e8c', 'ordem': 16},
        {'nome': 'Solda', 'tipo_servico': 'Acabamento', 'cor': '#fd7e14', 'ordem': 17},
        {'nome': 'Têmpera', 'tipo_servico': 'Acabamento', 'cor': '#fd7e14', 'ordem': 18},
        {'nome': 'Retífica', 'tipo_servico': 'Acabamento', 'cor': '#fd7e14', 'ordem': 19},
        {'nome': 'Expedição', 'tipo_servico': 'Outros', 'cor': '#198754', 'ordem': 20},
    ]
    
    app = create_app()
    
    with app.app_context():
        print("Iniciando migração das listas Kanban...")
        
        # Verificar se já existem listas no banco
        listas_existentes = KanbanLista.query.count()
        if listas_existentes > 0:
            print(f"Já existem {listas_existentes} listas no banco de dados.")
            resposta = input("Deseja continuar e adicionar apenas as listas que não existem? (s/n): ")
            if resposta.lower() != 's':
                print("Migração cancelada.")
                return
        
        listas_adicionadas = 0
        listas_existentes_nomes = []
        
        for lista_data in listas_padrao:
            # Verificar se a lista já existe
            lista_existente = KanbanLista.query.filter_by(nome=lista_data['nome']).first()
            
            if lista_existente:
                listas_existentes_nomes.append(lista_data['nome'])
                continue
            
            # Criar nova lista
            nova_lista = KanbanLista(
                nome=lista_data['nome'],
                tipo_servico=lista_data['tipo_servico'],
                cor=lista_data['cor'],
                ordem=lista_data['ordem'],
                ativa=True
            )
            
            db.session.add(nova_lista)
            listas_adicionadas += 1
            print(f"Adicionada: {lista_data['nome']} ({lista_data['tipo_servico']})")
        
        # Salvar alterações
        try:
            db.session.commit()
            print(f"\nMigração concluída com sucesso!")
            print(f"Listas adicionadas: {listas_adicionadas}")
            
            if listas_existentes_nomes:
                print(f"Listas que já existiam: {len(listas_existentes_nomes)}")
                print(f"Nomes: {', '.join(listas_existentes_nomes)}")
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao salvar no banco de dados: {e}")
            return
        
        print("\nAs listas Kanban agora são gerenciadas dinamicamente pelo banco de dados.")
        print("Acesse /kanban/listas para gerenciar as listas.")

if __name__ == '__main__':
    migrate_kanban_lists()
