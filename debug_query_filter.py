#!/usr/bin/env python3
"""
Debug da query de filtragem para entender por que OS-2025-08-002 ainda aparece
"""

from app import create_app
from models import db, OrdemServico, StatusProducaoOS, Pedido, PedidoOrdemServico
from sqlalchemy.orm import joinedload

app = create_app()

with app.app_context():
    print("=== DEBUG QUERY FILTER ===")
    
    # Testar a query original (sem filtro)
    print("\n1. Query ORIGINAL (sem filtro de entregues):")
    status_originais = (
        StatusProducaoOS.query
        .filter(StatusProducaoOS.status_atual != 'Finalizado')
        .all()
    )
    print(f"   Total sem filtro: {len(status_originais)}")
    for s in status_originais:
        print(f"   - Status ID {s.id}: OS {s.ordem_servico_id}, Status: {s.status_atual}")
    
    # Testar a query com filtro
    print("\n2. Query COM FILTRO (excluindo entregues):")
    try:
        status_filtrados = (
            StatusProducaoOS.query
            .filter(StatusProducaoOS.status_atual != 'Finalizado')
            .filter(~StatusProducaoOS.ordem_servico.has(
                OrdemServico.pedidos.any(
                    PedidoOrdemServico.pedido.has(Pedido.status == 'entregue')
                )
            ))
            .all()
        )
        print(f"   Total com filtro: {len(status_filtrados)}")
        for s in status_filtrados:
            print(f"   - Status ID {s.id}: OS {s.ordem_servico_id}, Status: {s.status_atual}")
    except Exception as e:
        print(f"   ❌ ERRO na query filtrada: {e}")
    
    # Verificar especificamente a OS-2025-08-002
    print("\n3. Verificação específica OS-2025-08-002:")
    os_002 = OrdemServico.query.filter_by(numero='OS-2025-08-002').first()
    if os_002:
        print(f"   OS ID: {os_002.id}")
        
        # Verificar pedidos
        pedidos = (
            Pedido.query
            .join(PedidoOrdemServico)
            .filter(PedidoOrdemServico.ordem_servico_id == os_002.id)
            .all()
        )
        print(f"   Pedidos associados: {len(pedidos)}")
        for p in pedidos:
            print(f"   - Pedido ID {p.id}: Status '{p.status}'")
        
        # Testar condição do filtro manualmente
        tem_pedido_entregue = any(p.status == 'entregue' for p in pedidos)
        print(f"   Tem pedido entregue: {tem_pedido_entregue}")
        print(f"   Deveria ser excluída: {tem_pedido_entregue}")
        
        # Verificar status de produção
        status_prod = StatusProducaoOS.query.filter_by(ordem_servico_id=os_002.id).first()
        if status_prod:
            print(f"   Status produção: '{status_prod.status_atual}'")
            print(f"   Status != 'Finalizado': {status_prod.status_atual != 'Finalizado'}")
    
    print("\n4. Teste da condição SQLAlchemy:")
    # Testar se a condição SQLAlchemy está funcionando
    try:
        # Buscar OS que TÊM pedidos entregues
        os_com_entregues = (
            OrdemServico.query
            .filter(OrdemServico.pedidos.any(
                PedidoOrdemServico.pedido.has(Pedido.status == 'entregue')
            ))
            .all()
        )
        print(f"   OS com pedidos entregues: {len(os_com_entregues)}")
        for os in os_com_entregues:
            print(f"   - {os.numero} (ID: {os.id})")
            
        # Buscar OS que NÃO têm pedidos entregues
        os_sem_entregues = (
            OrdemServico.query
            .filter(~OrdemServico.pedidos.any(
                PedidoOrdemServico.pedido.has(Pedido.status == 'entregue')
            ))
            .all()
        )
        print(f"   OS SEM pedidos entregues: {len(os_sem_entregues)}")
        for os in os_sem_entregues:
            print(f"   - {os.numero} (ID: {os.id})")
            
    except Exception as e:
        print(f"   ❌ ERRO no teste SQLAlchemy: {e}")
        
    print("\n" + "="*50)
