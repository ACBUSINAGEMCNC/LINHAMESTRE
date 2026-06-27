from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from models import db, PedidoConsumo, ItemPedidoConsumo, ItemConsumo, Item
from datetime import datetime
import logging

pedidos_consumo = Blueprint('pedidos_consumo', __name__)
logger = logging.getLogger(__name__)


def _ensure_consumo_schema():
    try:
        from migrations.add_consumo_tables import migrate_postgres, migrate_sqlite
        if db.engine.url.drivername.startswith('postgresql'):
            return migrate_postgres()
        return migrate_sqlite()
    except Exception as e:
        logger.warning(f"Erro ao garantir schema consumo: {e}")
        return False


def _next_numero():
    from sqlalchemy import func
    last = db.session.query(func.max(PedidoConsumo.numero)).scalar()
    if last and last.startswith('UC-'):
        try:
            n = int(last.split('-')[1]) + 1
        except Exception:
            n = 1
    else:
        n = 1
    return f'UC-{n:05d}'


def _next_codigo_item():
    """Gera o próximo código automático para ItemConsumo: IC-001, IC-002, ..."""
    from sqlalchemy import func
    last = db.session.query(func.max(ItemConsumo.codigo)).filter(
        ItemConsumo.codigo.like('IC-%')
    ).scalar()
    if last:
        try:
            n = int(last.split('-')[1]) + 1
        except Exception:
            n = 1
    else:
        n = 1
    return f'IC-{n:03d}'


# ── Manutenção / correção de códigos ─────────────────────────────────────────

@pedidos_consumo.route('/consumo/itens/corrigir-codigos', methods=['POST'])
def corrigir_codigos_item_consumo():
    """Renumera todos os itens cujo código não segue o padrão IC-NNN."""
    import re
    padrao = re.compile(r'^IC-\d+$')

    todos = ItemConsumo.query.order_by(ItemConsumo.id).all()
    itens_errados = [i for i in todos if not padrao.match(i.codigo or '')]

    if not itens_errados:
        flash('Nenhum item com código fora do padrão encontrado.', 'info')
        return redirect(url_for('pedidos_consumo.listar_itens_consumo'))

    proximo = 1

    corrigidos = []
    for item in itens_errados:
        novo = f'IC-{proximo:03d}'
        corrigidos.append(f'"{item.codigo}" → {novo}')
        item.codigo = novo
        proximo += 1

    db.session.commit()
    flash(f'{len(corrigidos)} item(s) corrigido(s): ' + ', '.join(corrigidos), 'success')
    return redirect(url_for('pedidos_consumo.listar_itens_consumo'))


# ── Itens de consumo (cadastro) ──────────────────────────────────────────────

@pedidos_consumo.route('/consumo/itens')
def listar_itens_consumo():
    _ensure_consumo_schema()
    itens = ItemConsumo.query.order_by(ItemConsumo.categoria, ItemConsumo.nome).all()
    return render_template('consumo/itens_consumo.html', itens=itens)


@pedidos_consumo.route('/consumo/itens/novo', methods=['GET', 'POST'])
def novo_item_consumo():
    _ensure_consumo_schema()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return redirect(request.url)

        codigo = _next_codigo_item()

        item = ItemConsumo(
            codigo=codigo,
            nome=nome,
            descricao=request.form.get('descricao', '').strip() or None,
            unidade=request.form.get('unidade', 'un').strip(),
            categoria=request.form.get('categoria', '').strip() or None,
            ativo=True,
        )
        db.session.add(item)
        db.session.commit()
        flash(f'Item {codigo} cadastrado com sucesso.', 'success')
        return redirect(url_for('pedidos_consumo.listar_itens_consumo'))

    proximo_codigo = _next_codigo_item()
    return render_template('consumo/novo_item_consumo.html', proximo_codigo=proximo_codigo)


@pedidos_consumo.route('/consumo/itens/editar/<int:item_id>', methods=['GET', 'POST'])
def editar_item_consumo(item_id):
    _ensure_consumo_schema()
    item = ItemConsumo.query.get_or_404(item_id)
    if request.method == 'POST':
        item.nome = request.form.get('nome', item.nome).strip()
        item.descricao = request.form.get('descricao', '').strip() or None
        item.unidade = request.form.get('unidade', 'un').strip()
        item.categoria = request.form.get('categoria', '').strip() or None
        item.ativo = request.form.get('ativo') == '1'
        db.session.commit()
        flash('Item de consumo atualizado.', 'success')
        return redirect(url_for('pedidos_consumo.listar_itens_consumo'))
    return render_template('consumo/editar_item_consumo.html', item=item)


