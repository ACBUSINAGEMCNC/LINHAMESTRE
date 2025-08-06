from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from models import db, Cliente, UnidadeEntrega
from utils import validate_form_data

clientes = Blueprint('clientes', __name__)

@clientes.route('/clientes')
def listar_clientes():
    """Rota para listar todos os clientes"""
    clientes = Cliente.query.all()
    return render_template('clientes/listar.html', clientes=clientes)

@clientes.route('/clientes/novo', methods=['GET', 'POST'])
def novo_cliente():
    """Rota para cadastrar um novo cliente"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('clientes/novo.html')
        
        nome = request.form['nome']
        
        # Verificar se já existe um cliente com o mesmo nome
        cliente_existente = Cliente.query.filter_by(nome=nome).first()
        if cliente_existente:
            flash('Já existe um cliente com este nome!', 'danger')
            return render_template('clientes/novo.html')
        
        cliente = Cliente(nome=nome)
        db.session.add(cliente)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes.listar_clientes'))
    
    return render_template('clientes/novo.html')

@clientes.route('/clientes/editar/<int:cliente_id>', methods=['GET', 'POST'])
def editar_cliente(cliente_id):
    """Rota para editar um cliente existente"""
    cliente = Cliente.query.get_or_404(cliente_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('clientes/editar.html', cliente=cliente)
        
        nome = request.form['nome']
        
        # Verificar se já existe outro cliente com o mesmo nome (exceto o atual)
        cliente_existente = Cliente.query.filter(Cliente.nome == nome, Cliente.id != cliente_id).first()
        if cliente_existente:
            flash('Já existe um cliente com este nome!', 'danger')
            return render_template('clientes/editar.html', cliente=cliente)
        
        cliente.nome = nome
        
        db.session.commit()
        flash('Cliente atualizado com sucesso!', 'success')
        return redirect(url_for('clientes.listar_clientes'))
    
    return render_template('clientes/editar.html', cliente=cliente)

@clientes.route('/clientes/<int:cliente_id>/unidades')
def listar_unidades(cliente_id):
    """Rota para listar unidades de entrega de um cliente"""
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template('unidades/listar.html', cliente=cliente)

@clientes.route('/clientes/<int:cliente_id>/unidades/nova', methods=['GET', 'POST'])
def nova_unidade(cliente_id):
    """Rota para cadastrar uma nova unidade de entrega para um cliente"""
    cliente = Cliente.query.get_or_404(cliente_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('unidades/nova.html', cliente=cliente)
        
        nome = request.form['nome']
        
        # Verificar se já existe uma unidade com o mesmo nome para este cliente
        unidade_existente = UnidadeEntrega.query.filter_by(nome=nome, cliente_id=cliente_id).first()
        if unidade_existente:
            flash('Já existe uma unidade com este nome para este cliente!', 'danger')
            return render_template('unidades/nova.html', cliente=cliente)
        
        unidade = UnidadeEntrega(nome=nome, cliente_id=cliente_id)
        db.session.add(unidade)
        db.session.commit()
        flash('Unidade cadastrada com sucesso!', 'success')
        return redirect(url_for('clientes.listar_unidades', cliente_id=cliente_id))
    
    return render_template('unidades/nova.html', cliente=cliente)

@clientes.route('/unidades/editar/<int:unidade_id>', methods=['GET', 'POST'])
def editar_unidade(unidade_id):
    """Rota para editar uma unidade de entrega existente"""
    unidade = UnidadeEntrega.query.get_or_404(unidade_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('unidades/editar.html', unidade=unidade)
        
        nome = request.form['nome']
        
        # Verificar se já existe outra unidade com o mesmo nome para o mesmo cliente (exceto a atual)
        unidade_existente = UnidadeEntrega.query.filter(
            UnidadeEntrega.nome == nome, 
            UnidadeEntrega.cliente_id == unidade.cliente_id,
            UnidadeEntrega.id != unidade_id
        ).first()
        
        if unidade_existente:
            flash('Já existe uma unidade com este nome para este cliente!', 'danger')
            return render_template('unidades/editar.html', unidade=unidade)
        
        unidade.nome = nome
        
        db.session.commit()
        flash('Unidade atualizada com sucesso!', 'success')
        return redirect(url_for('clientes.listar_unidades', cliente_id=unidade.cliente_id))
    
    return render_template('unidades/editar.html', unidade=unidade)

@clientes.route('/api/unidades/<int:cliente_id>')
def api_unidades(cliente_id):
    """API para obter unidades de entrega de um cliente"""
    unidades = UnidadeEntrega.query.filter_by(cliente_id=cliente_id).all()
    return jsonify([{'id': u.id, 'nome': u.nome} for u in unidades])
