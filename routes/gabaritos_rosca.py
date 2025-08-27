from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, GabaritoRosca
from utils import validate_form_data, save_uploaded_file, generate_next_code

gabaritos_rosca = Blueprint('gabaritos_rosca', __name__)

@gabaritos_rosca.route('/trabalhos/gabaritos-rosca')
def listar_gabaritos_rosca():
    """Rota para listar todos os gabaritos de rosca"""
    gabaritos = GabaritoRosca.query.all()
    return render_template('trabalhos/gabaritos-rosca/listar.html', gabaritos=gabaritos)

@gabaritos_rosca.route('/trabalhos/gabaritos-rosca/novo', methods=['GET', 'POST'])
def novo_gabarito_rosca():
    """Rota para cadastrar um novo gabarito de rosca"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['tipo_rosca', 'local_armazenamento'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/gabaritos-rosca/novo.html')
        
        tipo_rosca = request.form['tipo_rosca']
        local_armazenamento = request.form['local_armazenamento']
        
        # Verificar se já existe um gabarito com o mesmo tipo de rosca
        gabarito_existente = GabaritoRosca.query.filter_by(tipo_rosca=tipo_rosca).first()
        if gabarito_existente:
            flash('Já existe um gabarito para este tipo de rosca!', 'danger')
            return render_template('trabalhos/gabaritos-rosca/novo.html')
        
        # Gerar código automático
        codigo = generate_next_code(GabaritoRosca, 'GRO', 'codigo')
        
        # Processar imagem se enviada
        imagem = None
        if 'imagem' in request.files and request.files['imagem'].filename:
            imagem = save_uploaded_file(request.files['imagem'], 'gabaritos')
        
        gabarito = GabaritoRosca(
            codigo=codigo,
            tipo_rosca=tipo_rosca,
            local_armazenamento=local_armazenamento,
            imagem=imagem
        )
        
        db.session.add(gabarito)
        db.session.commit()
        flash('Gabarito de rosca cadastrado com sucesso!', 'success')
        return redirect(url_for('gabaritos_rosca.listar_gabaritos_rosca'))
    
    return render_template('trabalhos/gabaritos-rosca/novo.html')

@gabaritos_rosca.route('/trabalhos/gabaritos-rosca/editar/<int:gabarito_id>', methods=['GET', 'POST'])
def editar_gabarito_rosca(gabarito_id):
    """Rota para editar um gabarito de rosca existente"""
    gabarito = GabaritoRosca.query.get_or_404(gabarito_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['tipo_rosca', 'local_armazenamento'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/gabaritos-rosca/editar.html', gabarito=gabarito)
        
        tipo_rosca = request.form['tipo_rosca']
        local_armazenamento = request.form['local_armazenamento']
        
        # Verificar se já existe outro gabarito com o mesmo tipo de rosca (exceto o atual)
        gabarito_existente = GabaritoRosca.query.filter(GabaritoRosca.tipo_rosca == tipo_rosca, GabaritoRosca.id != gabarito_id).first()
        if gabarito_existente:
            flash('Já existe um gabarito para este tipo de rosca!', 'danger')
            return render_template('trabalhos/gabaritos-rosca/editar.html', gabarito=gabarito)
        
        # Processar imagem se enviada
        if 'imagem' in request.files and request.files['imagem'].filename:
            gabarito.imagem = save_uploaded_file(request.files['imagem'], 'gabaritos')
        
        gabarito.tipo_rosca = tipo_rosca
        gabarito.local_armazenamento = local_armazenamento
        
        db.session.commit()
        flash('Gabarito de rosca atualizado com sucesso!', 'success')
        return redirect(url_for('gabaritos_rosca.listar_gabaritos_rosca'))
    
    return render_template('trabalhos/gabaritos-rosca/editar.html', gabarito=gabarito)
