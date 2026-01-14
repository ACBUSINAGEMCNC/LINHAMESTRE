"""
Script para debugar a detecção de quantidade alterada em itens compostos
"""

from app import create_app
from models import db, OrdemServico, PedidoOrdemServico, Pedido
import logging

logging.basicConfig(level=logging.DEBUG)

def debug_os(numero_os):
    app = create_app()
    with app.app_context():
        os = OrdemServico.query.filter_by(numero=numero_os).first()
        if not os:
            print(f"❌ OS {numero_os} não encontrada")
            return
        
        print(f"\n{'='*80}")
        print(f"🔍 Analisando OS: {os.numero}")
        print(f"{'='*80}\n")
        
        for pedido_os in os.pedidos:
            pedido = pedido_os.pedido
            print(f"\n📦 PedidoOrdemServico ID: {pedido_os.id}")
            print(f"   Pedido ID: {pedido.id}")
            print(f"   Número Pedido: {pedido.numero_pedido}")
            print(f"   Cliente: {pedido.cliente.nome}")
            print(f"   Item: {pedido.item.codigo_acb if pedido.item else pedido.nome_item}")
            print(f"   Quantidade Atual: {pedido.quantidade}")
            print(f"   Quantidade Snapshot: {pedido_os.quantidade_snapshot}")
            
            # Verificar se é pedido AUTO
            if pedido.numero_pedido and pedido.numero_pedido.startswith('AUTO-'):
                print(f"   ✓ É pedido virtual (AUTO)")
                
                # Extrair ID do pedido original
                import re
                match = re.search(r'-(\d+)$', pedido.numero_pedido)
                if match:
                    pedido_original_id = int(match.group(1))
                    print(f"   ✓ ID pedido original extraído: {pedido_original_id}")
                    
                    pedido_original = Pedido.query.get(pedido_original_id)
                    if pedido_original:
                        print(f"   ✓ Pedido original encontrado")
                        print(f"     - Item ID: {pedido_original.item_id}")
                        print(f"     - Quantidade: {pedido_original.quantidade}")
                        
                        if pedido_original.item_id:
                            item_composto = pedido_original.item
                            print(f"     - Item: {item_composto.codigo_acb}")
                            print(f"     - É composto: {item_composto.eh_composto}")
                            
                            if item_composto.eh_composto:
                                print(f"     ✓ Item composto confirmado")
                                print(f"     - Componentes: {len(item_composto.componentes)}")
                                
                                for comp_rel in item_composto.componentes:
                                    print(f"       • Componente ID: {comp_rel.item_componente_id}")
                                    print(f"         Fator: {comp_rel.quantidade}")
                                    
                                    if comp_rel.item_componente_id == pedido.item_id:
                                        quantidade_esperada = comp_rel.quantidade * pedido_original.quantidade
                                        print(f"       ✓ COMPONENTE ENCONTRADO!")
                                        print(f"         Quantidade esperada: {quantidade_esperada}")
                                        print(f"         Quantidade atual: {pedido.quantidade}")
                                        print(f"         Quantidade snapshot: {pedido_os.quantidade_snapshot}")
                                        
                                        if pedido.quantidade != quantidade_esperada:
                                            print(f"       ⚠️  QUANTIDADE ALTERADA DETECTADA!")
                                        else:
                                            print(f"       ✓ Quantidade está correta")
            
            # Verificar propriedade quantidade_alterada
            print(f"\n   🔍 Propriedade quantidade_alterada: {pedido_os.quantidade_alterada}")
            print(f"   {'='*70}")

if __name__ == "__main__":
    # Testar com a OS da imagem
    debug_os("OS-2026-01-003")
