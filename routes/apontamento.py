from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from models import db, Usuario, ApontamentoProducao, StatusProducaoOS, OrdemServico, ItemTrabalho, PedidoOrdemServico, Pedido, Item, Trabalho
from datetime import datetime
from sqlalchemy.orm import joinedload
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

@apontamento_bp.route('/dashboard')
def dashboard():
    """Dashboard de apontamentos (ORM)"""
    try:
        # Status ativos (exclui finalizados), com relações carregadas
        status_list = (
            StatusProducaoOS.query.options(
                joinedload(StatusProducaoOS.ordem_servico),
                joinedload(StatusProducaoOS.operador_atual),
                joinedload(StatusProducaoOS.trabalho_atual),
                joinedload(StatusProducaoOS.item_atual)
            )
            .filter(StatusProducaoOS.status_atual != 'Finalizado')
            .order_by(StatusProducaoOS.inicio_acao.desc())
            .all()
        )

        # Últimos apontamentos com OS e operador
        ultimos_apontamentos = (
            ApontamentoProducao.query.options(
                joinedload(ApontamentoProducao.ordem_servico),
                joinedload(ApontamentoProducao.usuario)
            )
            .order_by(ApontamentoProducao.data_hora.desc())
            .limit(10)
            .all()
        )

        return render_template(
            'apontamento/dashboard.html',
            status_ativos=status_list,
            ultimos_apontamentos=ultimos_apontamentos
        )
    except Exception as e:
        flash(f'Erro ao carregar dashboard: {e}', 'error')
        return render_template('apontamento/dashboard.html', status_ativos=[], ultimos_apontamentos=[])

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

                # Buscar número/identificador da OS
                try:
                    if status.ordem_servico_id:
                        os_obj = OrdemServico.query.get(status.ordem_servico_id)
                        if os_obj:
                            # Tente usar um campo de número/código se existir; caso não, use ID
                            os_num = getattr(os_obj, 'numero', None) or getattr(os_obj, 'codigo', None) or f"OS-{os_obj.id}"
                            status_info['os_numero'] = os_num
                except Exception as e_os:
                    print(f"[ERRO] Falha ao buscar numero da OS: {e_os}")
                
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
                
                # Adicionar quantidade atual e última quantidade apontada para este item/trabalho
                try:
                    if hasattr(status, 'quantidade_atual'):
                        status_info['quantidade_atual'] = status.quantidade_atual
                    ultima_q = None
                    if getattr(status, 'item_atual_id', None) and getattr(status, 'trabalho_atual_id', None):
                        ultimo_ap = ApontamentoProducao.query.filter(
                            ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                            ApontamentoProducao.item_id == status.item_atual_id,
                            ApontamentoProducao.trabalho_id == status.trabalho_atual_id,
                            ApontamentoProducao.quantidade != None
                        ).order_by(ApontamentoProducao.data_hora.desc()).first()
                        if ultimo_ap and ultimo_ap.quantidade is not None:
                            ultima_q = int(ultimo_ap.quantidade)
                    if ultima_q is None:
                        if hasattr(status, 'quantidade_atual') and status.quantidade_atual is not None:
                            ultima_q = int(status.quantidade_atual)
                    status_info['ultima_quantidade'] = ultima_q if ultima_q is not None else 0
                except Exception as e_q:
                    print(f"[ERRO] Falha ao calcular ultima_quantidade: {e_q}")
                
                # Adicionar timestamp de início da ação
                status_info['inicio_acao'] = status.inicio_acao.isoformat() if getattr(status, 'inicio_acao', None) else None

                # Mapear apontamentos ativos por (item, trabalho) para indicar múltiplos simultâneos
                try:
                    ativos = ApontamentoProducao.query.filter(
                        ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                        ApontamentoProducao.data_fim == None,
                        ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
                    ).order_by(ApontamentoProducao.data_hora.desc()).all()

                    ativos_info = []
                    vistos = set()
                    for ap in ativos:
                        chave = (ap.item_id, ap.trabalho_id)
                        if chave in vistos:
                            continue
                        vistos.add(chave)

                        # Coletar informações do item/trabalho
                        item_nome = None
                        item_codigo = None
                        trabalho_nome = None
                        try:
                            it = Item.query.get(ap.item_id) if ap.item_id else None
                            if it:
                                item_nome = getattr(it, 'nome', None)
                                item_codigo = getattr(it, 'codigo_acb', None)
                            tr = Trabalho.query.get(ap.trabalho_id) if ap.trabalho_id else None
                            if tr:
                                trabalho_nome = getattr(tr, 'nome', None)
                        except Exception:
                            pass

                        # Calcular última quantidade para este par (item,trabalho)
                        ultima_q_combo = 0
                        try:
                            ultimo_ap_combo = ApontamentoProducao.query.filter(
                                ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                ApontamentoProducao.item_id == ap.item_id,
                                ApontamentoProducao.trabalho_id == ap.trabalho_id,
                                ApontamentoProducao.quantidade != None
                            ).order_by(ApontamentoProducao.data_hora.desc()).first()
                            if ultimo_ap_combo and ultimo_ap_combo.quantidade is not None:
                                ultima_q_combo = int(ultimo_ap_combo.quantidade)
                        except Exception:
                            pass

                        # Operador e início
                        operador_nome = None
                        operador_codigo = None
                        operador_id = getattr(ap, 'operador_id', None) or getattr(ap, 'usuario_id', None)
                        try:
                            if operador_id:
                                op_user = Usuario.query.get(operador_id)
                                if op_user:
                                    operador_nome = getattr(op_user, 'nome', None)
                                    operador_codigo = getattr(op_user, 'codigo_operador', None)
                        except Exception:
                            pass

                        ativos_info.append({
                            'item_id': ap.item_id,
                            'item_codigo': item_codigo,
                            'item_nome': item_nome,
                            'trabalho_id': ap.trabalho_id,
                            'trabalho_nome': trabalho_nome,
                            'status': 'Setup em andamento' if ap.tipo_acao == 'inicio_setup' else ('Pausado' if ap.tipo_acao == 'pausa' else 'Produção em andamento'),
                            'inicio_acao': ap.data_hora.isoformat() if ap.data_hora else None,
                            'operador_id': operador_id,
                            'operador_nome': operador_nome,
                            'operador_codigo': operador_codigo,
                            'ultima_quantidade': ultima_q_combo,
                            # Motivo da pausa (somente quando tipo_acao == 'pausa')
                            'motivo_pausa': getattr(ap, 'motivo_parada', None) if ap.tipo_acao == 'pausa' else None
                        })

                    status_info['ativos_por_trabalho'] = ativos_info
                    status_info['qtd_ativos'] = len(ativos_info)
                    status_info['multiplo_ativos'] = len(ativos_info) > 1
                except Exception as e_mult:
                    print(f"[ERRO] Falha ao montar ativos_por_trabalho: {e_mult}")

                # Adicionar ao resultado
                resultado['status_ativos'].append(status_info)
            except Exception as e_status:
                print(f"[ERRO] Falha ao montar status_info para status ID {getattr(status, 'id', None)}: {e_status}")
                # Continua para o próximo status
                continue
        
        print(f"[DEBUG] Status ativos formatados: {len(resultado['status_ativos'])}")
        return jsonify(resultado)
    except Exception as e:
        print(f"[ERRO FATAL] Falha ao buscar status ativos: {e}")
        return jsonify({'error': str(e), 'message': 'Falha ao buscar status ativos'}), 500

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

        # Validar transições de estado (permitindo paralelismo por item/trabalho)
        # Consultas de apoio para verificar abertos por combinação
        def existe_inicio_aberto(os_id, item_id, trab_id, tipo_inicio):
            return ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == os_id,
                ApontamentoProducao.item_id == item_id,
                ApontamentoProducao.trabalho_id == trab_id,
                ApontamentoProducao.tipo_acao == tipo_inicio,
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first() is not None

        if tipo_acao == 'inicio_setup':
            # Bloquear somente se já houver um setup em andamento para MESMO item/trabalho
            if existe_inicio_aberto(dados['ordem_servico_id'], dados['item_id'], dados['trabalho_id'], 'inicio_setup'):
                return jsonify({
                    'success': False,
                    'message': 'Já existe um setup em andamento para este item/trabalho nesta OS.'
                })

        if tipo_acao == 'fim_setup':
            # Deve existir um início de setup aberto para este item/trabalho
            ap_setup = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == 'inicio_setup',
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            if not ap_setup:
                return jsonify({
                    'success': False,
                    'message': 'Não é possível finalizar setup sem ter iniciado setup para este item/trabalho.'
                })
            # Somente o mesmo operador pode finalizar
            if ap_setup.usuario_id != usuario.id:
                op = Usuario.query.get(ap_setup.usuario_id)
                return jsonify({
                    'success': False,
                    'message': f'Apenas o operador que iniciou o setup ({op.nome}) pode finalizá-lo.'
                })

        if tipo_acao == 'inicio_producao':
            # Não bloquear por existir outra produção em andamento na OS; bloquear apenas se mesma combinação já estiver ativa
            if existe_inicio_aberto(dados['ordem_servico_id'], dados['item_id'], dados['trabalho_id'], 'inicio_producao'):
                return jsonify({
                    'success': False,
                    'message': 'Já existe produção em andamento para este item/trabalho nesta OS.'
                })
            # Se houve início de setup para esta combinação e ainda não há fim_setup, exigir conclusão
            ap_setup_iniciado = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == 'inicio_setup'
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            if ap_setup_iniciado and ap_setup_iniciado.data_fim is None:
                return jsonify({
                    'success': False,
                    'message': 'Conclua o setup deste item/trabalho antes de iniciar a produção.'
                })

        if tipo_acao == 'pausa':
            # Deve existir uma produção em andamento para esta combinação
            ap_prod = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == 'inicio_producao',
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            if not ap_prod:
                return jsonify({'success': False, 'message': 'Não é possível pausar: não há produção em andamento para este item/trabalho.'})
            if ap_prod.usuario_id != usuario.id:
                op = Usuario.query.get(ap_prod.usuario_id)
                return jsonify({'success': False, 'message': f'Apenas o operador que iniciou a produção ({op.nome}) pode pausá-la.'})

        if tipo_acao == 'stop':
            # Pode parar produção em andamento, pausa aberta, ou setup em andamento para este par
            ap_prod = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == 'inicio_producao',
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            ap_pausa = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == 'pausa',
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            ap_setup = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == 'inicio_setup',
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()

            if not ap_prod and not ap_pausa and not ap_setup:
                return jsonify({'success': False, 'message': 'Não é possível aplicar STOP: não há apontamento ativo (produção/pausa/setup) para este item/trabalho.'})

            # Validar operador que abriu o apontamento ativo
            ap_base = ap_prod or ap_pausa or ap_setup
            if ap_base and ap_base.usuario_id != usuario.id:
                op = Usuario.query.get(ap_base.usuario_id)
                return jsonify({'success': False, 'message': f'Apenas o operador que iniciou ({op.nome}) pode aplicar STOP.'})

        if tipo_acao == 'fim_producao':
            # Deve existir uma produção em andamento para esta combinação
            ap_prod = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == 'inicio_producao',
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            if not ap_prod:
                return jsonify({'success': False, 'message': 'Não é possível finalizar: não há produção em andamento para este item/trabalho.'})
            if ap_prod.usuario_id != usuario.id:
                op = Usuario.query.get(ap_prod.usuario_id)
                return jsonify({'success': False, 'message': f'Apenas o operador que iniciou a produção ({op.nome}) pode finalizá-la.'})
        
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
        
        # Calcular última quantidade (independente por trabalho) para validação do input de quantidade
        ultima_quantidade = 0
        try:
            ultimo_ap = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.quantidade != None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            if ultimo_ap and ultimo_ap.quantidade is not None:
                ultima_quantidade = int(ultimo_ap.quantidade)
        except Exception as e_q:
            print(f"[ERRO] Falha ao obter última quantidade para validação: {e_q}")

        # Validação de quantidade mínima quando informada (início produção, pausa e fim produção)
        if dados.get('quantidade') is not None:
            try:
                qtd_informada = int(dados['quantidade'])
            except Exception:
                return jsonify({'success': False, 'message': 'Quantidade inválida'})
            if qtd_informada < ultima_quantidade:
                return jsonify({
                    'success': False,
                    'message': f'Quantidade informada ({qtd_informada}) menor que a última apontada ({ultima_quantidade}). Informe um valor maior ou igual.'
                })

        # Validações específicas por tipo de ação
        tipo_acao = dados['tipo_acao']
        if tipo_acao == 'pausa':
            # Pausa simples: sem obrigatoriedade de quantidade/motivo
            pass

        if tipo_acao == 'stop':
            # STOP simples: sem obrigatoriedade de quantidade/motivo
            pass
        
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
            # Se houver pausa aberta para este par, encerrá-la
            try:
                pausa_aberta = ApontamentoProducao.query.filter(
                    ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                    ApontamentoProducao.item_id == dados['item_id'],
                    ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                    ApontamentoProducao.tipo_acao == 'pausa',
                    ApontamentoProducao.data_fim == None
                ).order_by(ApontamentoProducao.data_hora.desc()).first()
                if pausa_aberta:
                    delta_pausa = agora - pausa_aberta.data_hora
                    pausa_aberta.data_fim = agora
                    pausa_aberta.tempo_decorrido = int(delta_pausa.total_seconds())
            except Exception:
                pass
                
        elif tipo_acao == 'pausa':
            status_os.status_atual = 'Pausado'
            status_os.operador_atual_id = usuario.id
            status_os.item_atual_id = dados['item_id']
            status_os.trabalho_atual_id = dados['trabalho_id']
            status_os.inicio_acao = agora
            status_os.motivo_parada = dados.get('motivo_parada')
            if dados.get('quantidade'):
                status_os.quantidade_atual = int(dados['quantidade'])
                
        elif tipo_acao == 'stop':
            status_os.status_atual = 'Aguardando'
            status_os.operador_atual_id = None
            status_os.item_atual_id = None
            status_os.trabalho_atual_id = None
            status_os.inicio_acao = None
            status_os.motivo_parada = None
                
        elif tipo_acao == 'fim_producao':
            status_os.status_atual = 'Finalizado'
            if dados.get('quantidade'):
                status_os.quantidade_atual = int(dados['quantidade'])
        
        # Verificar se é uma ação de finalização (fim_setup, fim_producao, pausa)
        # Se for, buscar o apontamento de início correspondente para calcular tempo decorrido
        tempo_decorrido = None
        data_fim = None
        apontamento_inicio = None
        
        if tipo_acao in ['fim_setup', 'fim_producao', 'stop']:
            # Determinar qual tipo de início procurar
            tipo_inicio = {
                'fim_setup': 'inicio_setup',
                'fim_producao': 'inicio_producao',
                'stop': 'inicio_producao'
            }.get(tipo_acao)
            
            # Buscar o último apontamento de início correspondente
            apontamento_inicio = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                ApontamentoProducao.item_id == dados['item_id'],
                ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                ApontamentoProducao.tipo_acao == tipo_inicio,
                ApontamentoProducao.data_fim == None
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            # Se STOP e não encontrou produção aberta, tentar encerrar setup aberto
            if tipo_acao == 'stop' and not apontamento_inicio:
                apontamento_inicio = ApontamentoProducao.query.filter(
                    ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                    ApontamentoProducao.item_id == dados['item_id'],
                    ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                    ApontamentoProducao.tipo_acao == 'inicio_setup',
                    ApontamentoProducao.data_fim == None
                ).order_by(ApontamentoProducao.data_hora.desc()).first()
            
            # Se encontrou, calcular tempo decorrido
            if apontamento_inicio:
                data_fim = agora
                delta = data_fim - apontamento_inicio.data_hora
                tempo_decorrido = int(delta.total_seconds())
                
                # Atualizar o apontamento de início com a data_fim
                apontamento_inicio.data_fim = data_fim
                apontamento_inicio.tempo_decorrido = tempo_decorrido

            # Se for STOP, também encerrar pausa e setup abertos para o mesmo par
            if tipo_acao == 'stop':
                try:
                    pausa_aberta = ApontamentoProducao.query.filter(
                        ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                        ApontamentoProducao.item_id == dados['item_id'],
                        ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                        ApontamentoProducao.tipo_acao == 'pausa',
                        ApontamentoProducao.data_fim == None
                    ).order_by(ApontamentoProducao.data_hora.desc()).first()
                    if pausa_aberta:
                        delta_pausa = agora - pausa_aberta.data_hora
                        pausa_aberta.data_fim = agora
                        pausa_aberta.tempo_decorrido = int(delta_pausa.total_seconds())
                    setup_aberto = ApontamentoProducao.query.filter(
                        ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                        ApontamentoProducao.item_id == dados['item_id'],
                        ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                        ApontamentoProducao.tipo_acao == 'inicio_setup',
                        ApontamentoProducao.data_fim == None
                    ).order_by(ApontamentoProducao.data_hora.desc()).first()
                    if setup_aberto:
                        delta_setup = agora - setup_aberto.data_hora
                        setup_aberto.data_fim = agora
                        setup_aberto.tempo_decorrido = int(delta_setup.total_seconds())
                except Exception:
                    pass
        
        # Criar registro de apontamento
        # Para 'pausa', criar como registro ABERTO (data_fim=None); para outros, manter padrão
        criar_data_fim = data_fim
        criar_tempo = tempo_decorrido
        if tipo_acao == 'pausa':
            # Encerrar o início de produção vigente (se ainda não encerrado acima)
            try:
                ap_inicio_prod = ApontamentoProducao.query.filter(
                    ApontamentoProducao.ordem_servico_id == dados['ordem_servico_id'],
                    ApontamentoProducao.item_id == dados['item_id'],
                    ApontamentoProducao.trabalho_id == dados['trabalho_id'],
                    ApontamentoProducao.tipo_acao == 'inicio_producao',
                    ApontamentoProducao.data_fim == None
                ).order_by(ApontamentoProducao.data_hora.desc()).first()
                if ap_inicio_prod:
                    ap_inicio_prod.data_fim = agora
                    ap_inicio_prod.tempo_decorrido = int((agora - ap_inicio_prod.data_hora).total_seconds())
            except Exception:
                pass
            criar_data_fim = None
            criar_tempo = None
        elif tipo_acao == 'stop':
            # Garantir que o evento STOP não fique aberto
            if not criar_data_fim:
                criar_data_fim = agora
                criar_tempo = 0

        apontamento = ApontamentoProducao(
            ordem_servico_id=dados['ordem_servico_id'],
            usuario_id=usuario.id,
            operador_id=usuario.id,  # Salvar operador_id para facilitar consultas
            item_id=dados['item_id'],
            trabalho_id=dados['trabalho_id'],
            tipo_acao=tipo_acao,
            data_hora=agora,
            data_fim=criar_data_fim,  # Para pausa permanece aberto; para finais usa data_fim calculado
            quantidade=int(dados['quantidade']) if dados.get('quantidade') else None,
            motivo_parada=dados.get('motivo_parada'),
            observacoes=dados.get('observacoes'),
            tempo_decorrido=criar_tempo,  # Salvar tempo decorrido se calculado
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
            'stop': 'Stop',
            'fim_producao': 'Fim de produção'
        }.get(tipo_acao, tipo_acao)
        
        return jsonify({
            'success': True,
            'message': f'{acao_nome} registrado com sucesso!',
            'status': status_os.status_atual,
            'ultima_quantidade': ultima_quantidade,
            'quantidade_atual': int(status_os.quantidade_atual) if getattr(status_os, 'quantidade_atual', None) is not None else None
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao registrar apontamento: {str(e)}'
        })

@apontamento_bp.route('/os/<int:os_id>/logs/view')
def logs_ordem_servico(os_id):
    """Visualizar logs de apontamento de uma ordem de serviço (HTML)"""
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
                'observacoes': apontamento.observacoes if hasattr(apontamento, 'observacoes') else None,
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
