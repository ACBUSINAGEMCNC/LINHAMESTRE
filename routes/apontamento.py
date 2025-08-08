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
        
        # Calcular última quantidade para validação do input de quantidade
        ultima_quantidade = None
        try:
            if status_atual and hasattr(status_atual, 'quantidade_atual') and status_atual.quantidade_atual is not None:
                ultima_quantidade = int(status_atual.quantidade_atual)
            else:
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
        if ultima_quantidade is None:
            ultima_quantidade = 0

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
            if not dados.get('quantidade'):
                return jsonify({'success': False, 'message': 'Quantidade é obrigatória para pausas'})
            if not dados.get('motivo_parada'):
                return jsonify({'success': False, 'message': 'Motivo da parada é obrigatório'})
        
        if tipo_acao == 'stop':
            if not dados.get('quantidade'):
                return jsonify({'success': False, 'message': 'Quantidade é obrigatória para stop'})
            if not dados.get('motivo_parada'):
                return jsonify({'success': False, 'message': 'Motivo da parada é obrigatório para stop'})
        
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
                
        elif tipo_acao == 'stop':
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
        
        if tipo_acao in ['fim_setup', 'fim_producao', 'pausa', 'stop']:
            # Determinar qual tipo de início procurar
            tipo_inicio = {
                'fim_setup': 'inicio_setup',
                'fim_producao': 'inicio_producao',
                'pausa': 'inicio_producao',
                'stop': 'inicio_producao'
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
            'stop': 'Stop',
            'fim_producao': 'Fim de produção'
        }.get(tipo_acao, tipo_acao)
        
        return jsonify({
            'success': True,
            'message': f'{acao_nome} registrado com sucesso!',
            'status': status_os.status_atual,
            'ultima_quantidade': int(status_os.quantidade_atual) if getattr(status_os, 'quantidade_atual', None) is not None else ultima_quantidade,
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
