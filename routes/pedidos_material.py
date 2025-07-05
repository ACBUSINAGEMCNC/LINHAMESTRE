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
    return render_template('pedidos_material/visualizar.html', pedido=pedido)

@pedidos_material.route('/pedidos-material/imprimir/<int:pedido_id>')
def imprimir_pedido_material(pedido_id):
    """Rota para imprimir um pedido de material"""
    pedido = PedidoMaterial.query.get_or_404(pedido_id)
    return render_template('pedidos_material/imprimir.html', pedido=pedido, Material=Material)
