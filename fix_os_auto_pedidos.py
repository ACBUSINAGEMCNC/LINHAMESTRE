from app import create_app
from models import db, OrdemServico, Pedido, PedidoOrdemServico


def _extract_original_id(numero_pedido: str):
    if not numero_pedido:
        return None
    if not numero_pedido.startswith('AUTO-'):
        return None
    try:
        return int(numero_pedido.split('-')[-1])
    except Exception:
        return None


def fix_os_auto_pedidos(ordem_id: int, keep_original_ids=None, dry_run: bool = True):
    app = create_app()
    with app.app_context():
        db.session.info['_audit_logging_disabled'] = True

        ordem = OrdemServico.query.get(ordem_id)
        if not ordem:
            raise SystemExit(f"OS não encontrada: {ordem_id}")

        assocs = list(ordem.pedidos or [])
        auto_assocs = []
        for a in assocs:
            p = a.pedido
            if not p or not p.numero_pedido:
                continue
            if p.numero_pedido.startswith('AUTO-'):
                auto_assocs.append(a)

        if not auto_assocs:
            print(f"OS {ordem.numero} ({ordem.id}) não possui pedidos AUTO-* para limpar.")
            return

        rows = []
        for a in auto_assocs:
            p = a.pedido
            original_id = _extract_original_id(p.numero_pedido)
            original = Pedido.query.get(original_id) if original_id else None
            rows.append(
                {
                    'assoc_id': a.id,
                    'pedido_id': p.id,
                    'numero_pedido': p.numero_pedido,
                    'item_id': p.item_id,
                    'quantidade': p.quantidade,
                    'original_id': original_id,
                    'original_numero': (original.numero_pedido if original else None),
                    'original_cliente': (original.cliente.nome if original and original.cliente else None),
                    'original_unidade': (original.unidade_entrega.nome if original and original.unidade_entrega else None),
                    'original_quantidade': (original.quantidade if original else None),
                }
            )

        print(f"\nOS: {ordem.numero} (id={ordem.id})")
        print(f"Pedidos AUTO encontrados: {len(rows)}")
        print("\nLista de AUTO-*")
        for r in rows:
            print(
                f"- pedido_id={r['pedido_id']} assoc_id={r['assoc_id']} num={r['numero_pedido']} qtd={r['quantidade']} "
                f"original_id={r['original_id']} original_num={r['original_numero']} cliente={r['original_cliente']} unidade={r['original_unidade']}"
            )

        keep_set = set(keep_original_ids or [])
        if keep_original_ids is None:
            print("\nInforme quais original_id devem PERMANECER nesta OS (separados por vírgula).")
            print("Exemplo: 237,238  (para manter só os AUTO-* destes pedidos originais)")
            raw = input("> ").strip()
            if raw:
                try:
                    keep_set = {int(x.strip()) for x in raw.split(',') if x.strip()}
                except Exception:
                    raise SystemExit("Entrada inválida. Use números separados por vírgula.")

        if not keep_set:
            raise SystemExit("Nenhum original_id informado para manter. Abortando para evitar apagar tudo.")

        to_delete = [r for r in rows if r['original_id'] not in keep_set]
        to_keep = [r for r in rows if r['original_id'] in keep_set]

        print(f"\nManter: {len(to_keep)} pedidos AUTO (originais: {sorted(list(keep_set))})")
        print(f"Remover: {len(to_delete)} pedidos AUTO")

        if dry_run:
            print("\nDRY-RUN: nada foi alterado. Rode com --apply para efetivar.")
            return

        for r in to_delete:
            assoc = PedidoOrdemServico.query.get(r['assoc_id'])
            pedido = Pedido.query.get(r['pedido_id'])
            if assoc:
                db.session.delete(assoc)
            if pedido:
                db.session.delete(pedido)

        db.session.commit()
        print("\nOK: limpeza aplicada.")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--ordem-id', type=int, required=True)
    parser.add_argument('--keep-original-ids', type=str, default=None)
    parser.add_argument('--apply', action='store_true')

    args = parser.parse_args()

    keep = None
    if args.keep_original_ids is not None:
        keep = []
        raw = (args.keep_original_ids or '').strip()
        if raw:
            keep = [int(x.strip()) for x in raw.split(',') if x.strip()]

    fix_os_auto_pedidos(
        ordem_id=args.ordem_id,
        keep_original_ids=keep,
        dry_run=(not args.apply),
    )
