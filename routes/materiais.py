from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Material
from utils import validate_form_data

materiais = Blueprint('materiais', __name__)

@materiais.route('/materiais')
def listar_materiais():
    """Rota para listar todos os materiais"""
    materiais = Material.query.all()
    return render_template('materiais/listar.html', materiais=materiais)

@materiais.route('/materiais/novo', methods=['GET', 'POST'])
def novo_material():
    """Rota para cadastrar um novo material"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome', 'tipo'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('materiais/novo.html')
        
        nome = request.form['nome']
        tipo = request.form['tipo']
        especifico = 'especifico' in request.form
        
        # Verificar se já existe um material com o mesmo nome
        material_existente = Material.query.filter_by(nome=nome).first()
        if material_existente:
            flash('Já existe um material com este nome!', 'danger')
            return render_template('materiais/novo.html')
        
        material = Material(
            nome=nome,
            tipo=tipo,
            especifico=especifico
        )
        
        if not especifico:
            material.material = request.form.get('material', '')
            material.liga = request.form.get('liga', '')
            
            if tipo == 'redondo':
                try:
                    material.diametro = float(request.form.get('diametro', 0) or 0)
                except ValueError:
                    flash('O diâmetro deve ser um número válido', 'danger')
                    return render_template('materiais/novo.html')
            elif tipo == 'quadrado' or tipo == 'sextavado':
                try:
                    material.lado = float(request.form.get('lado', 0) or 0)
                except ValueError:
                    flash('O lado deve ser um número válido', 'danger')
                    return render_template('materiais/novo.html')
            elif tipo == 'retangulo':
                try:
                    material.largura = float(request.form.get('largura', 0) or 0)
                    material.altura = float(request.form.get('altura', 0) or 0)
                except ValueError:
                    flash('A largura e altura devem ser números válidos', 'danger')
                    return render_template('materiais/novo.html')
        
        db.session.add(material)
        db.session.commit()
        flash('Material cadastrado com sucesso!', 'success')
        return redirect(url_for('materiais.listar_materiais'))
    
    return render_template('materiais/novo.html')

@materiais.route('/materiais/editar/<int:material_id>', methods=['GET', 'POST'])
def editar_material(material_id):
    """Rota para editar um material existente"""
    material = Material.query.get_or_404(material_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome', 'tipo'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('materiais/editar.html', material=material)
        
        nome = request.form['nome']
        tipo = request.form['tipo']
        especifico = 'especifico' in request.form
        
        # Verificar se já existe outro material com o mesmo nome (exceto o atual)
        material_existente = Material.query.filter(Material.nome == nome, Material.id != material_id).first()
        if material_existente:
            flash('Já existe um material com este nome!', 'danger')
            return render_template('materiais/editar.html', material=material)
        
        material.nome = nome
        material.tipo = tipo
        material.especifico = especifico
        
        if not especifico:
            material.material = request.form.get('material', '')
            material.liga = request.form.get('liga', '')
            
            if tipo == 'redondo':
                try:
                    material.diametro = float(request.form.get('diametro', 0) or 0)
                    # Limpar outros campos que não se aplicam
                    material.lado = None
                    material.largura = None
                    material.altura = None
                except ValueError:
                    flash('O diâmetro deve ser um número válido', 'danger')
                    return render_template('materiais/editar.html', material=material)
            elif tipo == 'quadrado' or tipo == 'sextavado':
                try:
                    material.lado = float(request.form.get('lado', 0) or 0)
                    # Limpar outros campos que não se aplicam
                    material.diametro = None
                    material.largura = None
                    material.altura = None
                except ValueError:
                    flash('O lado deve ser um número válido', 'danger')
                    return render_template('materiais/editar.html', material=material)
            elif tipo == 'retangulo':
                try:
                    material.largura = float(request.form.get('largura', 0) or 0)
                    material.altura = float(request.form.get('altura', 0) or 0)
                    # Limpar outros campos que não se aplicam
                    material.diametro = None
                    material.lado = None
                except ValueError:
                    flash('A largura e altura devem ser números válidos', 'danger')
                    return render_template('materiais/editar.html', material=material)
            else:
                # Para outros tipos, limpar todos os campos específicos
                material.diametro = None
                material.lado = None
                material.largura = None
                material.altura = None
        
        db.session.commit()
        flash('Material atualizado com sucesso!', 'success')
        return redirect(url_for('materiais.listar_materiais'))
    
    return render_template('materiais/editar.html', material=material)
