from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
from models import db, Item, Material, Trabalho, ItemMaterial, ItemTrabalho, Pedido, ArquivoCNC
from utils import validate_form_data, save_file, generate_next_code, parse_json_field
from flask import current_app

itens = Blueprint('itens', __name__)

@itens.route('/itens')
def listar_itens():
    """Rota para listar todos os itens"""
    itens = Item.query.all()
    return render_template('itens/listar.html', itens=itens)

@itens.route('/itens/novo', methods=['GET', 'POST'])
def novo_item():
    """Rota para cadastrar um novo item"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            materiais = Material.query.all()
            trabalhos = Trabalho.query.all()
            return render_template('itens/novo.html', materiais=materiais, trabalhos=trabalhos, item=None)
        
        nome = request.form['nome']
        
        # Verificar se já existe um item com o mesmo nome
        item_existente = Item.query.filter_by(nome=nome).first()
        if item_existente:
            flash('Já existe um item com este nome!', 'danger')
            materiais = Material.query.all()
            trabalhos = Trabalho.query.all()
            return render_template('itens/novo.html', materiais=materiais, trabalhos=trabalhos, item=None)
        
        # Gerar código ACB automaticamente
        novo_codigo = generate_next_code(Item, "ACB", "codigo_acb")
        
        # Criar o item
        item = Item(
            nome=nome,
            codigo_acb=novo_codigo,
            tempera='tempera' in request.form,
            tipo_tempera=request.form.get('tipo_tempera', ''),
            retifica='retifica' in request.form,
            pintura='pintura' in request.form,
            tipo_pintura=request.form.get('tipo_pintura', ''),
            cor_pintura=request.form.get('cor_pintura', ''),
            oleo_protetivo='oleo_protetivo' in request.form,
            zincagem='zincagem' in request.form,
            tipo_zincagem=request.form.get('tipo_zincagem', ''),
            tipo_embalagem=request.form.get('tipo_embalagem', '')
        )
        
        # Validar e converter o peso
        try:
            peso = request.form.get('peso', 0)
            item.peso = float(peso) if peso else 0
        except ValueError:
            flash('O peso deve ser um número válido', 'danger')
            materiais = Material.query.all()
            trabalhos = Trabalho.query.all()
            return render_template('itens/novo.html', materiais=materiais, trabalhos=trabalhos, item=None)
        
        # Upload de arquivos
        if 'desenho_tecnico' in request.files:
            item.desenho_tecnico = save_file(request.files['desenho_tecnico'], 'desenhos')
        
        if 'imagem' in request.files:
            item.imagem = save_file(request.files['imagem'], 'imagens')
        
        if 'instrucoes_trabalho' in request.files:
            item.instrucoes_trabalho = save_file(request.files['instrucoes_trabalho'], 'instrucoes')
        
        db.session.add(item)
        db.session.commit()
        
        # Adicionar materiais
        materiais_json = parse_json_field(request.form, 'materiais')
        for mat in materiais_json:
            try:
                item_material = ItemMaterial(
                    item_id=item.id,
                    material_id=mat['id'],
                    comprimento=float(mat.get('comprimento', 0) or 0),
                    quantidade=int(mat.get('quantidade', 1) or 1)
                )
                db.session.add(item_material)
            except (ValueError, KeyError) as e:
                flash(f'Erro ao processar material: {str(e)}', 'danger')
        
        # Adicionar trabalhos
        trabalhos_json = parse_json_field(request.form, 'trabalhos')
        for trab in trabalhos_json:
            try:
                item_trabalho = ItemTrabalho(
                    item_id=item.id,
                    trabalho_id=trab['id'],
                    tempo_setup=int(trab.get('tempo_setup', 0) or 0),
                    tempo_peca=int(trab.get('tempo_peca', 0) or 0)
                )
                db.session.add(item_trabalho)
            except (ValueError, KeyError) as e:
                flash(f'Erro ao processar trabalho: {str(e)}', 'danger')
        
        # Adicionar arquivos CNC
        if 'cnc_files' in request.files:
            cnc_files = request.files.getlist('cnc_files')
            maquina = request.form.get('maquina_cnc', '')
            criador_id = current_app.config['CURRENT_USER_ID']  # Substituir por autenticação real
            for file in cnc_files:
                if file and file.filename.endswith(('.txt', '.nc')):
                    filename = save_file(file, 'cnc_files')
                    arquivo_cnc = ArquivoCNC(
                        item_id=item.id,
                        nome_arquivo=filename,
                        caminho_arquivo=os.path.join('uploads/cnc_files', filename),
                        maquina=maquina,
                        criador_id=criador_id
                    )
                    db.session.add(arquivo_cnc)
        
        db.session.commit()
        flash('Item cadastrado com sucesso!', 'success')
        return redirect(url_for('itens.listar_itens'))
    
    materiais = Material.query.all()
    trabalhos = Trabalho.query.all()
    return render_template('itens/novo.html', materiais=materiais, trabalhos=trabalhos, item=None)

@itens.route('/itens/editar/<int:item_id>', methods=['GET', 'POST'])
def editar_item(item_id):
    """Rota para editar um item existente"""
    item = Item.query.get_or_404(item_id)
    materiais = Material.query.all()
    trabalhos = Trabalho.query.all()
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['nome'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('itens/editar.html', item=item, materiais=materiais, trabalhos=trabalhos)
        
        nome = request.form['nome']
        
        # Verificar se já existe outro item com o mesmo nome (exceto o atual)
        item_existente = Item.query.filter(Item.nome == nome, Item.id != item_id).first()
        if item_existente:
            flash('Já existe um item com este nome!', 'danger')
            return render_template('itens/editar.html', item=item, materiais=materiais, trabalhos=trabalhos)
        
        # Atualizar dados do item
        item.nome = nome
        item.tempera = 'tempera' in request.form
        item.tipo_tempera = request.form.get('tipo_tempera', '')
        item.retifica = 'retifica' in request.form
        item.pintura = 'pintura' in request.form
        item.tipo_pintura = request.form.get('tipo_pintura', '')
        item.cor_pintura = request.form.get('cor_pintura', '')
        item.oleo_protetivo = 'oleo_protetivo' in request.form
        item.zincagem = 'zincagem' in request.form
        item.tipo_zincagem = request.form.get('tipo_zincagem', '')
        item.tipo_embalagem = request.form.get('tipo_embalagem', '')
        
        # Validar e converter o peso
        try:
            peso = request.form.get('peso', 0)
            item.peso = float(peso) if peso else 0
        except ValueError:
            flash('O peso deve ser um número válido', 'danger')
            return render_template('itens/editar.html', item=item, materiais=materiais, trabalhos=trabalhos)
        
        # Upload de arquivos
        if 'desenho_tecnico' in request.files and request.files['desenho_tecnico'].filename:
            item.desenho_tecnico = save_file(request.files['desenho_tecnico'], 'desenhos')
        
        if 'imagem' in request.files and request.files['imagem'].filename:
            item.imagem = save_file(request.files['imagem'], 'imagens')
        
        if 'instrucoes_trabalho' in request.files and request.files['instrucoes_trabalho'].filename:
            item.instrucoes_trabalho = save_file(request.files['instrucoes_trabalho'], 'instrucoes')
        
        # Atualizar materiais
        materiais_json = parse_json_field(request.form, 'materiais')
        
        # Remover materiais existentes
        ItemMaterial.query.filter_by(item_id=item.id).delete()
        
        # Adicionar novos materiais
        for mat in materiais_json:
            try:
                item_material = ItemMaterial(
                    item_id=item.id,
                    material_id=mat['id'],
                    comprimento=float(mat.get('comprimento', 0) or 0),
                    quantidade=int(mat.get('quantidade', 1) or 1)
                )
                db.session.add(item_material)
            except (ValueError, KeyError) as e:
                flash(f'Erro ao processar material: {str(e)}', 'danger')
        
        # Atualizar trabalhos
        trabalhos_json = parse_json_field(request.form, 'trabalhos')
        
        # Remover trabalhos existentes
        ItemTrabalho.query.filter_by(item_id=item.id).delete()
        
        # Adicionar novos trabalhos
        for trab in trabalhos_json:
            try:
                item_trabalho = ItemTrabalho(
                    item_id=item.id,
                    trabalho_id=trab['id'],
                    tempo_setup=int(trab.get('tempo_setup', 0) or 0),
                    tempo_peca=int(trab.get('tempo_peca', 0) or 0)
                )
                db.session.add(item_trabalho)
            except (ValueError, KeyError) as e:
                flash(f'Erro ao processar trabalho: {str(e)}', 'danger')
        
        # Adicionar arquivos CNC
        if 'cnc_files' in request.files:
            cnc_files = request.files.getlist('cnc_files')
            maquina = request.form.get('maquina_cnc', '')
            criador_id = current_app.config['CURRENT_USER_ID']  # Substituir por autenticação real
            for file in cnc_files:
                if file and file.filename.endswith(('.txt', '.nc')):
                    filename = save_file(file, 'cnc_files')
                    arquivo_cnc = ArquivoCNC(
                        item_id=item.id,
                        nome_arquivo=filename,
                        caminho_arquivo=os.path.join('uploads/cnc_files', filename),
                        maquina=maquina,
                        criador_id=criador_id
                    )
                    db.session.add(arquivo_cnc)
        
        db.session.commit()
        flash('Item atualizado com sucesso!', 'success')
        return redirect(url_for('itens.listar_itens'))
    
    # Obter materiais e trabalhos do item para preencher o formulário
    item_materiais = []
    for im in item.materiais:
        material = Material.query.get(im.material_id)
        item_materiais.append({
            'id': im.material_id,
            'nome': material.nome,
            'tipo': material.tipo,
            'comprimento': im.comprimento,
            'quantidade': im.quantidade
        })
    
    item_trabalhos = []
    for it in item.trabalhos:
        trabalho = Trabalho.query.get(it.trabalho_id)
        item_trabalhos.append({
            'id': it.trabalho_id,
            'nome': trabalho.nome,
            'tempo_setup': it.tempo_setup,
            'tempo_peca': it.tempo_peca
        })
    
    return render_template('itens/editar.html', 
                          item=item, 
                          materiais=materiais, 
                          trabalhos=trabalhos,
                          item_materiais=json.dumps(item_materiais),
                          item_trabalhos=json.dumps(item_trabalhos))

@itens.route('/itens/atualizar_ordem', methods=['POST'])
def atualizar_ordem():
    # Apenas retorna sucesso sem tentar salvar no banco
    # A ordem será mantida no localStorage do navegador
    return jsonify({'status': 'sucesso'})

@itens.route('/itens/<int:item_id>/adicionar-arquivo-cnc', methods=['POST'])
def adicionar_arquivo_cnc(item_id):
    """Rota para adicionar um arquivo CNC a um item existente"""
    item = Item.query.get_or_404(item_id)
    
    # Processar arquivos CNC enviados via formulário dinâmico
    cnc_files = request.files.getlist('cnc_files[]') if 'cnc_files[]' in request.files else []
    cnc_nomes = request.form.getlist('cnc_nomes[]') if 'cnc_nomes[]' in request.form else []
    cnc_maquinas = request.form.getlist('cnc_maquinas[]') if 'cnc_maquinas[]' in request.form else []
    
    # Criar diretório para arquivos CNC se não existir
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER_INSTRUCOES'], 'arquivos_cnc')
    os.makedirs(upload_dir, exist_ok=True)
    
    arquivos_adicionados = 0
    
    if cnc_files and len(cnc_files) > 0 and cnc_files[0].filename != '':
        # Processar cada arquivo CNC com seus metadados
        for i, file in enumerate(cnc_files):
            if file and file.filename.endswith(('.txt', '.nc')):
                # Obter nome e máquina correspondentes
                nome_personalizado = cnc_nomes[i] if i < len(cnc_nomes) else ''
                maquina = cnc_maquinas[i] if i < len(cnc_maquinas) else ''
                
                # Se não houver nome personalizado, usar o nome original
                if not nome_personalizado:
                    nome_personalizado = os.path.splitext(file.filename)[0]
                
                # Gerar nome de arquivo com extensão original
                extensao = os.path.splitext(file.filename)[1]
                nome_arquivo = secure_filename(f"{nome_personalizado}{extensao}")
                
                # Salvar arquivo
                file_path = os.path.join(upload_dir, nome_arquivo)
                file.save(file_path)
                
                # Criar registro no banco
                arquivo_cnc = ArquivoCNC(
                    item_id=item.id,
                    nome_arquivo=nome_arquivo,
                    caminho_arquivo=file_path,  # Adicionar o caminho do arquivo
                    maquina=maquina,
                    criador_id=request.form.get('usuario_id', session.get('usuario_id', 1))  # Usar ID do usuário da sessão
                )
                db.session.add(arquivo_cnc)
                arquivos_adicionados += 1
    
    if arquivos_adicionados > 0:
        db.session.commit()
        flash(f'{arquivos_adicionados} arquivo(s) CNC adicionado(s) com sucesso!', 'success')
    else:
        flash('Nenhum arquivo CNC válido foi enviado.', 'warning')
    
    return redirect(url_for('itens.editar_item', item_id=item_id))

@itens.route('/itens/<int:item_id>/remover-arquivo-cnc/<int:arquivo_id>', methods=['GET'])
def remover_arquivo_cnc(item_id, arquivo_id):
    """Rota para remover um arquivo CNC de um item"""
    arquivo = ArquivoCNC.query.get_or_404(arquivo_id)
    
    # Verificar se o arquivo pertence ao item correto
    if arquivo.item_id != item_id:
        flash('Arquivo não pertence a este item!', 'danger')
        return redirect(url_for('itens.editar_item', item_id=item_id))
    
    # Tentar excluir o arquivo físico
    try:
        if os.path.exists(arquivo.caminho_arquivo):
            os.remove(arquivo.caminho_arquivo)
    except Exception as e:
        flash(f'Erro ao excluir o arquivo: {str(e)}', 'warning')
    
    # Excluir o registro no banco de dados
    db.session.delete(arquivo)
    db.session.commit()
    
    flash('Arquivo CNC removido com sucesso!', 'success')
    return redirect(url_for('itens.editar_item', item_id=item_id))

@itens.route('/itens/download-arquivo-cnc/<int:arquivo_id>', methods=['GET'])
def download_arquivo_cnc(arquivo_id):
    """Rota para download de arquivo CNC"""
    arquivo = ArquivoCNC.query.get_or_404(arquivo_id)
    
    # Verificar se o arquivo existe
    if not os.path.exists(arquivo.caminho_arquivo):
        flash('Arquivo não encontrado no servidor.', 'danger')
        return redirect(url_for('itens.editar_item', item_id=arquivo.item_id))
    
    # Retornar o arquivo para download
    return send_file(arquivo.caminho_arquivo, as_attachment=True, download_name=arquivo.nome_arquivo)

@itens.route('/itens/excluir/<int:item_id>', methods=['POST'])
def excluir_item(item_id):
    """Rota para excluir um item"""
    item = Item.query.get_or_404(item_id)
    
    # Verificar se o item está associado a algum pedido
    pedidos_associados = Pedido.query.filter_by(item_id=item_id).count()
    if pedidos_associados > 0:
        flash('Não é possível excluir um item associado a pedidos!', 'danger')
        return redirect(url_for('itens.listar_itens'))
    
    # Excluir relações com materiais e trabalhos
    ItemMaterial.query.filter_by(item_id=item_id).delete()
    ItemTrabalho.query.filter_by(item_id=item_id).delete()
    ArquivoCNC.query.filter_by(item_id=item_id).delete()
    
    # Armazenar o nome para mensagem
    nome_item = item.nome
    
    # Excluir o item
    db.session.delete(item)
    db.session.commit()
    
    flash(f'Item "{nome_item}" excluído com sucesso!', 'success')
    return redirect(url_for('itens.listar_itens'))

@itens.route('/itens/visualizar/<int:item_id>')
def visualizar_item(item_id):
    """Rota para visualizar detalhes de um item"""
    item = Item.query.get_or_404(item_id)
    return render_template('itens/visualizar.html', item=item)

@itens.route('/api/item/<int:item_id>')
def api_item(item_id):
    """API para obter dados de um item"""
    item = Item.query.get_or_404(item_id)
    return jsonify({
        'id': item.id,
        'nome': item.nome,
        'codigo_acb': item.codigo_acb
    })
