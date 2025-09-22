#!/usr/bin/env python3
"""
Script de debug para testar o sistema de itens compostos
"""

import os
import sys
from datetime import datetime

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Item, ItemComposto, Pedido, OrdemServico, PedidoOrdemServico

def debug_item_composto():
    """Debug do sistema de itens compostos"""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("DEBUG: SISTEMA DE ITENS COMPOSTOS")
        print("=" * 60)
        
        # 1. Verificar se existem itens compostos
        print("\n1. VERIFICANDO ITENS COMPOSTOS:")
        itens_compostos = Item.query.filter_by(eh_composto=True).all()
        print(f"   Total de itens compostos: {len(itens_compostos)}")
        
        for item in itens_compostos:
            print(f"   - {item.codigo_acb}: {item.nome}")
            print(f"     Componentes: {len(item.componentes)}")
            for comp in item.componentes:
                print(f"       * {comp.item_componente.codigo_acb}: {comp.item_componente.nome} (Qtd: {comp.quantidade})")
        
        # 2. Verificar pedidos de itens compostos
        print("\n2. VERIFICANDO PEDIDOS DE ITENS COMPOSTOS:")
        pedidos_compostos = []
        for item in itens_compostos:
            pedidos = Pedido.query.filter_by(item_id=item.id).all()
            pedidos_compostos.extend(pedidos)
            print(f"   Item {item.codigo_acb}: {len(pedidos)} pedido(s)")
            for pedido in pedidos:
                print(f"     - Pedido {pedido.numero_pedido}: Qtd {pedido.quantidade}")
                print(f"       Cliente: {pedido.cliente.nome if pedido.cliente else 'N/A'}")
                print(f"       Status OS: {pedido.numero_oc or 'Sem OS'}")
        
        # 3. Verificar OS geradas
        print("\n3. VERIFICANDO OS GERADAS:")
        total_os = OrdemServico.query.count()
        print(f"   Total de OS no sistema: {total_os}")
        
        # Verificar OS recentes
        os_recentes = OrdemServico.query.order_by(OrdemServico.data_criacao.desc()).limit(10).all()
        print(f"   Últimas 10 OS:")
        for os in os_recentes:
            pedidos_os = [pos.pedido for pos in os.pedidos]
            print(f"     - OS {os.numero}: {len(pedidos_os)} pedido(s)")
            for pedido in pedidos_os:
                item_info = f"{pedido.item.codigo_acb} - {pedido.item.nome}" if pedido.item else pedido.nome_item
                print(f"       * {item_info} (Qtd: {pedido.quantidade})")
        
        # 4. Testar função de desmembramento (simulação)
        print("\n4. TESTANDO LÓGICA DE DESMEMBRAMENTO:")
        if itens_compostos and pedidos_compostos:
            item_teste = itens_compostos[0]
            pedidos_teste = [p for p in pedidos_compostos if p.item_id == item_teste.id]
            
            if pedidos_teste:
                print(f"   Testando item: {item_teste.codigo_acb}")
                print(f"   Pedidos para teste: {len(pedidos_teste)}")
                
                quantidade_total = sum(p.quantidade for p in pedidos_teste)
                print(f"   Quantidade total: {quantidade_total}")
                
                print("   Componentes que seriam desmembrados:")
                for comp in item_teste.componentes:
                    qtd_componente = comp.quantidade * quantidade_total
                    print(f"     - {comp.item_componente.codigo_acb}: {qtd_componente} unidades")
                    
                    # Verificar se o componente tem materiais e trabalhos
                    materiais = len(comp.item_componente.materiais)
                    trabalhos = len(comp.item_componente.trabalhos)
                    print(f"       Materiais: {materiais}, Trabalhos: {trabalhos}")
        
        # 5. Verificar estrutura do banco
        print("\n5. VERIFICANDO ESTRUTURA DO BANCO:")
        try:
            # Testar query básica
            total_itens = Item.query.count()
            itens_simples = Item.query.filter_by(eh_composto=False).count()
            print(f"   Total de itens: {total_itens}")
            print(f"   Itens simples: {itens_simples}")
            print(f"   Itens compostos: {len(itens_compostos)}")
            
            # Testar relacionamentos
            total_componentes = ItemComposto.query.count()
            print(f"   Total de relacionamentos componente: {total_componentes}")
            
        except Exception as e:
            print(f"   ❌ Erro ao verificar estrutura: {str(e)}")
        
        print("\n" + "=" * 60)
        print("DEBUG CONCLUÍDO")
        print("=" * 60)

if __name__ == "__main__":
    debug_item_composto()
