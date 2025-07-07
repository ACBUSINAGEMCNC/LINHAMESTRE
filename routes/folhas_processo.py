from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from models import (db, Usuario, Item, FolhaProcesso, FolhaTornoCNC, FolhaCentroUsinagem, 
                   FolhaCorteSerraria, FolhaServicosGerais)
from utils import validate_form_data
from datetime import datetime, date

folhas_processo = Blueprint('folhas_processo', __name__)

# Funções auxiliares
def obter_folha_especifica(folha):
    """Obtém a folha específica baseada no tipo de processo"""
    if folha.tipo_processo == 'torno_cnc':
        return FolhaTornoCNC.query.filter_by(folha_processo_id=folha.id).first()
    elif folha.tipo_processo == 'centro_usinagem':
        return FolhaCentroUsinagem.query.filter_by(folha_processo_id=folha.id).first()
    elif folha.tipo_processo == 'corte_serra':
        return FolhaCorteSerraria.query.filter_by(folha_processo_id=folha.id).first()
    elif folha.tipo_processo == 'servicos_gerais':
        return FolhaServicosGerais.query.filter_by(folha_processo_id=folha.id).first()
    return None

def criar_copia_folha_especifica(nova_folha_id, folha_especifica_base):
    """Cria uma cópia da folha específica para uma nova versão"""
    if isinstance(folha_especifica_base, FolhaTornoCNC):
        return FolhaTornoCNC(
            folha_processo_id=nova_folha_id,
            codigo_item=folha_especifica_base.codigo_item,
            nome_peca=folha_especifica_base.nome_peca,
            responsavel_preenchimento=folha_especifica_base.responsavel_preenchimento,
            data_preenchimento=folha_especifica_base.data_preenchimento,
            revisao=folha_especifica_base.revisao,
            numero_programa=folha_especifica_base.numero_programa,
            codigo_programa=folha_especifica_base.codigo_programa,
            ferramenta_1=folha_especifica_base.ferramenta_1,
            ferramenta_2=folha_especifica_base.ferramenta_2,
            ferramenta_3=folha_especifica_base.ferramenta_3,
            ferramenta_4=folha_especifica_base.ferramenta_4,
            ferramenta_5=folha_especifica_base.ferramenta_5,
            ferramenta_6=folha_especifica_base.ferramenta_6,
            dimensao_critica_1=folha_especifica_base.dimensao_critica_1,
            dimensao_critica_2=folha_especifica_base.dimensao_critica_2,
            dimensao_critica_3=folha_especifica_base.dimensao_critica_3,
            velocidade_corte=folha_especifica_base.velocidade_corte,
            avanco=folha_especifica_base.avanco,
            rotacao=folha_especifica_base.rotacao,
            refrigeracao=folha_especifica_base.refrigeracao,
            observacoes_setup=folha_especifica_base.observacoes_setup,
            observacoes_operacao=folha_especifica_base.observacoes_operacao
        )
    elif isinstance(folha_especifica_base, FolhaCentroUsinagem):
        return FolhaCentroUsinagem(
            folha_processo_id=nova_folha_id,
            codigo_item=folha_especifica_base.codigo_item,
            nome_peca=folha_especifica_base.nome_peca,
            responsavel_tecnico=folha_especifica_base.responsavel_tecnico,
            # Copiar outros campos...
        )
    elif isinstance(folha_especifica_base, FolhaCorteSerraria):
        return FolhaCorteSerraria(
            folha_processo_id=nova_folha_id,
            codigo_item=folha_especifica_base.codigo_item,
            nome_peca=folha_especifica_base.nome_peca,
            operador_responsavel=folha_especifica_base.operador_responsavel,
            # Copiar outros campos...
        )
    elif isinstance(folha_especifica_base, FolhaServicosGerais):
        return FolhaServicosGerais(
            folha_processo_id=nova_folha_id,
            operador_responsavel=folha_especifica_base.operador_responsavel,
            # Copiar outros campos...
        )
    return None

# Verificação de permissão
@folhas_processo.before_request
def verificar_permissao():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('auth.login'))

