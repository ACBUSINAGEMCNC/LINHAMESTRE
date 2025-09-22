from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, abort
from models import (db, Usuario, Maquina, Castanha, GabaritoRosca, GabaritoCentroUsinagem,
                   NovaFolhaProcesso, FolhaProcessoSerra, FolhaProcessoTornoCNC, 
                   FolhaProcessoCentroUsinagem, FolhaProcessoManualAcabamento,
                   FerramentaTorno, FerramentaCentro, MedidaCritica, ImagemPecaProcesso, ImagemProcessoGeral, Item)
from utils import validate_form_data, save_uploaded_file, get_file_url
from datetime import datetime
import json

novas_folhas_processo = Blueprint('novas_folhas_processo', __name__)

# ==================== ROTAS PRINCIPAIS ====================

@novas_folhas_processo.route('/folhas-processo-novas')
def listar_folhas():
    """Lista todas as folhas de processo (opcionalmente filtradas por item)"""
    item_id = request.args.get('item_id')
    
    if item_id:
        # Filtrar por item específico
        folhas = NovaFolhaProcesso.query.filter_by(ativo=True, item_id=item_id).order_by(NovaFolhaProcesso.data_criacao.desc()).all()
        item = Item.query.get(item_id)
        return render_template('novas_folhas_processo/listar.html', folhas=folhas, item=item)
    else:
        # Listar todas as folhas
        folhas = NovaFolhaProcesso.query.filter_by(ativo=True).order_by(NovaFolhaProcesso.data_criacao.desc()).all()
        return render_template('novas_folhas_processo/listar.html', folhas=folhas)

@novas_folhas_processo.route('/folhas-processo-novas/nova/<int:item_id>', methods=['GET', 'POST'])
def nova_folha(item_id):
    """Criar nova folha de processo para um item específico"""
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'POST':
        maquina_id = request.form.get('maquina_id')
        titulo_servico = request.form.get('titulo_servico')
        
        if not maquina_id or not titulo_servico:
            flash('Máquina e tipo de serviço são obrigatórios!', 'error')
            return redirect(url_for('novas_folhas_processo.nova_folha', item_id=item_id))
        
        maquina = Maquina.query.get_or_404(maquina_id)
        
        # Criar nova folha de processo SEMPRE vinculada ao item
        nova_folha = NovaFolhaProcesso(
            item_id=item_id,
            maquina_id=maquina_id,
            categoria_maquina=maquina.categoria_trabalho,
            titulo_servico=titulo_servico,
            usuario_criacao_id=session.get('usuario_id')
        )
        
        db.session.add(nova_folha)
        db.session.commit()
        
        flash(f'Folha de processo criada para o item #{item_id}!', 'success')
        
        # Redirecionar para edição específica baseada na categoria
        categoria = maquina.categoria_trabalho.lower()
        if 'serra' in categoria:
            return redirect(url_for('novas_folhas_processo.editar_serra', folha_id=nova_folha.id))
        elif 'torno' in categoria and 'cnc' in categoria:
            return redirect(url_for('novas_folhas_processo.editar_torno_cnc', folha_id=nova_folha.id))
        elif 'centro' in categoria and 'usinagem' in categoria:
            return redirect(url_for('novas_folhas_processo.editar_centro', folha_id=nova_folha.id))
        else:
            return redirect(url_for('novas_folhas_processo.editar_manual', folha_id=nova_folha.id))
    
    # GET - Mostrar formulário
    maquinas = Maquina.query.all()
    
    return render_template('novas_folhas_processo/nova_simples.html', 
                         item=item, maquinas=maquinas)

@novas_folhas_processo.route('/folhas-processo-novas/selecionar-item')
def selecionar_item():
    """Página para selecionar item antes de criar folha"""
    itens = Item.query.all()
    return render_template('novas_folhas_processo/selecionar_item.html', itens=itens)

