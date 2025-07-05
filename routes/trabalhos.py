from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Trabalho
from utils import validate_form_data

trabalhos = Blueprint('trabalhos', __name__)

@trabalhos.route('/trabalhos')
def listar_trabalhos():
    """Rota para listar todos os trabalhos"""
    trabalhos = Trabalho.query.all()
    return render_template('trabalhos/listar.html', trabalhos=trabalhos)

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