@pedidos_consumo.route('/consumo/itens/toggle/<int:item_id>', methods=['POST'])
def toggle_item_consumo(item_id):
    item = ItemConsumo.query.get_or_404(item_id)
    item.ativo = not item.ativo
    db.session.commit()
    return redirect(url_for('pedidos_consumo.listar_itens_consumo'))


# ── API de busca de itens (para o modal do pedido) ───────────────────────────

@pedidos_consumo.route('/consumo/api/buscar-itens')
def api_buscar_itens():
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', 'consumo')

    resultados = []

    if tipo in ('consumo', 'todos'):
        query = ItemConsumo.query.filter(ItemConsumo.ativo == True)
        if q:
            query = query.filter(
                db.or_(
                    ItemConsumo.nome.ilike(f'%{q}%'),
                    ItemConsumo.codigo.ilike(f'%{q}%'),
                    ItemConsumo.categoria.ilike(f'%{q}%'),
                )
            )
        for ic in query.order_by(ItemConsumo.nome).limit(30).all():
            resultados.append({
                'tipo': 'consumo',
                'id': ic.id,
                'codigo': ic.codigo,
                'nome': ic.nome,
                'unidade': ic.unidade,
                'categoria': ic.categoria or '',
            })

    if tipo in ('sistema', 'todos'):
        query = Item.query
        if q:
            query = query.filter(
                db.or_(
                    Item.nome.ilike(f'%{q}%'),
                    Item.codigo_acb.ilike(f'%{q}%'),
                )
            )
        for it in query.order_by(Item.nome).limit(30).all():
            resultados.append({
                'tipo': 'sistema',
                'id': it.id,
                'codigo': it.codigo_acb or '',
                'nome': it.nome,
                'unidade': 'un',
                'categoria': it.tipo_item or '',
            })

    return jsonify(resultados)


# ── Pedidos de consumo ────────────────────────────────────────────────────────

@pedidos_consumo.route('/consumo/pedidos')
def listar_pedidos_consumo():
    _ensure_consumo_schema()
    pedidos = PedidoConsumo.query.order_by(PedidoConsumo.data_criacao.desc()).all()
    return render_template('consumo/listar.html', pedidos=pedidos)


@pedidos_consumo.route('/consumo/pedidos/novo', methods=['GET', 'POST'])
def novo_pedido_consumo():
    _ensure_consumo_schema()
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip() or None
        observacoes = request.form.get('observacoes', '').strip() or None
        status = request.form.get('status', 'aberto').strip()
        status_validos = ['aberto', 'enviado_aguardando', 'concluido', 'cancelado', 'nao_comprado']

        pedido = PedidoConsumo(
            numero=_next_numero(),
            titulo=titulo,
            observacoes=observacoes,
            status=status if status in status_validos else 'aberto'
        )
        db.session.add(pedido)
        db.session.flush()

        _salvar_itens_pedido(pedido, request.form)

        db.session.commit()
        flash(f'Pedido {pedido.numero} criado com sucesso.', 'success')
        return redirect(url_for('pedidos_consumo.visualizar_pedido_consumo', pedido_id=pedido.id))

    itens_consumo = ItemConsumo.query.filter_by(ativo=True).order_by(ItemConsumo.categoria, ItemConsumo.nome).all()
    return render_template('consumo/novo.html', itens_consumo=itens_consumo)


@pedidos_consumo.route('/consumo/pedidos/visualizar/<int:pedido_id>')
def visualizar_pedido_consumo(pedido_id):
    _ensure_consumo_schema()
    pedido = PedidoConsumo.query.get_or_404(pedido_id)
    return render_template('consumo/visualizar.html', pedido=pedido)


@pedidos_consumo.route('/consumo/pedidos/editar/<int:pedido_id>', methods=['GET', 'POST'])
def editar_pedido_consumo(pedido_id):
    _ensure_consumo_schema()
    pedido = PedidoConsumo.query.get_or_404(pedido_id)

    if request.method == 'POST':
        pedido.titulo = request.form.get('titulo', '').strip() or None
        pedido.observacoes = request.form.get('observacoes', '').strip() or None
        pedido.status = request.form.get('status', 'aberto').strip() or 'aberto'

        # Remove linhas existentes e recria
        for linha in list(pedido.itens):
            db.session.delete(linha)
        db.session.flush()

        _salvar_itens_pedido(pedido, request.form)

        db.session.commit()
        flash('Pedido atualizado.', 'success')
        return redirect(url_for('pedidos_consumo.visualizar_pedido_consumo', pedido_id=pedido.id))

    itens_consumo = ItemConsumo.query.filter_by(ativo=True).order_by(ItemConsumo.categoria, ItemConsumo.nome).all()
    return render_template('consumo/editar.html', pedido=pedido, itens_consumo=itens_consumo)