@novas_folhas_processo.route('/folhas-processo-novas/<int:folha_id>')
def visualizar_folha(folha_id):
    """Visualiza uma folha de processo baseada em sua categoria"""
    folha = NovaFolhaProcesso.query.get_or_404(folha_id)
    categoria = folha.categoria_maquina.lower()
    
    if categoria == 'serra':
        folha_especifica = FolhaProcessoSerra.query.filter_by(nova_folha_id=folha_id).first()
        return render_template('novas_folhas_processo/visualizar_serra.html', 
                             folha=folha, folha_serra=folha_especifica)
    elif categoria == 'torno cnc':
        folha_especifica = FolhaProcessoTornoCNC.query.filter_by(nova_folha_id=folha_id).first()
        ferramentas = FerramentaTorno.query.filter_by(folha_torno_id=folha_especifica.id).all() if folha_especifica else []
        medidas = MedidaCritica.query.filter_by(folha_tipo='torno', folha_id=folha_especifica.id).all() if folha_especifica else []
        imagens_peca = ImagemPecaProcesso.query.filter_by(folha_tipo='torno', folha_id=folha_especifica.id).all() if folha_especifica else []
        
        return render_template('novas_folhas_processo/visualizar_torno_cnc.html', 
                             folha=folha, folha_torno=folha_especifica,
                             ferramentas=ferramentas, medidas=medidas, imagens_peca=imagens_peca)
    elif categoria == 'centro de usinagem':
        folha_especifica = FolhaProcessoCentroUsinagem.query.filter_by(nova_folha_id=folha_id).first()
        ferramentas = FerramentaCentro.query.filter_by(folha_centro_id=folha_especifica.id).all() if folha_especifica else []
        medidas = MedidaCritica.query.filter_by(folha_tipo='centro', folha_id=folha_especifica.id).all() if folha_especifica else []
        imagens_peca = ImagemPecaProcesso.query.filter_by(folha_tipo='centro', folha_id=folha_especifica.id).all() if folha_especifica else []
        
        return render_template('novas_folhas_processo/visualizar_centro_usinagem.html', 
                             folha=folha, folha_centro=folha_especifica,
                             ferramentas=ferramentas, medidas=medidas, imagens_peca=imagens_peca)
    else:
        folha_especifica = FolhaProcessoManualAcabamento.query.filter_by(nova_folha_id=folha_id).first()
        return render_template('novas_folhas_processo/visualizar_manual_acabamento.html', 
                             folha=folha, folha_manual=folha_especifica)

# ==================== ROTAS DE EDIÇÃO POR CATEGORIA ====================

@novas_folhas_processo.route('/folhas-processo-novas/serra/<int:folha_id>/editar', methods=['GET', 'POST'])
def editar_serra(folha_id):
    """Edita folha de processo para categoria Serra"""
    folha = NovaFolhaProcesso.query.get_or_404(folha_id)
    folha_serra = FolhaProcessoSerra.query.filter_by(nova_folha_id=folha_id).first()
    
    if not folha_serra:
        folha_serra = FolhaProcessoSerra(nova_folha_id=folha_id)
        db.session.add(folha_serra)
    
    if request.method == 'POST':
        # Atualizar dados da serra
        folha_serra.tamanho_corte = request.form.get('tamanho_corte', '')
        folha_serra.diametro_material = float(request.form.get('diametro_material', 0) or 0)
        folha_serra.tipo_material = request.form.get('tipo_material', '')
        folha_serra.como_cortar = request.form.get('como_cortar', '')
        folha_serra.observacoes = request.form.get('observacoes', '')
        
        # Upload da imagem da peça bruta
        if 'imagem_peca_bruta' in request.files and request.files['imagem_peca_bruta'].filename:
            folha_serra.imagem_peca_bruta = save_uploaded_file(request.files['imagem_peca_bruta'], 'folhas_processo')
        
        # Atualizar dados da folha principal
        folha.data_atualizacao = datetime.utcnow()
        
        db.session.commit()
        flash('Folha de processo atualizada com sucesso!', 'success')
        return redirect(url_for('novas_folhas_processo.visualizar_folha', folha_id=folha_id))
    
    return render_template('novas_folhas_processo/editar_serra.html', folha=folha, folha_serra=folha_serra)

