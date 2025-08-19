#!/usr/bin/env python3
"""
Script para debugar por que OS-2025-08-002 aparece no dashboard quando deveria estar entregue
"""

from app import create_app
from models import db, OrdemServico, StatusProducaoOS, Pedido, PedidoOrdemServico
from sqlalchemy.orm import joinedload

app = create_app()

with app.app_context():
    print("=== DEBUG: OS-2025-08-002 ===")
    
    # Buscar a OS específica
    os_002 = OrdemServico.query.filter_by(numero='OS-2025-08-002').first()
    
    if not os_002:
        print("❌ OS-2025-08-002 não encontrada no banco!")
        exit(1)
    
    print(f"✅ OS encontrada: ID={os_002.id}, Número={os_002.numero}")
    print(f"   Data criação: {os_002.data_criacao}")
    print(f"   Status geral: {getattr(os_002, 'status', 'N/A')}")
    
    # Verificar atributos disponíveis
    print(f"   Atributos disponíveis: {[attr for attr in dir(os_002) if not attr.startswith('_')]}")
    
    # Verificar status de produção
    status_producao = StatusProducaoOS.query.filter_by(ordem_servico_id=os_002.id).first()
    
    if status_producao:
        print(f"\n📊 Status de Produção:")
        print(f"   ID: {status_producao.id}")
        print(f"   Status atual: '{status_producao.status_atual}'")
        print(f"   Início ação: {status_producao.inicio_acao}")
        print(f"   Operador atual: {status_producao.operador_atual_id}")
        print(f"   Trabalho atual: {status_producao.trabalho_atual_id}")
        print(f"   Item atual: {status_producao.item_atual_id}")
    else:
        print("\n❌ Nenhum status de produção encontrado")
    
    # Verificar pedidos associados
    pedidos = (
        Pedido.query.options(
            joinedload(Pedido.ordens_servico)
        )
        .join(PedidoOrdemServico)
        .filter(PedidoOrdemServico.ordem_servico_id == os_002.id)
        .all()
    )
    
    print(f"\n📦 Pedidos associados ({len(pedidos)}):")
    for pedido in pedidos:
        print(f"   Pedido ID: {pedido.id}")
        print(f"   Status: {getattr(pedido, 'status', 'N/A')}")
        print(f"   Data entrega: {getattr(pedido, 'data_entrega', 'N/A')}")
        print(f"   Entregue: {getattr(pedido, 'entregue', 'N/A')}")
        print(f"   ---")
    
    # Verificar critério de filtragem do dashboard
    print(f"\n🔍 Critério de filtragem do dashboard:")
    if status_producao:
        criterio_ativo = status_producao.status_atual != 'Finalizado'
        print(f"   Status atual != 'Finalizado': {criterio_ativo}")
        print(f"   Status atual: '{status_producao.status_atual}'")
        
        if criterio_ativo:
            print("   ⚠️  MOTIVO: OS aparece no dashboard porque status != 'Finalizado'")
        else:
            print("   ✅ OS não deveria aparecer no dashboard")
    
    # Verificar se há lista_kanban definida (pode estar em outro campo)
    lista_kanban_field = getattr(os_002, 'lista_kanban', None) or getattr(os_002, 'kanban_lista', None)
    if lista_kanban_field:
        print(f"\n🏭 Lista Kanban: '{lista_kanban_field}'")
        print("   ⚠️  OS tem lista_kanban definida, pode aparecer no dashboard por isso")
    else:
        print("\n❌ Sem lista_kanban definida")
    
    print("\n" + "="*50)
    print("CONCLUSÃO:")
    
    if status_producao and status_producao.status_atual != 'Finalizado':
        print("🔴 PROBLEMA IDENTIFICADO:")
        print(f"   A OS-2025-08-002 aparece no dashboard porque:")
        print(f"   - Tem status de produção: '{status_producao.status_atual}'")
        print(f"   - Status != 'Finalizado'")
        print(f"   - Critério do dashboard: StatusProducaoOS.status_atual != 'Finalizado'")
        print(f"\n💡 SOLUÇÃO:")
        print(f"   Para remover do dashboard, o status deve ser alterado para 'Finalizado'")
        print(f"   ou a lógica de filtragem deve considerar outros critérios (ex: pedido entregue)")
    else:
        print("✅ Status correto - investigar outros critérios")