@folhas_processo.route('/folhas-processo/item/<int:item_id>')
def listar_folhas(item_id):
    """Lista todas as folhas de processo de um item"""
    item = Item.query.get_or_404(item_id)
    folhas = FolhaProcesso.query.filter_by(item_id=item_id, ativo=True).order_by(
        FolhaProcesso.tipo_processo, FolhaProcesso.versao.desc()
    ).all()
    
    return render_template('folhas_processo/listar.html', item=item, folhas=folhas)

# ----------------------------- HISTÓRICO DE VERSÕES -----------------------------
@folhas_processo.route('/folhas-processo/historico/<int:item_id>')
def historico_folhas(item_id):
    """Exibe o histórico de versões de todas as folhas de processo de um item"""
    item = Item.query.get_or_404(item_id)

    # Buscar todas as folhas do item ordenadas por tipo e versão desc
    folhas = FolhaProcesso.query.filter_by(item_id=item_id).order_by(
        FolhaProcesso.tipo_processo, FolhaProcesso.versao.desc()
    ).all()

    # Agrupar em dicionário
    folhas_agrupadas: dict[str, list] = {}
    for folha in folhas:
        folhas_agrupadas.setdefault(folha.tipo_processo, []).append(folha)

    return render_template('folhas_processo/historico.html', item=item, folhas_agrupadas=folhas_agrupadas)

@folhas_processo.route('/folhas-processo/criar/<int:item_id>')
def criar_folha_form(item_id):
    """Exibe formulário para criar nova folha de processo"""
    item = Item.query.get_or_404(item_id)
    
    # Verificar os tipos de trabalho do item para sugerir tipos de folha
    tipos_trabalho = [t.categoria for t in item.trabalhos if t.categoria]
    tipos_folha_disponiveis = {
        'torno_cnc': 'Torno CNC',
        'centro_usinagem': 'Centro de Usinagem', 
        'corte_serra': 'Corte e Serra',
        'servicos_gerais': 'Serviços Gerais'
    }
    
    return render_template('folhas_processo/criar.html', 
                          item=item, 
                          tipos_folha=tipos_folha_disponiveis,
                          tipos_trabalho=tipos_trabalho)