@novas_folhas_processo.route('/folhas-processo-novas/torno-cnc/<int:folha_id>/editar', methods=['GET', 'POST'])
def editar_torno_cnc(folha_id):
    """Edita folha de processo para categoria Torno CNC"""
    folha = NovaFolhaProcesso.query.get_or_404(folha_id)
    folha_torno = FolhaProcessoTornoCNC.query.filter_by(nova_folha_id=folha_id).first()
    
    if not folha_torno:
        folha_torno = FolhaProcessoTornoCNC(nova_folha_id=folha_id)
        db.session.add(folha_torno)
        db.session.flush()
    
    if request.method == 'POST':
        # Atualizar dados do torno
        folha_torno.castanha_id = int(request.form.get('castanha_id') or 0) or None
        folha_torno.gabarito_rosca_id = int(request.form.get('gabarito_rosca_id') or 0) or None
        # Processar upload de programa CNC se houver arquivo
        if 'arquivo_programa' in request.files and request.files['arquivo_programa'].filename:
            arquivo_programa = request.files['arquivo_programa']
            if arquivo_programa and arquivo_programa.filename.lower().endswith(('.nc', '.txt', '.cnc')):
                try:
                    # Ler o conteúdo do arquivo
                    conteudo_programa = arquivo_programa.read().decode('utf-8')
                    folha_torno.programa_cnc = conteudo_programa
                    # Se nome do programa não foi fornecido, usar nome do arquivo
                    if not request.form.get('nome_programa'):
                        folha_torno.nome_programa = arquivo_programa.filename
                    else:
                        folha_torno.nome_programa = request.form.get('nome_programa', '')
                except:
                    # Se houver erro na leitura, usar o texto digitado
                    folha_torno.programa_cnc = request.form.get('programa_cnc', '')
                    folha_torno.nome_programa = request.form.get('nome_programa', '')
            else:
                folha_torno.programa_cnc = request.form.get('programa_cnc', '')
                folha_torno.nome_programa = request.form.get('nome_programa', '')
        else:
            folha_torno.programa_cnc = request.form.get('programa_cnc', '')
            folha_torno.nome_programa = request.form.get('nome_programa', '')
        folha_torno.jogo_bucha_guia = request.form.get('jogo_bucha_guia', '')
        folha_torno.local_armazenagem_bucha = request.form.get('local_armazenagem_bucha', '')
        folha_torno.encosto = request.form.get('encosto', '')
        folha_torno.local_armazenagem_encosto = request.form.get('local_armazenagem_encosto', '')
        folha_torno.observacoes = request.form.get('observacoes', '')
        
        # Upload das imagens
        for campo_imagem in ['imagem_torre_montada', 'imagem_peca_fixa', 'imagem_bucha_guia', 'imagem_encosto']:
            if campo_imagem in request.files and request.files[campo_imagem].filename:
                setattr(folha_torno, campo_imagem, save_uploaded_file(request.files[campo_imagem], 'folhas_processo'))
        
        # Processar ferramentas novas (do modal)
        if 'ferramentas[]' in request.form:
            import json
            for ferramenta_json in request.form.getlist('ferramentas[]'):
                try:
                    dados_ferramenta = json.loads(ferramenta_json)
                    nova_ferramenta = FerramentaTorno(
                        folha_torno_id=folha_torno.id,
                        posicao=dados_ferramenta.get('posicao'),
                        descricao=dados_ferramenta.get('descricao'),
                        configuracao=dados_ferramenta.get('configuracao')
                    )
                    db.session.add(nova_ferramenta)
                except:
                    pass  # Ignora erros de JSON malformado
        
        # Processar medidas novas (do modal)
        if 'medidas[]' in request.form:
            import json
            for medida_json in request.form.getlist('medidas[]'):
                try:
                    dados_medida = json.loads(medida_json)
                    nova_medida = MedidaCritica(
                        folha_tipo='torno',
                        folha_id=folha_torno.id,
                        descricao=dados_medida.get('descricao'),
                        valor=dados_medida.get('valor'),
                        tolerancia=dados_medida.get('tolerancia')
                    )
                    db.session.add(nova_medida)
                except:
                    pass  # Ignora erros de JSON malformado
        
        folha.data_atualizacao = datetime.utcnow()
        db.session.commit()
        flash('Folha de processo atualizada com sucesso!', 'success')
        return redirect(url_for('novas_folhas_processo.visualizar_folha', folha_id=folha_id))
    
    # Buscar dados para os selects
    castanhas = Castanha.query.all()
    gabaritos_rosca = GabaritoRosca.query.all()
    ferramentas = FerramentaTorno.query.filter_by(folha_torno_id=folha_torno.id).all()
    medidas = MedidaCritica.query.filter_by(folha_tipo='torno', folha_id=folha_torno.id).all()
    imagens_peca = ImagemPecaProcesso.query.filter_by(folha_tipo='torno', folha_id=folha_torno.id).all()
    
    return render_template('novas_folhas_processo/editar_torno_cnc.html', 
                          folha=folha, folha_torno=folha_torno,
                          castanhas=castanhas, gabaritos_rosca=gabaritos_rosca,
                          ferramentas=ferramentas, medidas=medidas, imagens_peca=imagens_peca)

