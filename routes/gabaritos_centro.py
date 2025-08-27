from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, GabaritoCentroUsinagem
from utils import validate_form_data, save_uploaded_file, generate_next_code

gabaritos_centro = Blueprint('gabaritos_centro', __name__)

@gabaritos_centro.route('/trabalhos/gabaritos-centro')
def listar_gabaritos_centro():
    """Rota para listar todos os gabaritos de centro de usinagem"""
    gabaritos = GabaritoCentroUsinagem.query.all()
    return render_template('trabalhos/gabaritos-centro/listar.html', gabaritos=gabaritos)

@gabaritos_centro.route('/trabalhos/gabaritos-centro/novo', methods=['GET', 'POST'])
def novo_gabarito_centro():
    """Rota para cadastrar um novo gabarito de centro de usinagem"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome', 'local_armazenamento'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/gabaritos-centro/novo.html')
        
        nome = request.form['nome']
        funcao = request.form.get('funcao', '')
        local_armazenamento = request.form['local_armazenamento']
        
        # Verificar se já existe um gabarito com o mesmo nome
        gabarito_existente = GabaritoCentroUsinagem.query.filter_by(nome=nome).first()
        if gabarito_existente:
            flash('Já existe um gabarito com este nome!', 'danger')
            return render_template('trabalhos/gabaritos-centro/novo.html')
        
        # Gerar código automático
        codigo = generate_next_code(GabaritoCentroUsinagem, 'GCU', 'codigo')
        
        # Processar imagem se enviada
        imagem = None
        if 'imagem' in request.files and request.files['imagem'].filename:
            imagem = save_uploaded_file(request.files['imagem'], 'gabaritos')
        
        gabarito = GabaritoCentroUsinagem(
            codigo=codigo,
            nome=nome,
            funcao=funcao,
            local_armazenamento=local_armazenamento,
            imagem=imagem
        )
        
        db.session.add(gabarito)
        db.session.commit()
        flash('Gabarito cadastrado com sucesso!', 'success')
        return redirect(url_for('gabaritos_centro.listar_gabaritos_centro'))
    
    return render_template('trabalhos/gabaritos-centro/novo.html')

@gabaritos_centro.route('/trabalhos/gabaritos-centro/editar/<int:gabarito_id>', methods=['GET', 'POST'])
def editar_gabarito_centro(gabarito_id):
    """Rota para editar um gabarito de centro de usinagem existente"""
    gabarito = GabaritoCentroUsinagem.query.get_or_404(gabarito_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome', 'local_armazenamento'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('trabalhos/gabaritos-centro/editar.html', gabarito=gabarito)
        
        nome = request.form['nome']
        funcao = request.form.get('funcao', '')
        local_armazenamento = request.form['local_armazenamento']
        
        # Verificar se já existe outro gabarito com o mesmo nome (exceto o atual)
        gabarito_existente = GabaritoCentroUsinagem.query.filter(GabaritoCentroUsinagem.nome == nome, GabaritoCentroUsinagem.id != gabarito_id).first()
        if gabarito_existente:
            flash('Já existe um gabarito com este nome!', 'danger')
            return render_template('trabalhos/gabaritos-centro/editar.html', gabarito=gabarito)
        
        # Processar imagem se enviada
        if 'imagem' in request.files and request.files['imagem'].filename:
            gabarito.imagem = save_uploaded_file(request.files['imagem'], 'gabaritos')
        
        gabarito.nome = nome
        gabarito.funcao = funcao
        gabarito.local_armazenamento = local_armazenamento
        
        db.session.commit()
        flash('Gabarito atualizado com sucesso!', 'success')
        return redirect(url_for('gabaritos_centro.listar_gabaritos_centro'))
    
    return render_template('trabalhos/gabaritos-centro/editar.html', gabarito=gabarito)
