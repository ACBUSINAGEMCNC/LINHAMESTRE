#!/usr/bin/env python3
"""
Debug dos cartões de progresso e cartões fantasma no dashboard
"""

from app import create_app
from models import db, OrdemServico, StatusProducaoOS, CartaoFantasma, ApontamentoProducao
from sqlalchemy.orm import joinedload

app = create_app()

with app.app_context():
    print("=== DEBUG CARTÕES DE PROGRESSO E FANTASMA ===")
    
    # 1. Verificar OS sem apontamento ativo mas com histórico
    print("\n1. OS sem apontamento ativo mas com histórico:")
    os_sem_status = (
        OrdemServico.query
        .filter(~OrdemServico.id.in_(
            db.session.query(StatusProducaoOS.ordem_servico_id)
            .filter(StatusProducaoOS.status_atual != 'Finalizado')
        ))
        .limit(5)
        .all()
    )
    
    for os in os_sem_status:
        print(f"   OS {os.numero} (ID: {os.id}):")
        
        # Buscar último apontamento
        ultimo_ap = (
            ApontamentoProducao.query
            .filter_by(ordem_servico_id=os.id)
            .filter(ApontamentoProducao.quantidade != None)
            .order_by(ApontamentoProducao.data_hora.desc())
            .first()
        )
        
        if ultimo_ap:
            print(f"     - Último apontamento: {ultimo_ap.quantidade} peças")
            print(f"     - Data: {ultimo_ap.data_hora}")
            print(f"     - Item: {ultimo_ap.item_id}, Trabalho: {ultimo_ap.trabalho_id}")
        else:
            print(f"     - Sem apontamentos com quantidade")
    
    # 2. Verificar cartões fantasma
    print("\n2. Cartões fantasma:")
    cartoes_fantasma = CartaoFantasma.query.all()
    print(f"   Total de cartões fantasma: {len(cartoes_fantasma)}")
    
    for cf in cartoes_fantasma:
        print(f"   Cartão fantasma ID {cf.id}:")
        print(f"     - OS ID: {cf.ordem_servico_id}")
        print(f"     - Lista: {cf.lista_kanban}")
        print(f"     - Ativo: {cf.ativo}")
        
        # Verificar se a OS existe
        os = OrdemServico.query.get(cf.ordem_servico_id)
        if os:
            print(f"     - OS: {os.numero}")
        else:
            print(f"     - ❌ OS não encontrada")
    
    # 3. Verificar lógica de filtragem atual
    print("\n3. Teste da lógica atual do dashboard:")
    
    # Simular a query do dashboard
    status_ativos = (
        StatusProducaoOS.query
        .filter(StatusProducaoOS.status_atual != 'Finalizado')
        .all()
    )
    
    print(f"   Status ativos encontrados: {len(status_ativos)}")
    for status in status_ativos:
        os = status.ordem_servico
        print(f"   - OS {os.numero}: {status.status_atual}")
        print(f"     Quantidade atual: {getattr(status, 'quantidade_atual', 'N/A')}")
        
        # Buscar último apontamento para esta OS
        ultimo_ap = (
            ApontamentoProducao.query
            .filter_by(ordem_servico_id=status.ordem_servico_id)
            .filter(ApontamentoProducao.quantidade != None)
            .order_by(ApontamentoProducao.data_hora.desc())
            .first()
        )
        
        if ultimo_ap:
            print(f"     Último apontamento: {ultimo_ap.quantidade} peças")
        else:
            print(f"     Sem apontamentos")
    
    # 4. Verificar OS em máquinas (para cartões sem status ativo)
    print("\n4. OS em máquinas (status = nome da lista):")
    listas_kanban = ['SERRA', 'GLM240', 'DOOSAN', 'D800', 'MAZAK']
    
    os_em_maquinas = (
        OrdemServico.query
        .filter(db.func.lower(db.func.trim(OrdemServico.status)).in_([l.lower() for l in listas_kanban]))
        .all()
    )
    
    print(f"   OS em máquinas encontradas: {len(os_em_maquinas)}")
    for os in os_em_maquinas:
        print(f"   - OS {os.numero}: Status '{os.status}'")
        
        # Verificar se tem status ativo
        status_ativo = StatusProducaoOS.query.filter_by(ordem_servico_id=os.id).first()
        if status_ativo:
            print(f"     Status ativo: {status_ativo.status_atual}")
        else:
            print(f"     ❌ SEM status ativo - deveria aparecer como cartão básico")
            
            # Buscar último apontamento
            ultimo_ap = (
                ApontamentoProducao.query
                .filter_by(ordem_servico_id=os.id)
                .filter(ApontamentoProducao.quantidade != None)
                .order_by(ApontamentoProducao.data_hora.desc())
                .first()
            )
            
            if ultimo_ap:
                print(f"     Último apontamento: {ultimo_ap.quantidade} peças")
            else:
                print(f"     Sem apontamentos")
    
    print("\n" + "="*60)
