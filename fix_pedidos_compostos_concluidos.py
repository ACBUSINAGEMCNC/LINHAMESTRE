from app import create_app
from models import db, Pedido


def fix_pedidos_compostos_concluidos(dry_run=False):
    app = create_app()
    with app.app_context():
        from datetime import datetime
        # O app registra auditoria no SQLAlchemy before_flush e, em produção, grava em audit_log.
        # Em scripts, isso pode falhar por falta de request/session e por FK de usuario.
        # Para correções pontuais como esta, desabilitamos a auditoria.
        db.session.info['_audit_logging_disabled'] = True

        pedidos = Pedido.query.filter(Pedido.data_entrega.is_(None)).all()

        total_verificados = 0
        total_corrigidos = 0

        for p in pedidos:
            if not p or not getattr(p, 'item', None):
                continue
            if not getattr(p.item, 'eh_composto', False):
                continue

            total_verificados += 1

            virtuais = Pedido.query.filter(Pedido.numero_pedido.like(f"AUTO-%-{p.id}")).all()
            if not virtuais:
                continue

            os_ids = set()
            os_list = []
            for pv in virtuais:
                for assoc in pv.ordens_servico or []:
                    if assoc.ordem_servico and assoc.ordem_servico_id not in os_ids:
                        os_ids.add(assoc.ordem_servico_id)
                        os_list.append(assoc.ordem_servico)

            if not os_list:
                continue

            if all((os.status == 'Finalizado') for os in os_list):
                total_corrigidos += 1
                numeros = ', '.join(sorted([o.numero for o in os_list if o and o.numero]))
                print(f"✅ Pedido original {p.id} ({p.numero_pedido}) -> marcar entregue. OS: {numeros}")
                if not dry_run:
                    p.data_entrega = datetime.now().date()

        if not dry_run and total_corrigidos > 0:
            db.session.commit()

        print(f"\nVerificados: {total_verificados}")
        print(f"Corrigidos: {total_corrigidos} (dry_run={dry_run})")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    fix_pedidos_compostos_concluidos(dry_run=args.dry_run)
