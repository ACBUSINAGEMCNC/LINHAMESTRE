from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, PedidoMaterial, ItemPedidoMaterial, Material, Item, ItemMaterial, Pedido, Fornecedor, CotacaoPedidoMaterial, CotacaoItemPedidoMaterial
from utils import validate_form_data, generate_next_code, parse_json_field
from datetime import datetime
from sqlalchemy.exc import IntegrityError

pedidos_material = Blueprint('pedidos_material', __name__)


def _build_material_item_map(pedido_material):
    pedidos_origem = []
    if pedido_material and pedido_material.numero:
        pedidos_origem = Pedido.query.filter_by(numero_pedido_material=pedido_material.numero).all()

    item_ids = []
    for p in pedidos_origem:
        if getattr(p, 'item_id', None):
            item_ids.append(p.item_id)

    if not item_ids:
        return {}

    itens = Item.query.filter(Item.id.in_(list(set(item_ids)))).all()
    itens_expandidos = []
    for it in itens:
        if it and getattr(it, 'eh_composto', False):
            for comp_rel in getattr(it, 'componentes', []) or []:
                comp_item = getattr(comp_rel, 'item_componente', None)
                if comp_item:
                    itens_expandidos.append(comp_item)
        else:
            itens_expandidos.append(it)

    vistos = set()
    itens_expandidos_unicos = []
    for it in itens_expandidos:
        if it and it.id not in vistos:
            vistos.add(it.id)
            itens_expandidos_unicos.append(it)

    itemmaterial = ItemMaterial.query.filter(ItemMaterial.item_id.in_([i.id for i in itens_expandidos_unicos])).all()
    material_to_item_ids = {}
    for im in itemmaterial:
        material_to_item_ids.setdefault(im.material_id, set()).add(im.item_id)

    item_by_id = {i.id: i for i in itens_expandidos_unicos}

    out = {}
    for material_id, ids in material_to_item_ids.items():
        items_payload = []
        for iid in sorted(list(ids)):
            it = item_by_id.get(iid)
            if not it:
                continue
            items_payload.append({
                'id': it.id,
                'codigo_acb': it.codigo_acb,
                'nome': it.nome,
                'imagem_url': it.imagem_path,
            })
        out[material_id] = items_payload
    return out

@pedidos_material.route('/pedidos-material')
def listar_pedidos_material():
    """Rota para listar todos os pedidos de material"""
    pedidos = PedidoMaterial.query.all()
    return render_template('pedidos_material/listar.html', pedidos=pedidos)

@pedidos_material.route('/pedidos-material/novo', methods=['GET', 'POST'])
def novo_pedido_material():
    """Rota para criar um novo pedido de material"""
    # Redirecionar para a página de pedidos onde o usuário pode usar o botão unificado de 'Gerar Material'
    flash('Utilize a página de Pedidos para gerar Pedidos de Material. Selecione os pedidos desejados e clique no botão "Gerar Material".', 'info')
    return redirect(url_for('pedidos.listar_pedidos'))

@pedidos_material.route('/pedidos-material/visualizar/<int:pedido_id>')
def visualizar_pedido_material(pedido_id):
    """Rota para visualizar um pedido de material"""
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    itens_especificos = []
    itens_barra = []
    for item in pedido.itens:
        if item.material and item.material.especifico:
            itens_especificos.append(item)
        else:
            itens_barra.append(item)

    material_item_map = _build_material_item_map(pedido)

    return render_template('pedidos_material/visualizar.html', pedido=pedido, itens_especificos=itens_especificos, itens_barra=itens_barra, material_item_map=material_item_map)


@pedidos_material.route('/pedidos-material/numero/<string:numero>')
def visualizar_pedido_material_por_numero(numero):
    """Atalho: localizar PedidoMaterial pelo número (PM-xxxxx) e redirecionar para a visualização."""
    pedido = PedidoMaterial.query.filter_by(numero=numero).first_or_404()
    return redirect(url_for('pedidos_material.visualizar_pedido_material', pedido_id=pedido.id))