@novas_folhas_processo.route('/folhas-processo-novas/centro-usinagem/<int:folha_id>/editar', methods=['GET', 'POST'])
def editar_centro_usinagem(folha_id):
    """Edita folha de processo para categoria Centro de Usinagem"""
    folha = NovaFolhaProcesso.query.get_or_404(folha_id)
    folha_centro = FolhaProcessoCentroUsinagem.query.filter_by(nova_folha_id=folha_id).first()
    
    if not folha_centro:
        folha_centro = FolhaProcessoCentroUsinagem(nova_folha_id=folha_id)
        db.session.add(folha_centro)
        db.session.flush()
    
    if request.method == 'POST':
        # Atualizar dados do centro de usinagem
        folha_centro.gabarito_centro_id = int(request.form.get('gabarito_centro_id') or 0) or None
        folha_centro.como_zeramento = request.form.get('como_zeramento', '')
        folha_centro.observacoes = request.form.get('observacoes', '')
        
        # Upload das imagens
        for campo_imagem in ['imagem_gabarito_montado', 'imagem_zeramento']:
            if campo_imagem in request.files and request.files[campo_imagem].filename:
                setattr(folha_centro, campo_imagem, save_uploaded_file(request.files[campo_imagem], 'folhas_processo'))
        
        folha.data_atualizacao = datetime.utcnow()
        db.session.commit()
        flash('Folha de processo atualizada com sucesso!', 'success')
        return redirect(url_for('novas_folhas_processo.visualizar_folha', folha_id=folha_id))
    
    # Buscar dados para os selects
    gabaritos_centro = GabaritoCentroUsinagem.query.all()
    ferramentas = FerramentaCentro.query.filter_by(folha_centro_id=folha_centro.id).all()
    medidas = MedidaCritica.query.filter_by(folha_tipo='centro', folha_id=folha_centro.id).all()
    imagens_peca = ImagemPecaProcesso.query.filter_by(folha_tipo='centro', folha_id=folha_centro.id).all()
    
    return render_template('novas_folhas_processo/editar_centro_usinagem.html', 
                          folha=folha, folha_centro=folha_centro,
                          gabaritos_centro=gabaritos_centro,
                          ferramentas=ferramentas, medidas=medidas, imagens_peca=imagens_peca)

