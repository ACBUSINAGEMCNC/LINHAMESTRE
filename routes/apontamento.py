from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from models import db, Usuario, ApontamentoProducao, StatusProducaoOS, OrdemServico, ItemTrabalho, PedidoOrdemServico, Pedido, Item, Trabalho
from datetime import datetime
import random
import string

apontamento_bp = Blueprint('apontamento', __name__)

@apontamento_bp.route('/operadores')
def listar_operadores():
    """Lista todos os operadores e seus códigos"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Verificar se usuário tem acesso
    usuario_atual = Usuario.query.get(session['user_id'])
    if not usuario_atual or (usuario_atual.nivel_acesso not in ['admin'] and not usuario_atual.acesso_cadastros):
        flash('Acesso negado. Apenas administradores podem gerenciar códigos de operador.', 'error')
        return redirect(url_for('main.index'))
    
    # Buscar todos os usuários
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    
    return render_template('apontamento/operadores.html', usuarios=usuarios)

@apontamento_bp.route('/operadores/gerar-codigo/<int:usuario_id>', methods=['POST'])
def gerar_codigo_operador(usuario_id):
    """Gera um código de 4 dígitos para um operador"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado'})
    
    # Verificar permissões
    usuario_atual = Usuario.query.get(session['user_id'])
    if not usuario_atual or (usuario_atual.nivel_acesso not in ['admin'] and not usuario_atual.acesso_cadastros):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # Gerar código único de 4 dígitos
    codigo = gerar_codigo_unico()
    if not codigo:
        return jsonify({'success': False, 'message': 'Não foi possível gerar um código único'})
    
    usuario.codigo_operador = codigo
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Código {codigo} gerado para {usuario.nome}',
        'codigo': codigo
    })

@apontamento_bp.route('/operadores/definir-codigo/<int:usuario_id>', methods=['POST'])
def definir_codigo_operador(usuario_id):
    """Define um código personalizado para um operador"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado'})
    
    # Verificar permissões
    usuario_atual = Usuario.query.get(session['user_id'])
    if not usuario_atual or (usuario_atual.nivel_acesso not in ['admin'] and not usuario_atual.acesso_cadastros):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    codigo = request.json.get('codigo', '').strip()
    
    # Validar código
    if not codigo or len(codigo) != 4 or not codigo.isdigit():
        return jsonify({'success': False, 'message': 'Código deve ter exatamente 4 dígitos'})
    
    # Verificar se código já existe
    if Usuario.query.filter(Usuario.codigo_operador == codigo, Usuario.id != usuario_id).first():
        return jsonify({'success': False, 'message': 'Este código já está em uso'})
    
    usuario = Usuario.query.get_or_404(usuario_id)
    usuario.codigo_operador = codigo
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Código {codigo} definido para {usuario.nome}',
        'codigo': codigo
    })

@apontamento_bp.route('/operadores/remover-codigo/<int:usuario_id>', methods=['POST'])
def remover_codigo_operador(usuario_id):
    """Remove o código de um operador"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado'})
    
    # Verificar permissões
    usuario_atual = Usuario.query.get(session['user_id'])
    if not usuario_atual or (usuario_atual.nivel_acesso not in ['admin'] and not usuario_atual.acesso_cadastros):
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    usuario = Usuario.query.get_or_404(usuario_id)
    codigo_anterior = usuario.codigo_operador
    usuario.codigo_operador = None
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Código {codigo_anterior} removido de {usuario.nome}'
    })

@apontamento_bp.route('/validar-codigo', methods=['POST'])
def validar_codigo():
    """Valida um código de operador (para uso nos modais de apontamento)"""
    codigo = request.json.get('codigo', '').strip()
    
    if not codigo or len(codigo) != 4 or not codigo.isdigit():
        return jsonify({'valid': False, 'message': 'Código deve ter 4 dígitos'})
    
    usuario = Usuario.query.filter_by(codigo_operador=codigo).first()
    
    if not usuario:
        return jsonify({'valid': False, 'message': 'Código não encontrado'})
    
    return jsonify({
        'valid': True, 
        'usuario_id': usuario.id,
        'nome': usuario.nome,
        'message': f'Operador: {usuario.nome}'
    })

