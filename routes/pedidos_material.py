from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, PedidoMaterial, ItemPedidoMaterial, Material, Pedido
from utils import validate_form_data, generate_next_code, parse_json_field
from datetime import datetime
from sqlalchemy.exc import IntegrityError

pedidos_material = Blueprint('pedidos_material', __name__)

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

    return render_template('pedidos_material/visualizar.html', pedido=pedido, itens_especificos=itens_especificos, itens_barra=itens_barra)


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
    return render_template('pedidos_material/imprimir.html', pedido=pedido, Material=Material)
