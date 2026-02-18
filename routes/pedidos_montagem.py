from flask import Blueprint, render_template, redirect, url_for, request, flash
from datetime import datetime
from models import (
    db,
    PedidoMontagem,
    ItemPedidoMontagem,
    Fornecedor,
    CotacaoPedidoMontagem,
    CotacaoItemPedidoMontagem,
)

pedidos_montagem = Blueprint('pedidos_montagem', __name__)


@pedidos_montagem.route('/pedidos-montagem')
def listar_pedidos_montagem():
    pedidos = PedidoMontagem.query.all()
    return render_template('pedidos_montagem/listar.html', pedidos=pedidos)


@pedidos_montagem.route('/pedidos-montagem/visualizar/<int:pedido_id>')
def visualizar_pedido_montagem(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    itens = ItemPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id).all()
    return render_template('pedidos_montagem/visualizar.html', pedido=pedido, itens=itens)


@pedidos_montagem.route('/pedidos-montagem/numero/<string:numero>')
def visualizar_pedido_montagem_por_numero(numero):
    """Atalho: localizar PedidoMontagem pelo número (PMT-xxxxx) e redirecionar para a visualização."""
    pedido = PedidoMontagem.query.filter_by(numero=numero).first_or_404()
    return redirect(url_for('pedidos_montagem.visualizar_pedido_montagem', pedido_id=pedido.id))


@pedidos_montagem.route('/pedidos-montagem/imprimir/<int:pedido_id>')
def imprimir_pedido_montagem(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    itens = ItemPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id).all()
    return render_template('pedidos_montagem/imprimir.html', pedido=pedido, itens=itens)


@pedidos_montagem.route('/pedidos-montagem/comparativo/<int:pedido_id>')
def comparar_fornecedores(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id).all()

    cotacao_itens = CotacaoItemPedidoMontagem.query.join(
        CotacaoPedidoMontagem,
        CotacaoItemPedidoMontagem.cotacao_id == CotacaoPedidoMontagem.id,
    ).filter(CotacaoPedidoMontagem.pedido_montagem_id == pedido.id).all()

    cotacao_itens_map = {}
    for ci in cotacao_itens:
        cotacao_itens_map[f"{ci.cotacao_id}_{ci.item_pedido_montagem_id}"] = ci

    melhores = {}
    for item in pedido.itens:
        melhores_preco_val = None
        melhores_prazo_val = None
        melhores_pagamento_val = None
        for c in cotacoes:
            key = f"{c.id}_{item.id}"
            ci = cotacao_itens_map.get(key)
            preco_base = None
            if ci:
                preco_base = ci.preco_total if ci.preco_total is not None else ci.preco_unitario
                if preco_base is not None and ci.ipi_percent is not None:
                    preco_base = preco_base * (1.0 + (ci.ipi_percent / 100.0))
            if preco_base is not None:
                if melhores_preco_val is None or preco_base < melhores_preco_val:
                    melhores_preco_val = preco_base
            if ci and ci.prazo_entrega_dias is not None:
                if melhores_prazo_val is None or ci.prazo_entrega_dias < melhores_prazo_val:
                    melhores_prazo_val = ci.prazo_entrega_dias
            if ci and ci.prazo_pagamento_dias is not None:
                if melhores_pagamento_val is None or ci.prazo_pagamento_dias > melhores_pagamento_val:
                    melhores_pagamento_val = ci.prazo_pagamento_dias

        for c in cotacoes:
            key = f"{c.id}_{item.id}"
            ci = cotacao_itens_map.get(key)
            preco_base = None
            if ci:
                preco_base = ci.preco_total if ci.preco_total is not None else ci.preco_unitario
                if preco_base is not None and ci.ipi_percent is not None:
                    preco_base = preco_base * (1.0 + (ci.ipi_percent / 100.0))
            melhores[key] = {
                'melhor_preco': (melhores_preco_val is not None and preco_base is not None and preco_base == melhores_preco_val),
                'melhor_prazo': (melhores_prazo_val is not None and ci and ci.prazo_entrega_dias == melhores_prazo_val),
                'melhor_pagamento': (melhores_pagamento_val is not None and ci and ci.prazo_pagamento_dias == melhores_pagamento_val),
            }

    return render_template(
        'pedidos_montagem/comparativo.html',
        pedido=pedido,
        cotacoes=cotacoes,
        cotacao_itens_map=cotacao_itens_map,
        melhores=melhores,
    )