@pedidos_material.route('/pedidos-material/atualizar/<int:pedido_id>', methods=['POST'])
def atualizar_pedido_material(pedido_id):
    """Atualiza manualmente as quantidades/comprimentos dos itens de um pedido de material"""
    pedido = PedidoMaterial.query.get_or_404(pedido_id)

    itens = ItemPedidoMaterial.query.filter_by(pedido_material_id=pedido.id).all()
    for item in itens:
        material = item.material
        if material and material.especifico:
            campo = f"qtd_{item.id}"
            if campo in request.form:
                try:
                    qtd = int(request.form.get(campo) or 0)
                    item.quantidade = max(qtd, 0)
                except ValueError:
                    pass
        else:
            campo = f"m_{item.id}"
            if campo in request.form:
                try:
                    metros = float((request.form.get(campo) or '0').replace(',', '.'))
                    item.comprimento = max(metros, 0) * 1000.0
                except ValueError:
                    pass

    db.session.commit()
    flash('Pedido de material atualizado.', 'success')
    return redirect(url_for('pedidos_material.visualizar_pedido_material', pedido_id=pedido.id))

@pedidos_material.route('/pedidos-material/imprimir/<int:pedido_id>')
def imprimir_pedido_material(pedido_id):
    """Rota para imprimir um pedido de material"""
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    material_item_map = _build_material_item_map(pedido)
    return render_template('pedidos_material/imprimir.html', pedido=pedido, Material=Material, material_item_map=material_item_map)


@pedidos_material.route('/pedidos-material/comparativo/<int:pedido_id>')
def comparar_fornecedores(pedido_id):
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMaterial.query.filter_by(pedido_material_id=pedido.id).all()

    cotacao_itens = CotacaoItemPedidoMaterial.query.join(
        CotacaoPedidoMaterial,
        CotacaoItemPedidoMaterial.cotacao_id == CotacaoPedidoMaterial.id
    ).filter(CotacaoPedidoMaterial.pedido_material_id == pedido.id).all()

    cotacao_itens_map = {}
    for ci in cotacao_itens:
        cotacao_itens_map[f"{ci.cotacao_id}_{ci.item_pedido_material_id}"] = ci

    # Métricas por item: melhor preço (com IPI), melhor prazo de entrega (menor) e melhor prazo de pagamento (maior)
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

    material_item_map = _build_material_item_map(pedido)

    return render_template(
        'pedidos_material/comparativo.html',
        pedido=pedido,
        cotacoes=cotacoes,
        cotacao_itens_map=cotacao_itens_map,
        melhores=melhores,
        material_item_map=material_item_map,
    )


@pedidos_material.route('/pedidos-material/comparativo/<int:pedido_id>/fornecedor', methods=['POST'])
def adicionar_fornecedor_comparativo(pedido_id):
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    nome = (request.form.get('nome_fornecedor') or '').strip()
    if not nome:
        flash('Informe o nome do fornecedor.', 'warning')
        return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))

    fornecedor = Fornecedor.query.filter_by(nome=nome).first()
    if not fornecedor:
        fornecedor = Fornecedor(nome=nome)
        db.session.add(fornecedor)
        db.session.flush()

    cotacao = CotacaoPedidoMaterial.query.filter_by(pedido_material_id=pedido.id, fornecedor_id=fornecedor.id).first()
    if cotacao:
        flash('Este fornecedor já existe neste comparativo.', 'info')
        return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))

    cotacao = CotacaoPedidoMaterial(pedido_material_id=pedido.id, fornecedor_id=fornecedor.id)
    db.session.add(cotacao)
    db.session.commit()

    flash('Fornecedor adicionado ao comparativo.', 'success')
    return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_material.route('/pedidos-material/comparativo/<int:pedido_id>/salvar', methods=['POST'])
def salvar_comparativo(pedido_id):
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMaterial.query.filter_by(pedido_material_id=pedido.id).all()

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

            ci = CotacaoItemPedidoMaterial.query.filter_by(cotacao_id=c.id, item_pedido_material_id=item.id).first()
            if not ci:
                ci = CotacaoItemPedidoMaterial(cotacao_id=c.id, item_pedido_material_id=item.id)
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
    return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_material.route('/pedidos-material/comparativo/<int:pedido_id>/sugerir-rateio', methods=['POST'])