@pedidos_consumo.route('/consumo/pedidos/excluir/<int:pedido_id>', methods=['POST'])
def excluir_pedido_consumo(pedido_id):
    pedido = PedidoConsumo.query.get_or_404(pedido_id)
    db.session.delete(pedido)
    db.session.commit()
    flash('Pedido excluído.', 'success')
    return redirect(url_for('pedidos_consumo.listar_pedidos_consumo'))


@pedidos_consumo.route('/consumo/pedidos/aprovar/<int:pedido_id>', methods=['POST'])
def aprovar_pedido_consumo(pedido_id):
    pedido = PedidoConsumo.query.get_or_404(pedido_id)
    usuario = getattr(g, 'usuario', None)
    if not usuario or getattr(usuario, 'nivel_acesso', None) != 'admin':
        flash('Sem permissão para aprovar.', 'danger')
        return redirect(url_for('pedidos_consumo.visualizar_pedido_consumo', pedido_id=pedido.id))
    from models import local_now_naive
    pedido.aprovado_em = local_now_naive()
    pedido.aprovado_por_id = usuario.id
    pedido.aprovado_por_nome = getattr(usuario, 'nome', '') or getattr(usuario, 'username', '')
    db.session.commit()
    flash('Pedido aprovado.', 'success')
    return redirect(url_for('pedidos_consumo.visualizar_pedido_consumo', pedido_id=pedido.id))


@pedidos_consumo.route('/consumo/pedidos/desaprovar/<int:pedido_id>', methods=['POST'])
def desaprovar_pedido_consumo(pedido_id):
    pedido = PedidoConsumo.query.get_or_404(pedido_id)
    pedido.aprovado_em = None
    pedido.aprovado_por_id = None
    pedido.aprovado_por_nome = None
    db.session.commit()
    flash('Aprovação removida.', 'warning')
    return redirect(url_for('pedidos_consumo.visualizar_pedido_consumo', pedido_id=pedido.id))


@pedidos_consumo.route('/consumo/pedidos/atualizar-status/<int:pedido_id>', methods=['POST'])
def atualizar_status_pedido_consumo(pedido_id):
    pedido = PedidoConsumo.query.get_or_404(pedido_id)
    novo_status = request.form.get('status', 'aberto').strip()
    status_validos = ['aberto', 'enviado_aguardando', 'concluido', 'cancelado', 'nao_comprado']
    pedido.status = novo_status if novo_status in status_validos else 'aberto'
    db.session.commit()
    flash(f'Pedido {pedido.numero} atualizado para {pedido.status}.', 'success')
    return redirect(url_for('pedidos_consumo.visualizar_pedido_consumo', pedido_id=pedido.id))


@pedidos_consumo.route('/consumo/pedidos/imprimir/<int:pedido_id>')
def imprimir_pedido_consumo(pedido_id):
    _ensure_consumo_schema()
    pedido = PedidoConsumo.query.get_or_404(pedido_id)
    return render_template('consumo/imprimir.html', pedido=pedido)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _salvar_itens_pedido(pedido, form):
    """Lê os campos do formulário e cria ItemPedidoConsumo para cada linha."""
    tipos = form.getlist('linha_tipo[]')
    ids = form.getlist('linha_id[]')
    descricoes = form.getlist('linha_descricao[]')
    quantidades = form.getlist('linha_quantidade[]')
    unidades = form.getlist('linha_unidade[]')
    observacoes = form.getlist('linha_observacao[]')

    for i, tipo in enumerate(tipos):
        qtd_raw = quantidades[i] if i < len(quantidades) else '1'
        try:
            qtd = float(qtd_raw)
        except Exception:
            qtd = 1.0
        if qtd <= 0:
            continue

        desc = descricoes[i].strip() if i < len(descricoes) else ''
        rid = ids[i].strip() if i < len(ids) else ''
        und = unidades[i].strip() if i < len(unidades) else 'un'
        obs = observacoes[i].strip() if i < len(observacoes) else ''

        linha = ItemPedidoConsumo(
            pedido_consumo_id=pedido.id,
            quantidade=qtd,
            unidade=und or 'un',
            observacao=obs or None,
        )

        if tipo == 'consumo' and rid:
            linha.item_consumo_id = int(rid)
        elif tipo == 'sistema' and rid:
            linha.item_id = int(rid)
        else:
            if not desc:
                continue
            linha.descricao_livre = desc

        db.session.add(linha)