@pedidos_montagem.route('/pedidos-montagem/comparativo/<int:pedido_id>/fornecedor', methods=['POST'])
def adicionar_fornecedor_comparativo(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    nome = (request.form.get('nome_fornecedor') or '').strip()
    if not nome:
        flash('Informe o nome do fornecedor.', 'warning')
        return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))

    fornecedor = Fornecedor.query.filter_by(nome=nome).first()
    if not fornecedor:
        fornecedor = Fornecedor(nome=nome)
        db.session.add(fornecedor)
        db.session.flush()

    cotacao = CotacaoPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id, fornecedor_id=fornecedor.id).first()
    if cotacao:
        flash('Este fornecedor já existe neste comparativo.', 'info')
        return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))

    cotacao = CotacaoPedidoMontagem(pedido_montagem_id=pedido.id, fornecedor_id=fornecedor.id, data_criacao=datetime.utcnow())
    db.session.add(cotacao)
    db.session.commit()

    flash('Fornecedor adicionado ao comparativo.', 'success')
    return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_montagem.route('/pedidos-montagem/comparativo/<int:pedido_id>/salvar', methods=['POST'])
def salvar_comparativo(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id).all()

    def _get_float(field):
        val = request.form.get(field)
        if val is None or str(val).strip() == '':
            return None
        try:
            return float(str(val).replace(',', '.'))
        except ValueError:
            return None

    def _get_int(field):
        val = request.form.get(field)
        if val is None or str(val).strip() == '':
            return None
        try:
            return int(val)
        except ValueError:
            return None

    for c in cotacoes:
        for item in pedido.itens:
            preco_total = _get_float(f"preco_total_{c.id}_{item.id}")
            preco_por_kg = _get_float(f"preco_kg_{c.id}_{item.id}")
            preco = _get_float(f"preco_{c.id}_{item.id}")
            ipi = _get_float(f"ipi_{c.id}_{item.id}")
            entrega = _get_int(f"entrega_{c.id}_{item.id}")
            pagamento = _get_int(f"pagamento_{c.id}_{item.id}")
            qtd_escolhida = _get_int(f"qtd_escolhida_{c.id}_{item.id}")
            m_escolhidos = _get_float(f"m_escolhidos_{c.id}_{item.id}")

            ci = CotacaoItemPedidoMontagem.query.filter_by(cotacao_id=c.id, item_pedido_montagem_id=item.id).first()
            if not ci:
                ci = CotacaoItemPedidoMontagem(cotacao_id=c.id, item_pedido_montagem_id=item.id)
                db.session.add(ci)

            ci.preco_total = preco_total
            ci.preco_por_kg = preco_por_kg
            ci.preco_unitario = preco
            ci.ipi_percent = ipi
            ci.prazo_entrega_dias = entrega
            ci.prazo_pagamento_dias = pagamento
            ci.quantidade_escolhida = qtd_escolhida
            ci.metros_escolhidos = m_escolhidos

    db.session.commit()
    flash('Cotações salvas.', 'success')
    return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_montagem.route('/pedidos-montagem/comparativo/<int:pedido_id>/sugerir-rateio', methods=['POST'])