@apontamento_bp.route('/os/<int:ordem_id>/itens', methods=['GET'])
def buscar_itens_os(ordem_id):
    """Busca todos os itens de uma ordem de serviço"""
    try:
        # Buscar a ordem de serviço
        ordem_servico = OrdemServico.query.get_or_404(ordem_id)
        
        # Buscar todos os itens desta OS
        itens = db.session.query(Item).join(
            Pedido, Item.id == Pedido.item_id
        ).join(
            PedidoOrdemServico, Pedido.id == PedidoOrdemServico.pedido_id
        ).filter(
            PedidoOrdemServico.ordem_servico_id == ordem_id
        ).distinct().all()
        
        # Converter para formato JSON
        itens_json = []
        for item in itens:
            itens_json.append({
                'id': item.id,
                'nome': item.nome,
                'codigo_acb': item.codigo_acb
            })
        
        return jsonify({
            'success': True,
            'itens': itens_json
        })
        
    except Exception as e:
        print(f"Erro ao buscar itens para OS {ordem_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar itens: {str(e)}'
        }), 500

@apontamento_bp.route('/item/<int:item_id>/tipos-trabalho', methods=['GET'])
def buscar_tipos_trabalho_item(item_id):
    """Busca os tipos de trabalho vinculados a um item específico"""
    try:
        # Buscar o item
        item = Item.query.get_or_404(item_id)
        
        # Buscar tipos de trabalho específicos deste item
        tipos_trabalho = db.session.query(Trabalho).join(
            ItemTrabalho, Trabalho.id == ItemTrabalho.trabalho_id
        ).filter(
            ItemTrabalho.item_id == item_id
        ).all()
        
        # Se não encontrou tipos específicos para este item, retornar erro
        if not tipos_trabalho:
            return jsonify({
                'success': False,
                'message': f'Nenhum tipo de trabalho cadastrado para o item {item.codigo_acb}. Configure os tipos de trabalho na página de edição do item.'
            }), 404
        
        # Converter para formato JSON
        tipos_json = []
        for tipo in tipos_trabalho:
            tipos_json.append({
                'id': tipo.id,
                'nome': tipo.nome,
                'descricao': tipo.descricao or ''
            })
        
        return jsonify({
            'success': True,
            'tipos_trabalho': tipos_json
        })
        
    except Exception as e:
        print(f"Erro ao buscar tipos de trabalho para item {item_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar tipos de trabalho: {str(e)}'
        }), 500

@apontamento_bp.route('/os/<int:ordem_id>/tipos-trabalho', methods=['GET'])
def buscar_tipos_trabalho_os(ordem_id):
    """Busca os tipos de trabalho vinculados aos itens de uma ordem de serviço (DEPRECIADO - usar por item)"""
    try:
        # Buscar a ordem de serviço
        ordem_servico = OrdemServico.query.get_or_404(ordem_id)
        
        # Buscar todos os tipos de trabalho únicos vinculados aos itens desta OS
        tipos_trabalho = db.session.query(Trabalho).join(
            ItemTrabalho, Trabalho.id == ItemTrabalho.trabalho_id
        ).join(
            Item, ItemTrabalho.item_id == Item.id
        ).join(
            Pedido, Item.id == Pedido.item_id
        ).join(
            PedidoOrdemServico, Pedido.id == PedidoOrdemServico.pedido_id
        ).filter(
            PedidoOrdemServico.ordem_servico_id == ordem_id
        ).distinct().all()
        
        # Se não encontrou tipos de trabalho específicos, retornar erro
        if not tipos_trabalho:
            return jsonify({
                'success': False,
                'message': f'Nenhum tipo de trabalho cadastrado para os itens desta OS. Configure os tipos de trabalho na página de edição dos itens.'
            })
        
        # Converter para formato JSON
        tipos_json = []
        for tipo in tipos_trabalho:
            tipos_json.append({
                'id': tipo.id,
                'nome': tipo.nome,
                'descricao': tipo.descricao or ''
            })
        
        return jsonify({
            'success': True,
            'tipos_trabalho': tipos_json
        })
        
    except Exception as e:
        print(f"Erro ao buscar tipos de trabalho para OS {ordem_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar tipos de trabalho: {str(e)}'
        }), 500

