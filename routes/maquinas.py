from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Maquina
from utils import validate_form_data, save_uploaded_file, generate_next_code

maquinas = Blueprint('maquinas', __name__)

@maquinas.route('/trabalhos/maquinas')
def listar_maquinas():
    """Rota para listar todas as máquinas"""
    maquinas = Maquina.query.all()
    return render_template('trabalhos/maquinas/listar.html', maquinas=maquinas)

@maquinas.route('/trabalhos/maquinas/nova', methods=['GET', 'POST'])
def nova_maquina():
    """Rota para cadastrar uma nova máquina"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome', 'categoria_trabalho'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/maquinas/nova.html')
        
        nome = request.form['nome']
        categoria_trabalho = request.form['categoria_trabalho']
        
        # Verificar se já existe uma máquina com o mesmo nome
        maquina_existente = Maquina.query.filter_by(nome=nome).first()
        if maquina_existente:
            flash('Já existe uma máquina com este nome!', 'danger')
            return render_template('trabalhos/maquinas/nova.html')
        
        # Gerar código automático
        codigo = generate_next_code(Maquina, 'MAQ', 'codigo')
        
        # Processar imagem se enviada
        imagem = None
        if 'imagem' in request.files and request.files['imagem'].filename:
            imagem = save_uploaded_file(request.files['imagem'], 'maquinas')
        
        maquina = Maquina(nome=nome, categoria_trabalho=categoria_trabalho, codigo=codigo, imagem=imagem)
        db.session.add(maquina)
        db.session.commit()
        flash('Máquina cadastrada com sucesso!', 'success')
        return redirect(url_for('maquinas.listar_maquinas'))
    
    return render_template('trabalhos/maquinas/nova.html')

@maquinas.route('/trabalhos/maquinas/editar/<int:maquina_id>', methods=['GET', 'POST'])
def editar_maquina(maquina_id):
    """Rota para editar uma máquina existente"""
    maquina = Maquina.query.get_or_404(maquina_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome', 'categoria_trabalho'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/maquinas/editar.html', maquina=maquina)
        
        nome = request.form['nome']
        categoria_trabalho = request.form['categoria_trabalho']
        
        # Verificar se já existe outra máquina com o mesmo nome (exceto a atual)
        maquina_existente = Maquina.query.filter(Maquina.nome == nome, Maquina.id != maquina_id).first()
        if maquina_existente:
            flash('Já existe uma máquina com este nome!', 'danger')
            return render_template('trabalhos/maquinas/editar.html', maquina=maquina)
        
        # Processar imagem se enviada
        if 'imagem' in request.files and request.files['imagem'].filename:
            maquina.imagem = save_uploaded_file(request.files['imagem'], 'maquinas')
        
        maquina.nome = nome
        maquina.categoria_trabalho = categoria_trabalho
        
        db.session.commit()
        flash('Máquina atualizada com sucesso!', 'success')
        return redirect(url_for('maquinas.listar_maquinas'))
    
    return render_template('trabalhos/maquinas/editar.html', maquina=maquina)