@novas_folhas_processo.route('/folhas-processo-novas/manual-acabamento/<int:folha_id>/editar', methods=['GET', 'POST'])
def editar_manual_acabamento(folha_id):
    """Edita folha de processo para categorias Manual, Acabamento e Outros"""
    folha = NovaFolhaProcesso.query.get_or_404(folha_id)
    folha_manual = FolhaProcessoManualAcabamento.query.filter_by(nova_folha_id=folha_id).first()
    
    if not folha_manual:
        folha_manual = FolhaProcessoManualAcabamento(nova_folha_id=folha_id)
        db.session.add(folha_manual)
        db.session.flush()
    
    if request.method == 'POST':
        # Atualizar dados gerais
        folha_manual.possui_tempera = 'possui_tempera' in request.form
        folha_manual.tipo_tempera = request.form.get('tipo_tempera', '') if folha_manual.possui_tempera else ''
        folha_manual.observacoes = request.form.get('observacoes', '')
        
        # Dados específicos da têmpera por indução
        if folha_manual.tipo_tempera == 'inducao':
            folha_manual.programa_inducao = request.form.get('programa_inducao', '')
            folha_manual.indutor_utilizado = request.form.get('indutor_utilizado', '')
            folha_manual.local_armazenagem_gabarito_inducao = request.form.get('local_armazenagem_gabarito_inducao', '')
            folha_manual.dureza_inducao = request.form.get('dureza_inducao', '')
            
            # Upload das imagens de indução
            for campo in ['imagem_gabarito_inducao', 'imagem_indutor', 'imagem_montagem_inducao', 'imagem_dureza_inducao']:
                if campo in request.files and request.files[campo].filename:
                    setattr(folha_manual, campo, save_uploaded_file(request.files[campo], 'folhas_processo'))
        
        # Dados específicos da têmpera por forno
        if folha_manual.tipo_tempera == 'forno':
            folha_manual.dureza_forno = request.form.get('dureza_forno', '')
            
            # Upload das imagens de forno
            for campo in ['imagem_peca_temperada_forno', 'imagem_dureza_forno']:
                if campo in request.files and request.files[campo].filename:
                    setattr(folha_manual, campo, save_uploaded_file(request.files[campo], 'folhas_processo'))
        
        folha.data_atualizacao = datetime.utcnow()
        db.session.commit()
        flash('Folha de processo atualizada com sucesso!', 'success')
        return redirect(url_for('novas_folhas_processo.visualizar_folha', folha_id=folha_id))
    
    return render_template('novas_folhas_processo/editar_manual_acabamento.html', 
                          folha=folha, folha_manual=folha_manual)

# ======================= ROTAS AJAX PARA CRUD DE FERRAMENTAS E MEDIDAS =======================

@novas_folhas_processo.route('/ferramenta/<int:ferramenta_id>', methods=['POST'])
def atualizar_ferramenta(ferramenta_id):
    """Atualizar ferramenta via AJAX"""
    try:
        # Verificar se a ferramenta existe
        ferramenta = FerramentaTorno.query.get(ferramenta_id)
        if not ferramenta:
            return jsonify({'success': False, 'message': f'Ferramenta com ID {ferramenta_id} não encontrada'})
        
        # Verificar se há dados JSON
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dados JSON não fornecidos'})
        
        # Validar dados obrigatórios
        posicao = data.get('posicao', '').strip()
        descricao = data.get('descricao', '').strip()
        
        if not posicao or not descricao:
            return jsonify({'success': False, 'message': 'Posição e descrição são obrigatórios'})
        
        # Atualizar ferramenta
        ferramenta.posicao = posicao
        ferramenta.descricao = descricao
        ferramenta.configuracao = data.get('configuracao', '').strip()
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Ferramenta atualizada com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