def gerar_codigo_unico():
    """Gera um código único de 4 dígitos"""
    max_tentativas = 100
    
    for _ in range(max_tentativas):
        # Gerar código de 4 dígitos (0001 a 9999)
        codigo = f"{random.randint(1, 9999):04d}"
        
        # Verificar se já existe
        if not Usuario.query.filter_by(codigo_operador=codigo).first():
            return codigo
    
    return None

@apontamento_bp.route('/status-ativos', methods=['GET'])
def status_ativos():
    """Retorna todos os status de produção ativos para apontamentos (usado para persistência frontend)"""
    try:
        # Buscar todos os status ativos de produção
        print("[DEBUG] Buscando status ativos...")
        status_ativos = StatusProducaoOS.query.filter(
            StatusProducaoOS.status_atual != 'Finalizado'
        ).all()
        
        print(f"[DEBUG] Encontrados {len(status_ativos)} status ativos")
        
        # Formatar resposta
        resultado = {
            'status_ativos': []
        }
        
        # Adicionar informações detalhadas para cada status
        for status in status_ativos:
            try:
                status_info = {
                    'id': status.id,
                    'ordem_servico_id': status.ordem_servico_id,
                    'ordem_id': status.ordem_servico_id,  # Mantido para compatibilidade com frontend
                    'status_atual': status.status_atual or 'Desconhecido'
                }
                
                # Buscar operador atual
                try:
                    if hasattr(status, 'operador_atual_id') and status.operador_atual_id:
                        operador = Usuario.query.get(status.operador_atual_id)
                        if operador:
                            status_info['operador_id'] = operador.id
                            status_info['operador_nome'] = operador.nome
                            status_info['operador_codigo'] = operador.codigo_operador
                    elif hasattr(status, 'operador_id') and status.operador_id:
                        operador = Usuario.query.get(status.operador_id)
                        if operador:
                            status_info['operador_id'] = operador.id
                            status_info['operador_nome'] = operador.nome
                            status_info['operador_codigo'] = operador.codigo_operador
                except Exception as e_op:
                    print(f"[ERRO] Falha ao buscar operador: {e_op}")
                
                # Buscar item atual
                try:
                    if hasattr(status, 'item_atual_id') and status.item_atual_id:
                        item = Item.query.get(status.item_atual_id)
                        if item:
                            status_info['item_id'] = item.id
                            status_info['item_nome'] = item.nome
                            status_info['item_codigo'] = item.codigo_acb
                except Exception as e_item:
                    print(f"[ERRO] Falha ao buscar item: {e_item}")
                
                # Buscar trabalho atual
                try:
                    if hasattr(status, 'trabalho_atual_id') and status.trabalho_atual_id:
                        trabalho = Trabalho.query.get(status.trabalho_atual_id)
                        if trabalho:
                            status_info['trabalho_id'] = trabalho.id
                            status_info['trabalho_nome'] = trabalho.nome
                except Exception as e_trab:
                    print(f"[ERRO] Falha ao buscar trabalho: {e_trab}")
                
                # Adicionar timestamp de início da ação
                status_info['inicio_acao'] = status.inicio_acao.isoformat() if status.inicio_acao else None
                
                # Adicionar ao resultado
                resultado['status_ativos'].append(status_info)
            except Exception as e_status:
                print(f"[ERRO] Falha ao processar status {status.id}: {e_status}")
        
        print(f"[DEBUG] Status ativos formatados: {len(resultado['status_ativos'])}")
        return jsonify(resultado)
    except Exception as e:
        print(f"[ERRO FATAL] Falha ao buscar status ativos: {e}")
        return jsonify({'error': str(e), 'message': 'Falha ao buscar status ativos'}), 500

