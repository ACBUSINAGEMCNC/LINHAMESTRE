from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, EstoquePecas, Item, MovimentacaoEstoquePecas
from utils import validate_form_data
from datetime import datetime

estoque_pecas = Blueprint('estoque_pecas', __name__)

@estoque_pecas.route('/estoque-pecas')
def index():
    """Rota para a página principal do estoque de peças"""
    # Organizar estoque por prateleira
    estoque = EstoquePecas.query.order_by(EstoquePecas.prateleira, EstoquePecas.posicao).all()
    return render_template('estoque_pecas/index.html', estoque=estoque)

@estoque_pecas.route('/estoque-pecas/entrada', methods=['GET', 'POST'])
def entrada():
    """Rota para registrar entrada de peças no estoque"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['item_id', 'quantidade'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            itens = Item.query.all()
            return render_template('estoque_pecas/entrada.html', itens=itens)
        
        item_id = request.form['item_id']
        
        # Validar quantidade
        try:
            quantidade = int(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                itens = Item.query.all()
                return render_template('estoque_pecas/entrada.html', itens=itens)
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            itens = Item.query.all()
            return render_template('estoque_pecas/entrada.html', itens=itens)
        
        referencia = request.form.get('referencia', '')
        observacao = request.form.get('observacao', '')
        prateleira = request.form.get('prateleira', '')
        posicao = request.form.get('posicao', '')
        
        # Verificar se já existe um registro para este item
        estoque_existente = EstoquePecas.query.filter_by(item_id=item_id).first()
        
        if estoque_existente:
            # Atualizar estoque existente
            estoque_existente.quantidade += quantidade
            
            # Atualizar prateleira e posição se fornecidas
            if prateleira:
                estoque_existente.prateleira = prateleira
            if posicao:
                estoque_existente.posicao = posicao
            
            # Registrar movimentação
            movimentacao = MovimentacaoEstoquePecas(
                estoque_pecas_id=estoque_existente.id,
                tipo='entrada',
                quantidade=quantidade,
                data=datetime.now().date(),
                referencia=referencia,
                observacao=observacao
            )
            
            db.session.add(movimentacao)
        else:
            # Criar novo registro de estoque
            novo_estoque = EstoquePecas(
                item_id=item_id,
                quantidade=quantidade,
                data_entrada=datetime.now().date(),
                prateleira=prateleira,
                posicao=posicao,
                observacao=observacao
            )
            
            db.session.add(novo_estoque)
            db.session.flush()  # Para obter o ID do novo registro
            
            # Registrar movimentação
            movimentacao = MovimentacaoEstoquePecas(
                estoque_pecas_id=novo_estoque.id,
                tipo='entrada',
                quantidade=quantidade,
                data=datetime.now().date(),
                referencia=referencia,
                observacao=observacao
            )
            
            db.session.add(movimentacao)
        
        db.session.commit()
        flash('Entrada de peças registrada com sucesso!', 'success')
        return redirect(url_for('estoque_pecas.index'))
    
    itens = Item.query.all()
    return render_template('estoque_pecas/entrada.html', itens=itens)

@estoque_pecas.route('/estoque-pecas/saida', methods=['GET', 'POST'])
def saida():
    """Rota para registrar saída de peças do estoque"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['estoque_id', 'quantidade'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            estoque = EstoquePecas.query.order_by(EstoquePecas.prateleira, EstoquePecas.posicao).all()
            return render_template('estoque_pecas/saida.html', estoque=estoque)
        
        estoque_id = request.form['estoque_id']
        
        # Validar quantidade
        try:
            quantidade = int(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                estoque = EstoquePecas.query.order_by(EstoquePecas.prateleira, EstoquePecas.posicao).all()
                return render_template('estoque_pecas/saida.html', estoque=estoque)
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            estoque = EstoquePecas.query.order_by(EstoquePecas.prateleira, EstoquePecas.posicao).all()
            return render_template('estoque_pecas/saida.html', estoque=estoque)
        
        referencia = request.form.get('referencia', '')
        observacao = request.form.get('observacao', '')
        
        # Buscar registro de estoque
        estoque_item = EstoquePecas.query.get_or_404(estoque_id)
        
        # Verificar se há quantidade suficiente
        if estoque_item.quantidade < quantidade:
            flash('Quantidade insuficiente em estoque!', 'danger')
            estoque = EstoquePecas.query.order_by(EstoquePecas.prateleira, EstoquePecas.posicao).all()
            return render_template('estoque_pecas/saida.html', estoque=estoque)
        
        # Atualizar estoque
        estoque_item.quantidade -= quantidade
        
        # Registrar movimentação
        movimentacao = MovimentacaoEstoquePecas(
            estoque_pecas_id=estoque_item.id,
            tipo='saida',
            quantidade=quantidade,
            data=datetime.now().date(),
            referencia=referencia,
            observacao=observacao
        )
        
        db.session.add(movimentacao)
        db.session.commit()
        
        flash('Saída de peças registrada com sucesso!', 'success')
        return redirect(url_for('estoque_pecas.index'))
    
    estoque = EstoquePecas.query.order_by(EstoquePecas.prateleira, EstoquePecas.posicao).all()
    return render_template('estoque_pecas/saida.html', estoque=estoque)

@estoque_pecas.route('/estoque-pecas/historico/<int:estoque_id>')
def historico(estoque_id):
    """Rota para visualizar o histórico de movimentações de um item do estoque"""
    estoque_item = EstoquePecas.query.get_or_404(estoque_id)
    movimentacoes = MovimentacaoEstoquePecas.query.filter_by(estoque_pecas_id=estoque_id).order_by(MovimentacaoEstoquePecas.data.desc()).all()
    
    return render_template('estoque_pecas/historico.html', estoque=estoque_item, movimentacoes=movimentacoes)

@estoque_pecas.route('/estoque-pecas/atualizar-localizacao/<int:estoque_id>', methods=['POST'])
def atualizar_localizacao(estoque_id):
    """Rota para atualizar a localização (prateleira e posição) de um item no estoque"""
    estoque_item = EstoquePecas.query.get_or_404(estoque_id)
    
    if request.method == 'POST':
        prateleira = request.form.get('prateleira', '')
        posicao = request.form.get('posicao', '')
        
        estoque_item.prateleira = prateleira
        estoque_item.posicao = posicao
        
        db.session.commit()
        flash('Localização atualizada com sucesso!', 'success')
    
    return redirect(url_for('estoque_pecas.index'))

@estoque_pecas.route('/estoque-pecas/movimentacao-rapida/<int:estoque_id>/<string:tipo>', methods=['POST'])
def movimentacao_rapida(estoque_id, tipo):
    """Rota para movimentação rápida (entrada ou saída) de itens no estoque"""
    estoque_item = EstoquePecas.query.get_or_404(estoque_id)
    
    if request.method == 'POST':
        try:
            quantidade = int(request.form.get('quantidade', 1))
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('estoque_pecas.index'))
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            return redirect(url_for('estoque_pecas.index'))
        
        referencia = request.form.get('referencia', '')
        observacao = request.form.get('observacao', 'Movimentação rápida')
        
        if tipo == 'entrada':
            estoque_item.quantidade += quantidade
        elif tipo == 'saida':
            if estoque_item.quantidade < quantidade:
                flash('Quantidade insuficiente em estoque!', 'danger')
                return redirect(url_for('estoque_pecas.index'))
            estoque_item.quantidade -= quantidade
        else:
            flash('Tipo de movimentação inválido!', 'danger')
            return redirect(url_for('estoque_pecas.index'))
        
        # Registrar movimentação
        movimentacao = MovimentacaoEstoquePecas(
            estoque_pecas_id=estoque_item.id,
            tipo=tipo,
            quantidade=quantidade,
            data=datetime.now().date(),
            referencia=referencia,
            observacao=observacao
        )
        
        db.session.add(movimentacao)
        db.session.commit()
        
        flash(f'Movimentação de {quantidade} item(ns) registrada com sucesso!', 'success')
    
    return redirect(url_for('estoque_pecas.index'))
