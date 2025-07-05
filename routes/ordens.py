from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from models import db, OrdemServico, Pedido, PedidoOrdemServico, Item
from utils import validate_form_data, generate_next_code
from datetime import datetime
from sqlalchemy.exc import IntegrityError

ordens = Blueprint('ordens', __name__)

@ordens.route('/ordens-servico')
def listar_ordens_servico():
    """Rota para listar todas as ordens de serviço"""
    ordens = OrdemServico.query.all()
    return render_template('ordens/listar.html', ordens=ordens)

@ordens.route('/ordens-servico/nova', methods=['GET', 'POST'])
def nova_ordem_servico():
    """Rota para criar uma nova ordem de serviço"""
    if request.method == 'POST':
        # Validação de dados
        pedidos_ids = request.form.getlist('pedidos')
        if not pedidos_ids:
            flash('Selecione pelo menos um pedido para gerar a ordem de serviço', 'danger')
            pedidos = Pedido.query.filter(Pedido.numero_oc == None).all()
            return render_template('ordens/nova.html', pedidos=pedidos)
        
        # Gerar número da OS automaticamente com tentativas para garantir unicidade
        max_tentativas = 5
        for tentativa in range(max_tentativas):
            try:
                novo_numero = generate_next_code(OrdemServico, "OS", "numero")
                
                # Verificar explicitamente se o número já existe
                if OrdemServico.query.filter_by(numero=novo_numero).first():
                    continue  # Se já existe, tenta novamente
                
                ordem = OrdemServico(numero=novo_numero)
                db.session.add(ordem)
                db.session.flush()  # Flush para obter o ID sem commit
                
                # Adicionar pedidos à OS
                for pedido_id in pedidos_ids:
                    pedido_os = PedidoOrdemServico(
                        pedido_id=pedido_id,
                        ordem_servico_id=ordem.id
                    )
                    db.session.add(pedido_os)
                    
                    # Atualizar número da OC no pedido
                    pedido = Pedido.query.get(pedido_id)
                    pedido.numero_oc = novo_numero
                
                db.session.commit()
                flash('Ordem de Serviço criada com sucesso!', 'success')
                return redirect(url_for('ordens.listar_ordens_servico'))
                
            except IntegrityError as e:
                db.session.rollback()
                if tentativa == max_tentativas - 1:
                    flash(f'Erro ao gerar ordem de serviço: {str(e)}', 'danger')
                    pedidos = Pedido.query.filter(Pedido.numero_oc == None).all()
                    return render_template('ordens/nova.html', pedidos=pedidos)
    
    pedidos = Pedido.query.filter(Pedido.numero_oc == None).all()
    return render_template('ordens/nova.html', pedidos=pedidos)

@ordens.route('/ordens-servico/imprimir/<int:ordem_id>')
def imprimir_ordem_servico(ordem_id):
    """Rota para imprimir uma ordem de serviço"""
    ordem = OrdemServico.query.get_or_404(ordem_id)
    return render_template('ordens/imprimir.html', ordem=ordem, Item=Item)

@ordens.route('/ordens-servico/imprimir-desenho/<int:ordem_id>')
def imprimir_desenho(ordem_id):
    """Rota para imprimir desenhos técnicos de uma ordem de serviço"""
    ordem = OrdemServico.query.get_or_404(ordem_id)
    return render_template('ordens/imprimir_desenho.html', ordem=ordem)