@apontamento_bp.route('/dashboard')
def dashboard():
    """Dashboard com cartões ativos e status de apontamento"""
    try:
        # Buscar todos os status ativos de produção
        status_ativos = StatusProducaoOS.query.filter(
            StatusProducaoOS.status_atual != 'Finalizado'
        ).all()
        
        # Buscar últimos apontamentos
        ultimos_apontamentos = ApontamentoProducao.query.order_by(
            ApontamentoProducao.data_hora.desc()
        ).limit(10).all()
        
        # Adicionar informações detalhadas para cada status ativo
        for status in status_ativos:
            # Buscar ordem, operador e item relacionados
            if status.ordem_id:
                status.ordem = OrdemServico.query.get(status.ordem_id)
            
            if status.operador_id:
                status.operador = Usuario.query.get(status.operador_id)
            
            if status.item_atual_id:
                status.item_atual = Item.query.get(status.item_atual_id)
                
            if status.trabalho_atual_id:
                status.trabalho_atual = Trabalho.query.get(status.trabalho_atual_id)
                
            # Buscar o último apontamento para este status
            ultimo_apontamento = ApontamentoProducao.query.filter_by(
                ordem_id=status.ordem_id
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            
            if ultimo_apontamento:
                status.ultimo_apontamento = ultimo_apontamento
        
        # Adicionar informações detalhadas para cada apontamento
        for ap in ultimos_apontamentos:
            if ap.operador_id:
                ap.operador = Usuario.query.get(ap.operador_id)
            
            if ap.ordem_id:
                ap.ordem = OrdemServico.query.get(ap.ordem_id)
                
            if ap.item_id:
                ap.item = Item.query.get(ap.item_id)
                
            if ap.trabalho_id:
                ap.trabalho = Trabalho.query.get(ap.trabalho_id)
        
        return render_template('apontamento/dashboard.html', 
                             status_ativos=status_ativos,
                             ultimos_apontamentos=ultimos_apontamentos)
    except Exception as e:
        flash(f'Erro ao carregar dashboard: {str(e)}', 'error')
        return redirect(url_for('main.index'))
        


@apontamento_bp.route('/os/<int:ordem_id>/logs')
def logs_apontamento(ordem_id):
    """Retorna os logs de apontamento para uma OS específica"""
    try:
        # Buscar todos os apontamentos para a OS
        print(f"[DEBUG] Buscando logs para OS {ordem_id}")
        apontamentos = ApontamentoProducao.query.filter_by(ordem_servico_id=ordem_id).order_by(
            ApontamentoProducao.data_hora.desc()
        ).all()
        
        print(f"[DEBUG] Encontrados {len(apontamentos)} apontamentos")
        
        resultado = {
            'logs': []
        }
        
        # Formatar dados para JSON
        for ap in apontamentos:
            try:
                data_hora_str = ''
                if ap.data_hora:
                    data_hora_str = ap.data_hora.strftime('%Y-%m-%dT%H:%M:%S')
                
                # Verificar se atributos existem antes de acessá-los (para compatibilidade com registros antigos)
                motivo_pausa = ''
                try:
                    if hasattr(ap, 'motivo_pausa') and ap.motivo_pausa:
                        motivo_pausa = ap.motivo_pausa
                except Exception:
                    pass
                    
                # Verificar data_fim para cálculo de duração
                data_fim_str = ''
                if hasattr(ap, 'data_fim') and ap.data_fim:
                    data_fim_str = ap.data_fim.strftime('%Y-%m-%dT%H:%M:%S')
                    
                log = {
                    'id': ap.id,
                    'tipo_acao': ap.tipo_acao or '',
                    'data_hora': data_hora_str,
                    'data_fim': data_fim_str,
                    'quantidade': ap.quantidade if hasattr(ap, 'quantidade') and ap.quantidade is not None else 0,
                    'motivo_pausa': motivo_pausa,
                    'operador_id': ap.operador_id if hasattr(ap, 'operador_id') else None,
                    'operador_nome': None,
                    'operador_codigo': None,
                    'ordem_servico_id': ap.ordem_servico_id,
                    'ordem_id': ap.ordem_servico_id,  # Mantendo ordem_id para compatibilidade
                    'item_id': ap.item_id if hasattr(ap, 'item_id') else None,
                    'item_nome': None,
                    'trabalho_id': ap.trabalho_id if hasattr(ap, 'trabalho_id') else None,
                    'trabalho_nome': None,
                    'trabalho_descricao': None
                }
                
                # Adicionar informações do operador, se existir
                try:
                    if hasattr(ap, 'operador_id') and ap.operador_id:
                        try:
                            operador = Usuario.query.get(ap.operador_id)
                            if operador:
                                log['operador_codigo'] = operador.codigo_operador
                                log['operador_nome'] = operador.nome
                        except Exception as e_op:
                            print(f"[ERRO] Falha ao buscar operador {ap.operador_id}: {e_op}")
                except Exception as e:
                    print(f"[ERRO] Falha ao verificar operador para apontamento {ap.id}: {e}")
                
                # Adicionar informações do item, se existir
                if ap.item_id:
                    try:
                        item = Item.query.get(ap.item_id)
                        if item:
                            log['item_nome'] = item.nome
                    except Exception as e_item:
                        print(f"[ERRO] Falha ao buscar item {ap.item_id}: {e_item}")
                
                # Adicionar informações do trabalho, se existir
                if ap.trabalho_id:
                    try:
                        trabalho = Trabalho.query.get(ap.trabalho_id)
                        if trabalho:
                            log['trabalho_descricao'] = trabalho.descricao
                    except Exception as e_trab:
                        print(f"[ERRO] Falha ao buscar trabalho {ap.trabalho_id}: {e_trab}")
                
                resultado['logs'].append(log)
            except Exception as e_log:
                print(f"[ERRO] Falha ao processar apontamento {ap.id}: {e_log}")
        
        return jsonify(resultado)
    except Exception as e:
        print(f"[ERRO FATAL] Falha ao carregar logs: {str(e)}")
        return jsonify({'error': str(e), 'message': 'Falha ao carregar logs de apontamento'}), 500

@apontamento_bp.route('/os/<int:ordem_id>/tipos-trabalho')
def tipos_trabalho_os(ordem_id):
    """Retorna os tipos de trabalho disponíveis para uma OS"""
    try:
        # Buscar a ordem de serviço
        ordem = OrdemServico.query.get_or_404(ordem_id)
        
        # Buscar os itens de trabalho associados à OS
        itens_trabalho = ItemTrabalho.query.filter_by(ordem_servico_id=ordem_id).all()
        
        tipos_trabalho = []
        for item in itens_trabalho:
            tipos_trabalho.append({
                'id': item.id,
                'nome': item.nome or f'Item {item.id}',
                'tempo_setup': item.tempo_setup,
                'tempo_peca': item.tempo_peca
            })
        
        return jsonify({
            'success': True,
            'tipos_trabalho': tipos_trabalho
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar tipos de trabalho: {str(e)}'
        })

@apontamento_bp.route('/registrar', methods=['POST'])
def registrar_apontamento():
    """Registra um novo apontamento de produção"""
    try:
        dados = request.get_json()
        
        # Validar dados obrigatórios
        if not dados.get('ordem_servico_id'):
            return jsonify({'success': False, 'message': 'OS é obrigatória'})
        
        if not dados.get('tipo_acao'):
            return jsonify({'success': False, 'message': 'Tipo de ação é obrigatório'})
        
        if not dados.get('codigo_operador'):
            return jsonify({'success': False, 'message': 'Código do operador é obrigatório'})
        
        if not dados.get('item_id'):
            return jsonify({'success': False, 'message': 'Item é obrigatório'})
        
        if not dados.get('trabalho_id'):
            return jsonify({'success': False, 'message': 'Tipo de trabalho é obrigatório'})
        
        # Validar código do operador
        usuario = Usuario.query.filter_by(codigo_operador=dados['codigo_operador']).first()
        if not usuario:
            return jsonify({'success': False, 'message': 'Código de operador inválido'})

        # Buscar status atual da OS para validar transições de estado
        status_atual = StatusProducaoOS.query.filter_by(ordem_servico_id=dados['ordem_servico_id']).first()
        tipo_acao = dados['tipo_acao']

        # Validar transições de estado
        if status_atual:
            # Verificar transições inválidas
            if tipo_acao == 'inicio_setup':
                if status_atual.status_atual in ['Setup em andamento', 'Produção em andamento']:
                    return jsonify({
                        'success': False, 
                        'message': f'Não é possível iniciar setup enquanto há uma operação em andamento. É necessário pausar ou finalizar antes.'
                    })
                # Verificar se o operador atual é diferente do solicitado
                if status_atual.operador_atual_id and status_atual.operador_atual_id != usuario.id:
                    operador_atual = Usuario.query.get(status_atual.operador_atual_id)
                    return jsonify({
                        'success': False,
                        'message': f'Esta OS já está sendo trabalhada pelo operador {operador_atual.nome} (código {operador_atual.codigo_operador}). Finalize a operação atual primeiro.'
                    })
            
            if tipo_acao == 'fim_setup':
                if status_atual.status_atual != 'Setup em andamento':
                    return jsonify({
                        'success': False, 
                        'message': 'Não é possível finalizar setup sem ter iniciado setup.'
                    })
                # Verificar se o operador atual é o mesmo que iniciou
                if status_atual.operador_atual_id and status_atual.operador_atual_id != usuario.id:
                    operador_atual = Usuario.query.get(status_atual.operador_atual_id)
                    return jsonify({
                        'success': False,
                        'message': f'Apenas o operador que iniciou o setup ({operador_atual.nome}) pode finalizá-lo.'
                    })
            
            if tipo_acao == 'inicio_producao':
                if status_atual.status_atual == 'Produção em andamento':
                    return jsonify({
                        'success': False, 
                        'message': 'Não é possível iniciar produção enquanto já há uma produção em andamento. É necessário pausar ou finalizar antes.'
                    })
                # Verificar se o setup foi concluído (se necessário)
                if status_atual.status_atual not in ['Setup concluído', 'Pausado', 'Aguardando']:
                    return jsonify({
                        'success': False,
                        'message': 'É necessário concluir o setup antes de iniciar a produção.'
                    })
            
            if tipo_acao == 'pausa':
                if status_atual.status_atual not in ['Setup em andamento', 'Produção em andamento']:
                    return jsonify({
                        'success': False, 
                        'message': 'Não é possível pausar sem ter uma operação em andamento.'
                    })
                # Verificar se o operador atual é o mesmo que iniciou
                if status_atual.operador_atual_id and status_atual.operador_atual_id != usuario.id:
                    operador_atual = Usuario.query.get(status_atual.operador_atual_id)
                    return jsonify({
                        'success': False,
                        'message': f'Apenas o operador que iniciou a operação ({operador_atual.nome}) pode pausá-la.'
                    })
            
            if tipo_acao == 'fim_producao':
                if status_atual.status_atual != 'Produção em andamento':
                    return jsonify({
                        'success': False, 
                        'message': 'Não é possível finalizar produção sem ter iniciado produção.'
                    })
                # Verificar se o operador atual é o mesmo que iniciou
                if status_atual.operador_atual_id and status_atual.operador_atual_id != usuario.id:
                    operador_atual = Usuario.query.get(status_atual.operador_atual_id)
                    return jsonify({
                        'success': False,
                        'message': f'Apenas o operador que iniciou a produção ({operador_atual.nome}) pode finalizá-la.'
                    })
        
        # Validar se a OS existe
        ordem = OrdemServico.query.get(dados['ordem_servico_id'])
        if not ordem:
            return jsonify({'success': False, 'message': 'Ordem de serviço não encontrada'})
        
        # Validar se o item existe
        item = Item.query.get(dados['item_id'])
        if not item:
            return jsonify({'success': False, 'message': 'Item não encontrado'})
        
        # Validar se o tipo de trabalho existe
        trabalho = Trabalho.query.get(dados['trabalho_id'])
        if not trabalho:
            return jsonify({'success': False, 'message': 'Tipo de trabalho não encontrado'})
        
        # Validar se o tipo de trabalho está vinculado ao item
        item_trabalho = ItemTrabalho.query.filter_by(
            item_id=dados['item_id'],
            trabalho_id=dados['trabalho_id']
        ).first()
        if not item_trabalho:
            return jsonify({
                'success': False, 
                'message': f'O tipo de trabalho "{trabalho.nome}" não está vinculado ao item "{item.codigo_acb}"'
            })
        
        # Validações específicas por tipo de ação
        tipo_acao = dados['tipo_acao']
        if tipo_acao == 'pausa':
            if not dados.get('quantidade'):
                return jsonify({'success': False, 'message': 'Quantidade é obrigatória para pausas'})
            if not dados.get('motivo_parada'):
                return jsonify({'success': False, 'message': 'Motivo da parada é obrigatório'})
        
        if tipo_acao == 'fim_producao':
            if not dados.get('quantidade'):
                return jsonify({'success': False, 'message': 'Quantidade final é obrigatória'})
        
        # Buscar ou criar status da OS
        status_os = StatusProducaoOS.query.filter_by(ordem_servico_id=dados['ordem_servico_id']).first()
        if not status_os:
            status_os = StatusProducaoOS(
                ordem_servico_id=dados['ordem_servico_id'],
                status_atual='Aguardando',
                operador_atual_id=usuario.id
            )
            db.session.add(status_os)
        
        # Atualizar status baseado na ação
        agora = datetime.now()
        
        if tipo_acao == 'inicio_setup':
            status_os.status_atual = 'Setup em andamento'
            status_os.operador_atual_id = usuario.id
            status_os.item_atual_id = dados['item_id']
            status_os.trabalho_atual_id = dados['trabalho_id']
            status_os.inicio_acao = agora
            
        elif tipo_acao == 'fim_setup':
            status_os.status_atual = 'Setup concluído'
            
        elif tipo_acao == 'inicio_producao':
            status_os.status_atual = 'Produção em andamento'
            status_os.operador_atual_id = usuario.id
            status_os.item_atual_id = dados['item_id']
            status_os.trabalho_atual_id = dados['trabalho_id']
            status_os.inicio_acao = agora
            if dados.get('quantidade'):
                status_os.quantidade_atual = int(dados['quantidade'])
                
        elif tipo_acao == 'pausa':
            status_os.status_atual = 'Pausado'
            status_os.motivo_parada = dados['motivo_parada']
            if dados.get('quantidade'):
                status_os.quantidade_atual = int(dados['quantidade'])
                
        elif tipo_acao == 'fim_producao':
            status_os.status_atual = 'Finalizado'
            if dados.get('quantidade'):
                status_os.quantidade_atual = int(dados['quantidade'])
        
        # Verificar se é uma ação de finalização (fim_setup, fim_producao, pausa)
        # Se for, buscar o apontamento de início correspondente para calcular tempo decorrido
        tempo_decorrido = None
        data_fim = None
        apontamento_inicio = None
        
        if tipo_acao in ['fim_setup', 'fim_producao', 'pausa']:
            # Determinar qual tipo de início procurar
            tipo_inicio = {
                'fim_setup': 'inicio_setup',
                'fim_producao': 'inicio_producao',
                'pausa': 'inicio_producao'
            }.get(tipo_acao)
            
            # Buscar o último apontamento de início correspondente
            apontamento_inicio = ApontamentoProducao.query.filter_by(
                ordem_servico_id=dados['ordem_servico_id'],
                tipo_acao=tipo_inicio
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            
            # Se encontrou, calcular tempo decorrido
            if apontamento_inicio:
                data_fim = agora
                delta = data_fim - apontamento_inicio.data_hora
                tempo_decorrido = int(delta.total_seconds())
                
                # Atualizar o apontamento de início com a data_fim
                apontamento_inicio.data_fim = data_fim
                apontamento_inicio.tempo_decorrido = tempo_decorrido
        
        # Criar registro de apontamento
        apontamento = ApontamentoProducao(
            ordem_servico_id=dados['ordem_servico_id'],
            usuario_id=usuario.id,
            operador_id=usuario.id,  # Salvar operador_id para facilitar consultas
            item_id=dados['item_id'],
            trabalho_id=dados['trabalho_id'],
            tipo_acao=tipo_acao,
            data_hora=agora,
            data_fim=data_fim,  # Salvar data_fim se for uma ação de finalização
            quantidade=int(dados['quantidade']) if dados.get('quantidade') else None,
            motivo_parada=dados.get('motivo_parada'),
            observacoes=dados.get('observacoes'),
            tempo_decorrido=tempo_decorrido,  # Salvar tempo decorrido se calculado
            lista_kanban=ordem.status  # Status atual da OS no Kanban
        )
        
        db.session.add(apontamento)
        db.session.commit()
        
        # Preparar mensagem de sucesso
        acao_nome = {
            'inicio_setup': 'Início de setup',
            'fim_setup': 'Fim de setup',
            'inicio_producao': 'Início de produção',
            'pausa': 'Pausa',
            'fim_producao': 'Fim de produção'
        }.get(tipo_acao, tipo_acao)
        
        return jsonify({
            'success': True,
            'message': f'{acao_nome} registrado com sucesso!',
            'status': status_os.status_atual
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao registrar apontamento: {str(e)}'
        })

@apontamento_bp.route('/os/<int:os_id>/logs')
def logs_ordem_servico(os_id):
    """Visualizar logs de apontamento de uma ordem de serviço"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    ordem_servico = OrdemServico.query.get_or_404(os_id)
    
    # Buscar todos os apontamentos desta OS
    apontamentos = ApontamentoProducao.query.filter_by(
        ordem_servico_id=os_id
    ).order_by(ApontamentoProducao.data_hora.desc()).all()
    
    # Buscar status atual
    status = StatusProducaoOS.query.filter_by(ordem_servico_id=os_id).first()
    
    return render_template('apontamento/logs_os.html', 
                         ordem_servico=ordem_servico,
                         apontamentos=apontamentos,
                         status=status)

@apontamento_bp.route('/os/<int:ordem_id>/logs', methods=['GET'])
def get_logs_ordem_servico(ordem_id):
    """Retorna logs de apontamento de uma ordem de serviço em formato JSON"""
    try:
        # Buscar todos os apontamentos desta OS
        apontamentos = ApontamentoProducao.query.filter_by(
            ordem_servico_id=ordem_id
        ).order_by(ApontamentoProducao.data_hora.desc()).all()
        
        logs = []
        for apontamento in apontamentos:
            log_info = {
                'id': apontamento.id,
                'tipo_acao': apontamento.tipo_acao,
                'data_hora': apontamento.data_hora.isoformat() if apontamento.data_hora else None,
                'data_fim': apontamento.data_fim.isoformat() if hasattr(apontamento, 'data_fim') and apontamento.data_fim else None,
                'quantidade': apontamento.quantidade,
                'motivo_pausa': apontamento.motivo_parada if hasattr(apontamento, 'motivo_parada') else None,
                'tempo_decorrido': apontamento.tempo_decorrido,
                'lista_kanban': apontamento.lista_kanban
            }
            
            # Adicionar informações do operador
            try:
                if hasattr(apontamento, 'operador_id') and apontamento.operador_id:
                    operador = Usuario.query.get(apontamento.operador_id)
                    if operador:
                        log_info['operador_id'] = operador.id
                        log_info['operador_nome'] = operador.nome
                        log_info['operador_codigo'] = operador.codigo_operador
                elif apontamento.usuario_id:
                    usuario = Usuario.query.get(apontamento.usuario_id)
                    if usuario:
                        log_info['operador_id'] = usuario.id
                        log_info['operador_nome'] = usuario.nome
                        log_info['operador_codigo'] = usuario.codigo_operador
            except Exception as e_op:
                print(f"[ERRO] Falha ao buscar operador para log {apontamento.id}: {e_op}")
            
            # Adicionar informações do item
            try:
                if apontamento.item_id:
                    item = Item.query.get(apontamento.item_id)
                    if item:
                        log_info['item_id'] = item.id
                        log_info['item_nome'] = item.nome
                        log_info['item_codigo'] = item.codigo_acb
            except Exception as e_item:
                print(f"[ERRO] Falha ao buscar item para log {apontamento.id}: {e_item}")
            
            # Adicionar informações do trabalho
            try:
                if apontamento.trabalho_id:
                    trabalho = Trabalho.query.get(apontamento.trabalho_id)
                    if trabalho:
                        log_info['trabalho_id'] = trabalho.id
                        log_info['trabalho_nome'] = trabalho.nome
            except Exception as e_trab:
                print(f"[ERRO] Falha ao buscar trabalho para log {apontamento.id}: {e_trab}")
            
            logs.append(log_info)
        
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        print(f"[ERRO] Falha ao buscar logs de apontamento para OS {ordem_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar logs de apontamento: {str(e)}'
        }), 500
