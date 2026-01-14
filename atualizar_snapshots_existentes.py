"""
Script para atualizar quantidade_snapshot em registros PedidoOrdemServico existentes.
Preenche o snapshot com a quantidade atual do Pedido para registros que não têm snapshot.
"""

from app import create_app
from models import db, PedidoOrdemServico, Pedido

def atualizar_snapshots():
    app = create_app()
    with app.app_context():
        # Buscar todos os PedidoOrdemServico sem snapshot
        registros_sem_snapshot = PedidoOrdemServico.query.filter(
            PedidoOrdemServico.quantidade_snapshot.is_(None)
        ).all()
        
        print(f"Encontrados {len(registros_sem_snapshot)} registros sem snapshot")
        
        atualizados = 0
        for pos in registros_sem_snapshot:
            if pos.pedido:
                pos.quantidade_snapshot = pos.pedido.quantidade
                atualizados += 1
                print(f"  Atualizado PedidoOrdemServico ID {pos.id}: snapshot = {pos.quantidade_snapshot}")
        
        if atualizados > 0:
            db.session.commit()
            print(f"\n✅ {atualizados} registros atualizados com sucesso!")
        else:
            print("\n✅ Nenhum registro precisou ser atualizado.")

if __name__ == "__main__":
    atualizar_snapshots()