@novas_folhas_processo.route('/ferramenta/<int:ferramenta_id>', methods=['DELETE'])
def excluir_ferramenta(ferramenta_id):
    """Excluir ferramenta via AJAX"""
    try:
        ferramenta = FerramentaTorno.query.get_or_404(ferramenta_id)
        db.session.delete(ferramenta)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@novas_folhas_processo.route('/medida/<int:medida_id>', methods=['POST'])
def atualizar_medida(medida_id):
    """Atualizar medida crítica via AJAX"""
    try:
        medida = MedidaCritica.query.get_or_404(medida_id)
        data = request.get_json()
        
        medida.descricao = data.get('descricao', '')
        medida.valor = data.get('valor', '')
        medida.tolerancia = data.get('tolerancia', '')
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@novas_folhas_processo.route('/medida/<int:medida_id>', methods=['DELETE'])
def excluir_medida(medida_id):
    """Excluir medida crítica via AJAX"""
    try:
        medida = MedidaCritica.query.get_or_404(medida_id)
        db.session.delete(medida)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ==================== ROTAS AJAX PARA MÚLTIPLAS ENTRADAS ====================

@novas_folhas_processo.route('/api/ferramentas/<tipo>/<int:folha_id>', methods=['POST'])
def adicionar_ferramenta(tipo, folha_id):
    """Adiciona uma ferramenta (AJAX)"""
    try:
        posicao = request.json.get('posicao')
        descricao = request.json.get('descricao')
        configuracao = request.json.get('configuracao')
        
        if tipo == 'torno':
            ferramenta = FerramentaTorno(
                folha_torno_id=folha_id,
                posicao=posicao,
                descricao=descricao,
                configuracao=configuracao
            )
        else:  # centro
            ferramenta = FerramentaCentro(
                folha_centro_id=folha_id,
                posicao=posicao,
                descricao=descricao,
                configuracao=configuracao
            )
        
        db.session.add(ferramenta)
        db.session.commit()
        
        return jsonify({'success': True, 'id': ferramenta.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@novas_folhas_processo.route('/api/medidas/<tipo>/<int:folha_id>', methods=['POST'])
def adicionar_medida(tipo, folha_id):
    """Adiciona uma medida crítica (AJAX)"""
    try:
        descricao = request.json.get('descricao')
        valor = request.json.get('valor')
        tolerancia = request.json.get('tolerancia')
        
        medida = MedidaCritica(
            folha_tipo=tipo,
            folha_id=folha_id,
            descricao=descricao,
            valor=valor,
            tolerancia=tolerancia
        )
        
        db.session.add(medida)
        db.session.commit()
        
        return jsonify({'success': True, 'id': medida.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@novas_folhas_processo.route('/api/imagens-peca/<tipo>/<int:folha_id>', methods=['POST'])
def adicionar_imagem_peca(tipo, folha_id):
    """Adiciona imagem de peça com observação (AJAX)"""
    try:
        observacao = request.form.get('observacao')
        
        if 'imagem' in request.files and request.files['imagem'].filename:
            imagem_path = save_uploaded_file(request.files['imagem'], 'folhas_processo')
            
            imagem_peca = ImagemPecaProcesso(
                folha_tipo=tipo,
                folha_id=folha_id,
                imagem=imagem_path,
                observacao=observacao
            )
            
            db.session.add(imagem_peca)
            db.session.commit()
            
            return jsonify({'success': True, 'id': imagem_peca.id})
        
        return jsonify({'success': False, 'error': 'Nenhuma imagem enviada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== ROTAS DE EXCLUSÃO ====================

@novas_folhas_processo.route('/folhas-processo-novas/<int:folha_id>/excluir', methods=['POST'])
def excluir_folha(folha_id):
    """Marca folha como inativa (exclusão lógica)"""
    folha = NovaFolhaProcesso.query.get_or_404(folha_id)
    folha.ativo = False
    db.session.commit()
    flash('Folha de processo excluída com sucesso!', 'success')
    return redirect(url_for('novas_folhas_processo.listar_folhas'))