def sugerir_rateio(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id).all()
    if not cotacoes:
        flash('Adicione fornecedores antes de sugerir o rateio.', 'warning')
        return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))

    for item in pedido.itens:
        melhor_ci = None
        melhor_val = None

        for c in cotacoes:
            ci = CotacaoItemPedidoMontagem.query.filter_by(cotacao_id=c.id, item_pedido_montagem_id=item.id).first()
            if not ci:
                ci = CotacaoItemPedidoMontagem(cotacao_id=c.id, item_pedido_montagem_id=item.id)
                db.session.add(ci)
                db.session.flush()

            preco_base = ci.preco_total if ci.preco_total is not None else ci.preco_unitario
            if preco_base is None:
                continue
            if ci.ipi_percent is not None:
                preco_base = preco_base * (1.0 + (ci.ipi_percent / 100.0))

            if melhor_val is None or preco_base < melhor_val:
                melhor_val = preco_base
                melhor_ci = ci

        for c in cotacoes:
            ci = CotacaoItemPedidoMontagem.query.filter_by(cotacao_id=c.id, item_pedido_montagem_id=item.id).first()
            if not ci:
                continue
            ci.quantidade_escolhida = 0
            ci.metros_escolhidos = 0

        if melhor_ci:
            melhor_ci.quantidade_escolhida = int(item.quantidade or 0)
            melhor_ci.metros_escolhidos = 0

    db.session.commit()
    flash('Rateio sugerido com base no melhor preço (com IPI).', 'success')
    return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_montagem.route('/pedidos-montagem/comparativo/<int:pedido_id>/sugerir-rateio-entrega', methods=['POST'])
def sugerir_rateio_entrega(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id).all()
    if not cotacoes:
        flash('Adicione fornecedores antes de sugerir o rateio.', 'warning')
        return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))

    for item in pedido.itens:
        melhor_ci = None
        melhor_val = None

        for c in cotacoes:
            ci = CotacaoItemPedidoMontagem.query.filter_by(cotacao_id=c.id, item_pedido_montagem_id=item.id).first()
            if not ci:
                continue
            if ci.prazo_entrega_dias is None:
                continue
            if melhor_val is None or ci.prazo_entrega_dias < melhor_val:
                melhor_val = ci.prazo_entrega_dias
                melhor_ci = ci

        for c in cotacoes:
            ci = CotacaoItemPedidoMontagem.query.filter_by(cotacao_id=c.id, item_pedido_montagem_id=item.id).first()
            if not ci:
                continue
            ci.quantidade_escolhida = 0
            ci.metros_escolhidos = 0

        if melhor_ci:
            melhor_ci.quantidade_escolhida = int(item.quantidade or 0)
            melhor_ci.metros_escolhidos = 0

    db.session.commit()
    flash('Rateio sugerido com base no melhor prazo de entrega.', 'success')
    return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_montagem.route('/pedidos-montagem/comparativo/<int:pedido_id>/sugerir-rateio-pagamento', methods=['POST'])
def sugerir_rateio_pagamento(pedido_id):
    pedido = PedidoMontagem.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMontagem.query.filter_by(pedido_montagem_id=pedido.id).all()
    if not cotacoes:
        flash('Adicione fornecedores antes de sugerir o rateio.', 'warning')
        return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))

    for item in pedido.itens:
        melhor_ci = None
        melhor_val = None

        for c in cotacoes:
            ci = CotacaoItemPedidoMontagem.query.filter_by(cotacao_id=c.id, item_pedido_montagem_id=item.id).first()
            if not ci:
                continue
            if ci.prazo_pagamento_dias is None:
                continue
            if melhor_val is None or ci.prazo_pagamento_dias > melhor_val:
                melhor_val = ci.prazo_pagamento_dias
                melhor_ci = ci

        for c in cotacoes:
            ci = CotacaoItemPedidoMontagem.query.filter_by(cotacao_id=c.id, item_pedido_montagem_id=item.id).first()
            if not ci:
                continue
            ci.quantidade_escolhida = 0
            ci.metros_escolhidos = 0

        if melhor_ci:
            melhor_ci.quantidade_escolhida = int(item.quantidade or 0)
            melhor_ci.metros_escolhidos = 0

    db.session.commit()
    flash('Rateio sugerido com base no melhor prazo de pagamento.', 'success')
    return redirect(url_for('pedidos_montagem.comparar_fornecedores', pedido_id=pedido.id))