def sugerir_rateio(pedido_id):
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMaterial.query.filter_by(pedido_material_id=pedido.id).all()
    if not cotacoes:
        flash('Adicione fornecedores antes de sugerir o rateio.', 'warning')
        return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))

    # Carregar/garantir CotacaoItemPedidoMaterial para todos
    for item in pedido.itens:
        melhor_ci = None
        melhor_val = None

        for c in cotacoes:
            ci = CotacaoItemPedidoMaterial.query.filter_by(cotacao_id=c.id, item_pedido_material_id=item.id).first()
            if not ci:
                ci = CotacaoItemPedidoMaterial(cotacao_id=c.id, item_pedido_material_id=item.id)
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

        # Zerando rateio nos outros fornecedores e preenchendo no melhor
        for c in cotacoes:
            ci = CotacaoItemPedidoMaterial.query.filter_by(cotacao_id=c.id, item_pedido_material_id=item.id).first()
            if not ci:
                continue
            ci.quantidade_escolhida = 0
            ci.metros_escolhidos = 0

        if melhor_ci:
            if item.material and item.material.especifico:
                melhor_ci.quantidade_escolhida = int(item.quantidade or 0)
                melhor_ci.metros_escolhidos = 0
            else:
                melhor_ci.metros_escolhidos = float((item.comprimento or 0) / 1000.0)
                melhor_ci.quantidade_escolhida = 0

    db.session.commit()
    flash('Rateio sugerido com base no melhor preço (com IPI).', 'success')
    return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_material.route('/pedidos-material/comparativo/<int:pedido_id>/sugerir-rateio-entrega', methods=['POST'])
def sugerir_rateio_entrega(pedido_id):
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMaterial.query.filter_by(pedido_material_id=pedido.id).all()
    if not cotacoes:
        flash('Adicione fornecedores antes de sugerir o rateio.', 'warning')
        return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))

    for item in pedido.itens:
        melhor_ci = None
        melhor_val = None

        for c in cotacoes:
            ci = CotacaoItemPedidoMaterial.query.filter_by(cotacao_id=c.id, item_pedido_material_id=item.id).first()
            if not ci:
                continue
            if ci.prazo_entrega_dias is None:
                continue
            if melhor_val is None or ci.prazo_entrega_dias < melhor_val:
                melhor_val = ci.prazo_entrega_dias
                melhor_ci = ci

        for c in cotacoes:
            ci = CotacaoItemPedidoMaterial.query.filter_by(cotacao_id=c.id, item_pedido_material_id=item.id).first()
            if not ci:
                continue
            ci.quantidade_escolhida = 0
            ci.metros_escolhidos = 0

        if melhor_ci:
            if item.material and item.material.especifico:
                melhor_ci.quantidade_escolhida = int(item.quantidade or 0)
                melhor_ci.metros_escolhidos = 0
            else:
                melhor_ci.metros_escolhidos = float((item.comprimento or 0) / 1000.0)
                melhor_ci.quantidade_escolhida = 0

    db.session.commit()
    flash('Rateio sugerido com base no melhor prazo de entrega.', 'success')
    return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))


@pedidos_material.route('/pedidos-material/comparativo/<int:pedido_id>/sugerir-rateio-pagamento', methods=['POST'])
def sugerir_rateio_pagamento(pedido_id):
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    cotacoes = CotacaoPedidoMaterial.query.filter_by(pedido_material_id=pedido.id).all()
    if not cotacoes:
        flash('Adicione fornecedores antes de sugerir o rateio.', 'warning')
        return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))

    # Melhor prazo de pagamento = maior quantidade de dias
    for item in pedido.itens:
        melhor_ci = None
        melhor_val = None

        for c in cotacoes:
            ci = CotacaoItemPedidoMaterial.query.filter_by(cotacao_id=c.id, item_pedido_material_id=item.id).first()
            if not ci:
                continue
            if ci.prazo_pagamento_dias is None:
                continue
            if melhor_val is None or ci.prazo_pagamento_dias > melhor_val:
                melhor_val = ci.prazo_pagamento_dias
                melhor_ci = ci

        for c in cotacoes:
            ci = CotacaoItemPedidoMaterial.query.filter_by(cotacao_id=c.id, item_pedido_material_id=item.id).first()
            if not ci:
                continue
            ci.quantidade_escolhida = 0
            ci.metros_escolhidos = 0

        if melhor_ci:
            if item.material and item.material.especifico:
                melhor_ci.quantidade_escolhida = int(item.quantidade or 0)
                melhor_ci.metros_escolhidos = 0
            else:
                melhor_ci.metros_escolhidos = float((item.comprimento or 0) / 1000.0)
                melhor_ci.quantidade_escolhida = 0

    db.session.commit()
    flash('Rateio sugerido com base no melhor prazo de pagamento.', 'success')
    return redirect(url_for('pedidos_material.comparar_fornecedores', pedido_id=pedido.id))
