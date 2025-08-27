from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Castanha, Maquina
from utils import validate_form_data, save_uploaded_file, generate_next_code

castanhas = Blueprint('castanhas', __name__)

@castanhas.route('/trabalhos/castanhas')
def listar_castanhas():
    """Rota para listar todas as castanhas"""
    castanhas = Castanha.query.all()
    return render_template('trabalhos/castanhas/listar.html', castanhas=castanhas)

@castanhas.route('/trabalhos/castanhas/nova', methods=['GET', 'POST'])
def nova_castanha():
    """Rota para cadastrar uma nova castanha"""
    if request.method == 'POST':
        # Validação de dados
        errors = []
        if not request.form.get('castanha_livre') and not request.form.get('diametro'):
            errors.append('O campo diâmetro é obrigatório para castanhas não-livres.')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/castanhas/nova.html', maquinas=Maquina.query.all())
        
        # Gerar código automático
        codigo = generate_next_code(Castanha, 'CAS', 'codigo')
        
        # Processar dados do formulário
        castanha_livre = 'castanha_livre' in request.form
        diametro = float(request.form.get('diametro', 0)) if request.form.get('diametro') else None
        comprimento = float(request.form.get('comprimento', 0)) if request.form.get('comprimento') else None
        maquina_id = int(request.form['maquina_id']) if request.form.get('maquina_id') else None
        local_armazenamento = request.form.get('local_armazenamento', '')
        
        # Processar imagem se enviada
        imagem = None
        if 'imagem' in request.files and request.files['imagem'].filename:
            imagem = save_uploaded_file(request.files['imagem'], 'castanhas')
        
        castanha = Castanha(
            codigo=codigo,
            diametro=diametro,
            comprimento=comprimento,
            castanha_livre=castanha_livre,
            maquina_id=maquina_id,
            local_armazenamento=local_armazenamento,
            imagem=imagem
        )
        
        db.session.add(castanha)
        db.session.commit()
        flash('Castanha cadastrada com sucesso!', 'success')
        return redirect(url_for('castanhas.listar_castanhas'))
    
    return render_template('trabalhos/castanhas/nova.html', maquinas=Maquina.query.all())

@castanhas.route('/trabalhos/castanhas/editar/<int:castanha_id>', methods=['GET', 'POST'])
def editar_castanha(castanha_id):
    """Rota para editar uma castanha existente"""
    castanha = Castanha.query.get_or_404(castanha_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = []
        if not request.form.get('castanha_livre') and not request.form.get('diametro'):
            errors.append('O campo diâmetro é obrigatório para castanhas não-livres.')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/castanhas/editar.html', castanha=castanha, maquinas=Maquina.query.all())
        
        # Processar dados do formulário
        castanha.castanha_livre = 'castanha_livre' in request.form
        castanha.diametro = float(request.form.get('diametro', 0)) if request.form.get('diametro') else None
        castanha.comprimento = float(request.form.get('comprimento', 0)) if request.form.get('comprimento') else None
        castanha.maquina_id = int(request.form['maquina_id']) if request.form.get('maquina_id') else None
        castanha.local_armazenamento = request.form.get('local_armazenamento', '')
        
        # Processar imagem se enviada
        if 'imagem' in request.files and request.files['imagem'].filename:
            castanha.imagem = save_uploaded_file(request.files['imagem'], 'castanhas')
        
        db.session.commit()
        flash('Castanha atualizada com sucesso!', 'success')
        return redirect(url_for('castanhas.listar_castanhas'))
    
    return render_template('trabalhos/castanhas/editar.html', castanha=castanha, maquinas=Maquina.query.all())