@folhas_processo.route('/folhas-processo/criar', methods=['POST'])
def criar_folha():
    """Cria uma nova folha de processo"""
    try:
        item_id = request.form.get('item_id')
        tipo_processo = request.form.get('tipo_processo')
        
        if not item_id or not tipo_processo:
            flash('Item e tipo de processo são obrigatórios', 'danger')
            return redirect(request.referrer)
        
        item = Item.query.get_or_404(item_id)
        usuario = Usuario.query.get(session['usuario_id'])
        
        # Verificar se já existe uma folha ativa deste tipo
        folha_existente = FolhaProcesso.query.filter_by(
            item_id=item_id, 
            tipo_processo=tipo_processo, 
            ativo=True
        ).first()
        
        if folha_existente:
            # Desativar a folha anterior e criar nova versão
            folha_existente.ativo = False
            nova_versao = folha_existente.versao + 1
        else:
            nova_versao = 1
        
        # Criar folha base
        folha = FolhaProcesso(
            item_id=item_id,
            tipo_processo=tipo_processo,
            versao=nova_versao,
            criado_por=usuario.nome,
            responsavel=request.form.get('responsavel', usuario.nome),
            observacoes=request.form.get('observacoes')
        )
        
        db.session.add(folha)
        db.session.flush()  # Para obter o ID da folha
        
        # Criar folha específica baseada no tipo
        folha_especifica = None
        
        if tipo_processo == 'torno_cnc':
            folha_especifica = FolhaTornoCNC(
                folha_processo_id=folha.id,
                codigo_item=item.codigo_acb,
                nome_peca=item.nome,
                responsavel_preenchimento=usuario.nome
            )
        elif tipo_processo == 'centro_usinagem':
            folha_especifica = FolhaCentroUsinagem(
                folha_processo_id=folha.id,
                codigo_item=item.codigo_acb,
                nome_peca=item.nome,
                responsavel_tecnico=usuario.nome
            )
        elif tipo_processo == 'corte_serra':
            folha_especifica = FolhaCorteSerraria(
                folha_processo_id=folha.id,
                codigo_item=item.codigo_acb,
                nome_peca=item.nome,
                operador_responsavel=usuario.nome
            )
        elif tipo_processo == 'servicos_gerais':
            folha_especifica = FolhaServicosGerais(
                folha_processo_id=folha.id,
                codigo_item=item.codigo_acb,
                nome_peca=item.nome,
                operador_responsavel=usuario.nome
            )
        
        if folha_especifica:
            db.session.add(folha_especifica)
        
        db.session.commit()
        
        flash(f'Folha de processo {tipo_processo.replace("_", " ").title()} criada com sucesso!', 'success')
        return redirect(url_for('folhas_processo.editar_folha', folha_id=folha.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar folha de processo: {str(e)}', 'danger')
        return redirect(request.referrer)

@folhas_processo.route('/folhas-processo/editar/<int:folha_id>')
def editar_folha(folha_id):
    """Exibe formulário para editar folha de processo"""
    folha = FolhaProcesso.query.get_or_404(folha_id)
    item = folha.item
    
    # Buscar a folha específica baseada no tipo
    folha_especifica = None
    template_name = 'folhas_processo/editar_base.html'
    
    if folha.tipo_processo == 'torno_cnc':
        folha_especifica = FolhaTornoCNC.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/editar_torno_cnc.html'
    elif folha.tipo_processo == 'centro_usinagem':
        folha_especifica = FolhaCentroUsinagem.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/editar_centro_usinagem.html'
    elif folha.tipo_processo == 'corte_serra':
        folha_especifica = FolhaCorteSerraria.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/editar_corte_serra.html'
    elif folha.tipo_processo == 'servicos_gerais':
        folha_especifica = FolhaServicosGerais.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/editar_servicos_gerais.html'
    
    return render_template(template_name, 
                          folha=folha, 
                          folha_especifica=folha_especifica,
                          item=item)

@folhas_processo.route('/folhas-processo/salvar/<int:folha_id>', methods=['POST'])
def salvar_folha(folha_id):
    """Salva as alterações na folha de processo"""
    try:
        folha = FolhaProcesso.query.get_or_404(folha_id)
        
        # Atualizar campos básicos da folha
        folha.responsavel = request.form.get('responsavel', folha.responsavel)
        folha.observacoes = request.form.get('observacoes', folha.observacoes)
        folha.data_atualizacao = datetime.utcnow()
        
        # Atualizar folha específica baseada no tipo
        if folha.tipo_processo == 'torno_cnc':
            folha_especifica = FolhaTornoCNC.query.filter_by(folha_processo_id=folha_id).first()
            if folha_especifica:
                folha_especifica.quantidade = request.form.get('quantidade', type=int)
                folha_especifica.maquina_torno = request.form.get('maquina_torno')
                folha_especifica.tipo_fixacao = request.form.get('tipo_fixacao')
                folha_especifica.tipo_material = request.form.get('tipo_material')
                folha_especifica.programa_cnc = request.form.get('programa_cnc')
                folha_especifica.ferramentas_utilizadas = request.form.get('ferramentas_utilizadas')
                folha_especifica.operacoes_previstas = request.form.get('operacoes_previstas')
                folha_especifica.diametros_criticos = request.form.get('diametros_criticos')
                folha_especifica.comprimentos_criticos = request.form.get('comprimentos_criticos')
                folha_especifica.rpm_sugerido = request.form.get('rpm_sugerido')
                folha_especifica.avanco_sugerido = request.form.get('avanco_sugerido')
                folha_especifica.ponto_controle_dimensional = request.form.get('ponto_controle_dimensional')
                folha_especifica.observacoes_tecnicas = request.form.get('observacoes_tecnicas')
                folha_especifica.responsavel_preenchimento = request.form.get('responsavel_preenchimento')
        
        # Adicionar lógica similar para outros tipos de folha...
        elif folha.tipo_processo == 'centro_usinagem':
            folha_especifica = FolhaCentroUsinagem.query.filter_by(folha_processo_id=folha_id).first()
            if folha_especifica:
                folha_especifica.quantidade = request.form.get('quantidade', type=int)
                folha_especifica.maquina_centro = request.form.get('maquina_centro')
                folha_especifica.sistema_fixacao = request.form.get('sistema_fixacao')
                folha_especifica.z_zero_origem = request.form.get('z_zero_origem')
                folha_especifica.lista_ferramentas = request.form.get('lista_ferramentas')
                folha_especifica.operacoes = request.form.get('operacoes')
                folha_especifica.caminho_programa_cnc = request.form.get('caminho_programa_cnc')
                folha_especifica.ponto_critico_colisao = request.form.get('ponto_critico_colisao')
                folha_especifica.limitacoes = request.form.get('limitacoes')
                folha_especifica.tolerancias_especificas = request.form.get('tolerancias_especificas')
                folha_especifica.observacoes_engenharia = request.form.get('observacoes_engenharia')
                folha_especifica.responsavel_tecnico = request.form.get('responsavel_tecnico')
        
        elif folha.tipo_processo == 'corte_serra':
            folha_especifica = FolhaCorteSerraria.query.filter_by(folha_processo_id=folha_id).first()
            if folha_especifica:
                folha_especifica.quantidade_cortar = request.form.get('quantidade_cortar', type=int)
                folha_especifica.tipo_material = request.form.get('tipo_material')
                folha_especifica.tipo_serra = request.form.get('tipo_serra')
                folha_especifica.tamanho_bruto = request.form.get('tamanho_bruto')
                folha_especifica.tamanho_final_corte = request.form.get('tamanho_final_corte')
                folha_especifica.perda_esperada = request.form.get('perda_esperada')
                folha_especifica.tolerancia_permitida = request.form.get('tolerancia_permitida')
                folha_especifica.operador_responsavel = request.form.get('operador_responsavel')
                folha_especifica.observacoes_corte = request.form.get('observacoes_corte')
                # Data do corte
                data_corte_str = request.form.get('data_corte')
                if data_corte_str:
                    folha_especifica.data_corte = datetime.strptime(data_corte_str, '%Y-%m-%d').date()
        
        elif folha.tipo_processo == 'servicos_gerais':
            folha_especifica = FolhaServicosGerais.query.filter_by(folha_processo_id=folha_id).first()
            if folha_especifica:
                folha_especifica.processo_rebarba = request.form.get('processo_rebarba') == 'on'
                folha_especifica.processo_lavagem = request.form.get('processo_lavagem') == 'on'
                folha_especifica.processo_inspecao = request.form.get('processo_inspecao') == 'on'
                folha_especifica.ferramentas_utilizadas = request.form.get('ferramentas_utilizadas')
                folha_especifica.padrao_qualidade = request.form.get('padrao_qualidade')
                folha_especifica.itens_inspecionar = request.form.get('itens_inspecionar')
                folha_especifica.resultado_inspecao = request.form.get('resultado_inspecao')
                folha_especifica.motivo_reprovacao = request.form.get('motivo_reprovacao')
                folha_especifica.operador_responsavel = request.form.get('operador_responsavel')
                folha_especifica.observacoes_gerais = request.form.get('observacoes_gerais')
        
        db.session.commit()
        
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': True, 'message': 'Folha salva com sucesso!'})
        else:
            flash('Folha de processo salva com sucesso!', 'success')
            return redirect(url_for('folhas_processo.editar_folha', folha_id=folha_id))
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Erro ao salvar folha de processo: {str(e)}'
        
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'error': error_msg})
        else:
            flash(error_msg, 'danger')
            return redirect(request.referrer)

@folhas_processo.route('/folhas-processo/visualizar/<int:folha_id>')
def visualizar_folha(folha_id):
    """Visualiza uma folha de processo (modo somente leitura)"""
    folha = FolhaProcesso.query.get_or_404(folha_id)
    item = folha.item
    
    # Buscar a folha específica baseada no tipo
    folha_especifica = None
    template_name = 'folhas_processo/visualizar_base.html'
    
    if folha.tipo_processo == 'torno_cnc':
        folha_especifica = FolhaTornoCNC.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/visualizar_torno_cnc.html'
    elif folha.tipo_processo == 'centro_usinagem':
        folha_especifica = FolhaCentroUsinagem.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/visualizar_centro_usinagem.html'
    elif folha.tipo_processo == 'corte_serra':
        folha_especifica = FolhaCorteSerraria.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/visualizar_corte_serra.html'
    elif folha.tipo_processo == 'servicos_gerais':
        folha_especifica = FolhaServicosGerais.query.filter_by(folha_processo_id=folha_id).first()
        template_name = 'folhas_processo/visualizar_servicos_gerais.html'
    
    return render_template(template_name, 
                          folha=folha, 
                          folha_especifica=folha_especifica,
                          item=item,
                          readonly=True)
