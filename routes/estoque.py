from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from models import db, Usuario, Estoque, Material, MovimentacaoEstoque, OrdemServico
from utils import validate_form_data
from datetime import datetime

estoque = Blueprint('estoque', __name__)

@estoque.before_request
def verificar_permissao_estoque():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('auth.login'))

    if usuario.nivel_acesso == 'admin':
        return

    if not usuario.acesso_estoque:
        flash('Você não tem permissão para acessar a área de Estoque', 'danger')
        return redirect(url_for('main.index'))

@estoque.route('/estoque')
def index():
    """Rota para a página de seleção de tipo de estoque"""
    return render_template('estoque/selecao.html')

@estoque.route('/estoque-selecao')
def selecao():
    """Rota alternativa para a página de seleção de tipo de estoque"""
    return render_template('estoque/selecao.html')

@estoque.route('/estoque-materiais')
def materiais():
    """Rota para a página principal do estoque de materiais"""
    estoques = Estoque.query.all()
    return render_template('estoque/index.html', estoques=estoques)

@estoque.route('/estoque/entrada', methods=['GET', 'POST'])
def entrada_estoque():
    """Rota para registrar entrada de material no estoque"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['material_id', 'quantidade', 'referencia'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            materiais = Material.query.all()
            return render_template('estoque/entrada.html', materiais=materiais)
        
        material_id = request.form['material_id']
        referencia = request.form['referencia']
        observacao = request.form.get('observacao', '')
        
        # Validar quantidade
        try:
            quantidade = int(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                materiais = Material.query.all()
                return render_template('estoque/entrada.html', materiais=materiais)
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            materiais = Material.query.all()
            return render_template('estoque/entrada.html', materiais=materiais)
        
        # Validar comprimento se fornecido
        comprimento = None
        if 'comprimento' in request.form and request.form['comprimento']:
            try:
                comprimento = float(request.form['comprimento'])
                if comprimento <= 0:
                    flash('O comprimento deve ser maior que zero', 'danger')
                    materiais = Material.query.all()
                    return render_template('estoque/entrada.html', materiais=materiais)
            except ValueError:
                flash('O comprimento deve ser um número válido', 'danger')
                materiais = Material.query.all()
                return render_template('estoque/entrada.html', materiais=materiais)
        
        # Verificar se já existe estoque para este material
        estoque_item = Estoque.query.filter_by(material_id=material_id).first()
        if not estoque_item:
            estoque_item = Estoque(material_id=material_id, quantidade=0, comprimento_total=0)
            db.session.add(estoque_item)
            db.session.commit()
        
        # Registrar movimentação
        movimentacao = MovimentacaoEstoque(
            estoque_id=estoque_item.id,
            tipo='entrada',
            quantidade=quantidade,
            comprimento=comprimento,
            referencia=referencia,
            observacao=observacao
        )
        db.session.add(movimentacao)
        
        # Atualizar saldo do estoque
        estoque_item.quantidade += quantidade
        if comprimento:
            estoque_item.comprimento_total += comprimento * quantidade
        
        db.session.commit()
        flash('Entrada de material registrada com sucesso!', 'success')
        return redirect(url_for('estoque.materiais'))
    
    materiais = Material.query.all()
    return render_template('estoque/entrada.html', materiais=materiais)

@estoque.route('/estoque/saida', methods=['GET', 'POST'])
def saida_estoque():
    """Rota para registrar saída de material do estoque"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['estoque_id', 'quantidade', 'referencia'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            estoque_items = Estoque.query.all()
            ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
            return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)
        
        estoque_id = request.form['estoque_id']
        referencia = request.form['referencia']
        observacao = request.form.get('observacao', '')
        
        # Validar quantidade
        try:
            quantidade = int(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                estoque_items = Estoque.query.all()
                ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
                return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            estoque_items = Estoque.query.all()
            ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
            return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)
        
        # Validar comprimento se fornecido
        comprimento = None
        if 'comprimento' in request.form and request.form['comprimento']:
            try:
                comprimento = float(request.form['comprimento'])
                if comprimento <= 0:
                    flash('O comprimento deve ser maior que zero', 'danger')
                    estoque_items = Estoque.query.all()
                    ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
                    return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)
            except ValueError:
                flash('O comprimento deve ser um número válido', 'danger')
                estoque_items = Estoque.query.all()
                ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
                return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)
        
        # Verificar estoque disponível
        estoque_item = Estoque.query.get_or_404(estoque_id)
        if estoque_item.quantidade < quantidade:
            flash('Quantidade insuficiente em estoque', 'danger')
            estoque_items = Estoque.query.all()
            ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
            return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)
        
        if comprimento and estoque_item.comprimento_total < comprimento * quantidade:
            flash('Comprimento insuficiente em estoque', 'danger')
            estoque_items = Estoque.query.all()
            ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
            return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)
        
        # Registrar movimentação
        movimentacao = MovimentacaoEstoque(
            estoque_id=estoque_item.id,
            tipo='saida',
            quantidade=quantidade,
            comprimento=comprimento,
            referencia=referencia,
            observacao=observacao
        )
        db.session.add(movimentacao)
        
        # Atualizar saldo do estoque
        estoque_item.quantidade -= quantidade
        if comprimento:
            estoque_item.comprimento_total -= comprimento * quantidade
        
        db.session.commit()
        flash('Saída de material registrada com sucesso!', 'success')
        return redirect(url_for('estoque.materiais'))
    
    estoque_items = Estoque.query.all()
    ordens_servico = OrdemServico.query.filter(OrdemServico.status != 'Finalizado').all()
    return render_template('estoque/saida.html', estoque=estoque_items, ordens_servico=ordens_servico)

@estoque.route('/estoque/historico/<int:estoque_id>')
def historico_estoque(estoque_id):
    """Rota para visualizar o histórico de movimentações de um item do estoque"""
    estoque_item = Estoque.query.get_or_404(estoque_id)
    movimentacoes = MovimentacaoEstoque.query.filter_by(estoque_id=estoque_id).order_by(MovimentacaoEstoque.data.desc()).all()
    return render_template('estoque/historico.html', estoque=estoque_item, movimentacoes=movimentacoes)
