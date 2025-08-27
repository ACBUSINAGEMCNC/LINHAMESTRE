from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Trabalho, Maquina, Castanha, GabaritoCentroUsinagem, GabaritoRosca
from utils import validate_form_data, save_uploaded_file, generate_next_code
import os
import uuid
from datetime import datetime

trabalhos = Blueprint('trabalhos', __name__)

@trabalhos.route('/trabalhos')
def listar_trabalhos():
    """Rota para listar todos os trabalhos"""
    trabalhos = Trabalho.query.all()
    maquinas = Maquina.query.all()
    castanhas = Castanha.query.all()
    gabaritos_centro = GabaritoCentroUsinagem.query.all()
    gabaritos_rosca = GabaritoRosca.query.all()
    
    return render_template('trabalhos/listar.html', 
                           trabalhos=trabalhos,
                           maquinas=maquinas,
                           castanhas=castanhas,
                           gabaritos_centro=gabaritos_centro,
                           gabaritos_rosca=gabaritos_rosca)

@trabalhos.route('/trabalhos/tipos')
def listar_tipos_trabalho():
    """Rota para listar todos os tipos de trabalho"""
    trabalhos = Trabalho.query.all()
    
    return render_template('trabalhos/tipos_trabalho.html', trabalhos=trabalhos)

@trabalhos.route('/trabalhos/tipos/novo', methods=['GET', 'POST'])
def novo_tipo_trabalho():
    """Rota para cadastrar um novo tipo de trabalho"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/novo_tipo.html')
        
        nome = request.form['nome']
        categoria = request.form.get('categoria', '')
        
        # Verificar se já existe um trabalho com o mesmo nome
        trabalho_existente = Trabalho.query.filter_by(nome=nome).first()
        if trabalho_existente:
            flash('Já existe um tipo de trabalho com este nome!', 'danger')
            return render_template('trabalhos/novo_tipo.html')
        
        trabalho = Trabalho(nome=nome, categoria=categoria)
        db.session.add(trabalho)
        db.session.commit()
        flash('Tipo de trabalho cadastrado com sucesso!', 'success')
        return redirect(url_for('trabalhos.listar_tipos_trabalho'))
    
    return render_template('trabalhos/novo_tipo.html')

@trabalhos.route('/trabalhos/tipos/editar/<int:trabalho_id>', methods=['GET', 'POST'])
def editar_tipo_trabalho(trabalho_id):
    """Rota para editar um tipo de trabalho existente"""
    trabalho = Trabalho.query.get_or_404(trabalho_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/editar_tipo.html', trabalho=trabalho)
        
        nome = request.form['nome']
        categoria = request.form.get('categoria', '')
        
        # Verificar se já existe outro trabalho com o mesmo nome (exceto o atual)
        trabalho_existente = Trabalho.query.filter(Trabalho.nome == nome, Trabalho.id != trabalho_id).first()
        if trabalho_existente:
            flash('Já existe um tipo de trabalho com este nome!', 'danger')
            return render_template('trabalhos/editar_tipo.html', trabalho=trabalho)
        
        trabalho.nome = nome
        trabalho.categoria = categoria
        
        db.session.commit()
        flash('Tipo de trabalho atualizado com sucesso!', 'success')
        return redirect(url_for('trabalhos.listar_tipos_trabalho'))
    
    return render_template('trabalhos/editar_tipo.html', trabalho=trabalho)

@trabalhos.route('/trabalhos/novo', methods=['GET', 'POST'])
def novo_trabalho():
    """Rota para cadastrar um novo trabalho"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/novo.html')
        
        nome = request.form['nome']
        categoria = request.form.get('categoria', '')
        
        # Verificar se já existe um trabalho com o mesmo nome
        trabalho_existente = Trabalho.query.filter_by(nome=nome).first()
        if trabalho_existente:
            flash('Já existe um trabalho com este nome!', 'danger')
            return render_template('trabalhos/novo.html')
        
        trabalho = Trabalho(nome=nome, categoria=categoria)
        db.session.add(trabalho)
        db.session.commit()
        flash('Trabalho cadastrado com sucesso!', 'success')
        return redirect(url_for('trabalhos.listar_trabalhos'))
    
    return render_template('trabalhos/novo.html')

@trabalhos.route('/trabalhos/editar/<int:trabalho_id>', methods=['GET', 'POST'])
def editar_trabalho(trabalho_id):
    """Rota para editar um trabalho existente"""
    trabalho = Trabalho.query.get_or_404(trabalho_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/editar.html', trabalho=trabalho)
        
        nome = request.form['nome']
        categoria = request.form.get('categoria', '')
        
        # Verificar se já existe outro trabalho com o mesmo nome (exceto o atual)
        trabalho_existente = Trabalho.query.filter(Trabalho.nome == nome, Trabalho.id != trabalho_id).first()
        if trabalho_existente:
            flash('Já existe um trabalho com este nome!', 'danger')
            return render_template('trabalhos/editar.html', trabalho=trabalho)
        
        trabalho.nome = nome
        trabalho.categoria = categoria
        
        db.session.commit()
        flash('Trabalho atualizado com sucesso!', 'success')
        return redirect(url_for('trabalhos.listar_trabalhos'))
    
    return render_template('trabalhos/editar.html', trabalho=trabalho)
