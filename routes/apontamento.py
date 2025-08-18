from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from models import db, Usuario, ApontamentoProducao, StatusProducaoOS, OrdemServico, ItemTrabalho, PedidoOrdemServico, Pedido, Item, Trabalho, KanbanLista, CartaoFantasma
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import joinedload
import logging
import random
import string
import time

apontamento_bp = Blueprint('apontamento', __name__)
logger = logging.getLogger(__name__)
# Timezone helpers
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    # Fallback to fixed -03:00 (Brazil currently no DST)
    LOCAL_TZ = timezone(timedelta(hours=-3))
UTC = timezone.utc

def to_brt_iso(dt):
    """Convert a datetime to America/Sao_Paulo ISO string with offset.
    Assumes naive datetimes are in UTC (as stored), then converts to local tz.
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    try:
        return dt.astimezone(LOCAL_TZ).isoformat()
    except Exception:
        return dt.isoformat()

@apontamento_bp.route('/operadores')
def listar_operadores():
    """Lista todos os operadores e seus códigos"""
    if 'usuario_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Verificar se usuário tem acesso
    usuario_atual = Usuario.query.get(session['usuario_id'])
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

        # Listas Kanban ativas para filtros no dashboard
        listas_kanban = KanbanLista.query.filter_by(ativa=True).order_by(KanbanLista.ordem).all()

        return render_template(
            'apontamento/dashboard.html',
            status_ativos=status_list,
            ultimos_apontamentos=ultimos_apontamentos,
            listas_kanban=listas_kanban
        )
    except Exception as e:
        flash(f'Erro ao carregar dashboard: {e}', 'error')
        return render_template('apontamento/dashboard.html', status_ativos=[], ultimos_apontamentos=[], listas_kanban=[])

@apontamento_bp.route('/operadores/gerar-codigo/<int:usuario_id>', methods=['POST'])
def gerar_codigo_operador(usuario_id):
    """Gera um código de 4 dígitos para um operador"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado'})
    
    # Verificar permissões
    usuario_atual = Usuario.query.get(session['usuario_id'])
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
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado'})
    
    # Verificar permissões
    usuario_atual = Usuario.query.get(session['usuario_id'])
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
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado'})
    
    # Verificar permissões
    usuario_atual = Usuario.query.get(session['usuario_id'])
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
        logger.exception(f"Erro ao buscar itens para OS {ordem_id}: {e}")
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
        logger.exception(f"Erro ao buscar tipos de trabalho para item {item_id}: {e}")
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
        logger.exception(f"Erro ao buscar tipos de trabalho para OS {ordem_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar tipos de trabalho: {str(e)}'
        }), 500

@apontamento_bp.route('/detalhes/<int:ordem_id>', methods=['GET'])
def detalhes_os(ordem_id):
    """Detalhes resumidos de uma OS para QPT: lista de trabalhos e última quantidade apontada por trabalho."""
    try:
        # Confirmar existência da OS e pré-carregar itens -> trabalhos
        os_obj = (
            OrdemServico.query.options(
                joinedload(OrdemServico.pedidos)
                    .joinedload(PedidoOrdemServico.pedido)
                    .joinedload(Pedido.item)
                    .joinedload(Item.trabalhos)
                    .joinedload(ItemTrabalho.trabalho)
            ).get_or_404(ordem_id)
        )
        # Coletar todos os trabalhos potenciais a partir dos itens da OS
        trabalhos_map = {}  # trabalho_id -> {'trabalho_id': id, 'trabalho_nome': nome, 'ultima_quantidade': 0}
        for po in getattr(os_obj, 'pedidos', []) or []:
            ped = getattr(po, 'pedido', None)
            item = getattr(ped, 'item', None) if ped else None
            if not item:
                continue
            for it in getattr(item, 'trabalhos', []) or []:
                tb = getattr(it, 'trabalho', None)
                if not tb:
                    continue
                tid = getattr(tb, 'id', None)
                if not tid:
                    continue
                if tid not in trabalhos_map:
                    trabalhos_map[tid] = {
                        'trabalho_id': tid,
                        'trabalho_nome': getattr(tb, 'nome', f'Trabalho #{tid}'),
                        'ultima_quantidade': 0
                    }
        # Incluir também quaisquer trabalhos que já tiveram apontamento nesta OS (mesmo que não estejam nos itens)
        try:
            ap_trabalhos = db.session.query(ApontamentoProducao.trabalho_id).filter(
                ApontamentoProducao.ordem_servico_id == ordem_id,
                ApontamentoProducao.trabalho_id != None
            ).distinct().all()
            for row in ap_trabalhos:
                tid = row[0]
                if tid and tid not in trabalhos_map:
                    tb = Trabalho.query.get(tid)
                    trabalhos_map[tid] = {
                        'trabalho_id': tid,
                        'trabalho_nome': getattr(tb, 'nome', f'Trabalho #{tid}') if tb else f'Trabalho #{tid}',
                        'ultima_quantidade': 0
                    }
        except Exception:
            pass

        # Buscar última quantidade por trabalho
        for tid in list(trabalhos_map.keys()):
            try:
                ultimo_ap = (ApontamentoProducao.query
                    .filter(
                        ApontamentoProducao.ordem_servico_id == ordem_id,
                        ApontamentoProducao.trabalho_id == tid,
                        ApontamentoProducao.quantidade != None
                    )
                    .order_by(ApontamentoProducao.data_hora.desc())
                    .first())
                if ultimo_ap and ultimo_ap.quantidade is not None:
                    trabalhos_map[tid]['ultima_quantidade'] = int(ultimo_ap.quantidade)
            except Exception:
                continue

        trabalhos_list = sorted(trabalhos_map.values(), key=lambda t: (t.get('trabalho_nome') or '').lower())
        return jsonify({
            'success': True,
            'ordem_servico_id': ordem_id,
            'trabalhos': trabalhos_list
        })
    except Exception as e:
        logger.exception(f"Erro ao obter detalhes da OS {ordem_id}: {e}")
        return jsonify({'success': False, 'message': f'Erro ao obter detalhes: {str(e)}'}), 500

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
        t_start = time.perf_counter()
        timings = {}
        # Query params (opcionais) para filtragem
        lista_filter = None
        if request.args.get('lista') and request.args.get('lista').strip() and request.args.get('lista').strip().lower() != 'todas':
            lista_filter = request.args.get('lista').strip().lower()
            
        lista_tipo_filter = None
        if request.args.get('lista_tipo') and request.args.get('lista_tipo').strip():
            lista_tipo_filter = request.args.get('lista_tipo').strip().lower()
            
        status_filter_raw = request.args.get('status', '').strip().lower()
        status_filter_set = None
        if status_filter_raw and status_filter_raw != 'todos':
            status_filter_set = set([s.strip() for s in status_filter_raw.split(',') if s.strip()])

        # Buscar TODAS as listas Kanban ativas para garantir que apareçam no dashboard
        logger.debug("Buscando todas as listas Kanban ativas...")
        t0 = time.perf_counter()
        listas_kanban = KanbanLista.query.filter_by(ativa=True).all()
        timings['listas_kanban_query_ms'] = int((time.perf_counter() - t0) * 1000)
        logger.debug(f"Encontradas {len(listas_kanban)} listas Kanban ativas")
        # Mapas auxiliares para normalização de nomes (case-insensitive)
        nomes_listas = [lista.nome for lista in listas_kanban]
        nomes_listas_lower = [lista.nome.strip().lower() for lista in listas_kanban]
        map_lista_por_lower = {lista.nome.strip().lower(): lista for lista in listas_kanban}
        
        # Construir mapa de cartões fantasma por OS para mesclar na resposta
        logger.debug("Buscando cartões fantasma ativos para mesclagem...")
        t0 = time.perf_counter()
        ghost_por_os = {}
        try:
            cartoes_fantasma_all = (
                CartaoFantasma.query.options(
                    joinedload(CartaoFantasma.ordem_servico)
                        .joinedload(OrdemServico.pedidos)
                        .joinedload(PedidoOrdemServico.pedido)
                        .joinedload(Pedido.cliente),
                    joinedload(CartaoFantasma.ordem_servico)
                        .joinedload(OrdemServico.pedidos)
                        .joinedload(PedidoOrdemServico.pedido)
                        .joinedload(Pedido.item)
                        .joinedload(Item.trabalhos)
                        .joinedload(ItemTrabalho.trabalho),
                    joinedload(CartaoFantasma.trabalho),
                    joinedload(CartaoFantasma.criado_por)
                )
                .filter(CartaoFantasma.ativo == True)
                .all()
            )
            for cf in cartoes_fantasma_all:
                try:
                    os_id = getattr(cf, 'ordem_servico_id', None)
                    if not os_id:
                        continue
                    lista_cf = (getattr(cf, 'lista_kanban', None) or '').strip()
                    lista_cf_lower = lista_cf.lower() if lista_cf else None
                    kl_cf = map_lista_por_lower.get(lista_cf_lower) if lista_cf_lower else None
                    info_cf = {
                        'id': cf.id,
                        'lista_kanban': lista_cf or None,
                        'lista_tipo': getattr(kl_cf, 'tipo_servico', None) if kl_cf else None,
                        'lista_cor': getattr(kl_cf, 'cor', None) if kl_cf else None,
                        'trabalho_id': getattr(cf, 'trabalho_id', None),
                        'trabalho_nome': getattr(getattr(cf, 'trabalho', None), 'nome', None) if getattr(cf, 'trabalho', None) else None,
                        'posicao_fila': getattr(cf, 'posicao_fila', None),
                        'observacoes': getattr(cf, 'observacoes', None),
                        'criado_por_id': getattr(getattr(cf, 'criado_por', None), 'id', None) if getattr(cf, 'criado_por', None) else None,
                        'criado_por_nome': getattr(getattr(cf, 'criado_por', None), 'nome', None) if getattr(cf, 'criado_por', None) else None,
                        'data_criacao': cf.data_criacao.isoformat() if getattr(cf, 'data_criacao', None) else None,
                    }
                    bucket = ghost_por_os.setdefault(os_id, {
                        'cards': [],
                        'listas_lower': set(),
                        'tipos_lower': set(),
                        'trabalhos_ids': set(),
                    })
                    bucket['cards'].append(info_cf)
                    if lista_cf_lower:
                        bucket['listas_lower'].add(lista_cf_lower)
                        if kl_cf and getattr(kl_cf, 'tipo_servico', None):
                            bucket['tipos_lower'].add(str(kl_cf.tipo_servico).strip().lower())
                    trab_id_cf = getattr(cf, 'trabalho_id', None)
                    if trab_id_cf:
                        bucket['trabalhos_ids'].add(trab_id_cf)
                except Exception as e_cf_it:
                    logger.error(f"Falha ao processar cartão fantasma para OS {getattr(cf, 'ordem_servico_id', None)}: {e_cf_it}")
                    continue
        except Exception as e_cf:
            logger.error(f"Falha ao buscar cartões fantasma para mesclagem: {e_cf}")
        timings['ghost_cards_query_ms'] = int((time.perf_counter() - t0) * 1000)
        
        # Buscar todos os status ativos de produção
        logger.debug("Buscando status ativos...")
        t0 = time.perf_counter()
        status_ativos = (
            StatusProducaoOS.query.options(
                joinedload(StatusProducaoOS.ordem_servico)
                    .joinedload(OrdemServico.pedidos)
                    .joinedload(PedidoOrdemServico.pedido)
                    .joinedload(Pedido.cliente),
                joinedload(StatusProducaoOS.ordem_servico)
                    .joinedload(OrdemServico.pedidos)
                    .joinedload(PedidoOrdemServico.pedido)
                    .joinedload(Pedido.item)
                    .joinedload(Item.trabalhos)
                    .joinedload(ItemTrabalho.trabalho),
                joinedload(StatusProducaoOS.operador_atual),
                joinedload(StatusProducaoOS.trabalho_atual),
                joinedload(StatusProducaoOS.item_atual),
            )
            .filter(StatusProducaoOS.status_atual != 'Finalizado')
            .all()
        )
        timings['status_ativos_query_ms'] = int((time.perf_counter() - t0) * 1000)

        logger.debug(f"Encontrados {len(status_ativos)} status ativos (pré-filtro)")
        for status in status_ativos:
            logger.debug(f"Status ativo encontrado: ID={status.id}, ordem_servico_id={status.ordem_servico_id}, status_atual='{status.status_atual}'")
        
        # Buscar TODAS as OS que estão em máquinas (mesmo sem apontamento ativo)
        logger.debug("Buscando todas as OS em máquinas...")
        logger.debug(f"Nomes das listas Kanban: {nomes_listas}")
        
        # Uso de comparação case-insensitive para evitar divergências de caixa
        t0 = time.perf_counter()
        todas_os_em_maquinas = (
            OrdemServico.query.options(
                joinedload(OrdemServico.pedidos)
                    .joinedload(PedidoOrdemServico.pedido)
                    .joinedload(Pedido.cliente),
                joinedload(OrdemServico.pedidos)
                    .joinedload(PedidoOrdemServico.pedido)
                    .joinedload(Pedido.item)
                    .joinedload(Item.trabalhos)
                    .joinedload(ItemTrabalho.trabalho),
            )
            .filter(db.func.lower(db.func.trim(OrdemServico.status)).in_(nomes_listas_lower))
            .all()
        )
        timings['os_em_maquinas_query_ms'] = int((time.perf_counter() - t0) * 1000)
        logger.debug(f"Encontradas {len(todas_os_em_maquinas)} OS em máquinas")
        
        # Debug: mostrar todas as OS encontradas
        for os in todas_os_em_maquinas:
            logger.debug(f"OS encontrada: {getattr(os, 'numero', None) or getattr(os, 'codigo', None) or f'OS-{os.id}'} - Status: {getattr(os, 'status', None)}")
        
        # Debug: buscar TODAS as OS independente do status para comparar
        todas_os_sistema = OrdemServico.query.all()
        logger.debug(f"Total de OS no sistema: {len(todas_os_sistema)}")
        for os in todas_os_sistema:
            logger.debug(f"OS sistema: {getattr(os, 'numero', None) or getattr(os, 'codigo', None) or f'OS-{os.id}'} - Status: {getattr(os, 'status', None)}")
        
        # Formatar resposta
        resultado = {
            'status_ativos': []
        }
        
        # Criar um mapa de OS que já têm status ativo
        os_com_status_ativo = set()
        
        # Adicionar informações detalhadas para cada status ativo
        t0 = time.perf_counter()
        for status in status_ativos:
            logger.debug(f"Iniciando processamento do status ID={status.id}, ordem_servico_id={status.ordem_servico_id}")
            try:
                status_info = {
                    'id': status.id,
                    'ordem_servico_id': status.ordem_servico_id,
                    'ordem_id': status.ordem_servico_id,  # Mantido para compatibilidade com frontend
                    'status_atual': status.status_atual or 'Desconhecido'
                }

                # Buscar número/identificador da OS e agregar clientes/quantidades usando relações pre-carregadas
                try:
                    os_obj = getattr(status, 'ordem_servico', None)
                    if os_obj:
                        os_num = getattr(os_obj, 'numero', None) or getattr(os_obj, 'codigo', None) or f"OS-{os_obj.id}"
                        status_info['os_numero'] = os_num
                        # Clientes e quantidade total (agregar todos os pedidos vinculados à OS)
                        try:
                            clientes_map = {}
                            total_q = 0
                            for po in getattr(os_obj, 'pedidos', []) or []:
                                ped = getattr(po, 'pedido', None)
                                if not ped:
                                    continue
                                q = int(getattr(ped, 'quantidade', 0) or 0)
                                total_q += q
                                cli = getattr(ped, 'cliente', None)
                                nome_cli = getattr(cli, 'nome', None) or 'Cliente'
                                clientes_map[nome_cli] = clientes_map.get(nome_cli, 0) + q
                            status_info['quantidade_total'] = int(total_q)
                            if clientes_map:
                                status_info['clientes_quantidades'] = [
                                    {'cliente_nome': k, 'quantidade': v} for k, v in clientes_map.items()
                                ]
                                # Compatibilidade: primeiro cliente
                                status_info['cliente_nome'] = next(iter(clientes_map.keys()))
                        except Exception as e_cli:
                            logger.error(f"Falha ao agregar clientes/quantidades: {e_cli}")
                except Exception as e_os:
                    logger.error(f"Falha ao obter OS relacionada: {e_os}")
                
                # Buscar operador atual (pré-carregado)
                try:
                    operador = getattr(status, 'operador_atual', None)
                    if not operador and hasattr(status, 'operador_id') and status.operador_id:
                        operador = Usuario.query.get(status.operador_id)
                    if operador:
                        status_info['operador_id'] = operador.id
                        status_info['operador_nome'] = operador.nome
                        status_info['operador_codigo'] = getattr(operador, 'codigo_operador', None)
                except Exception as e_op:
                    logger.error(f"Falha ao buscar operador: {e_op}")
                
                # Buscar item atual
                try:
                    item_encontrado = False
                    
                    # Primeira tentativa: usar item_atual_id se disponível
                    if getattr(status, 'item_atual', None):
                        item = status.item_atual
                        if item:
                            status_info['item_id'] = item.id
                            status_info['item_nome'] = item.nome
                            status_info['item_codigo'] = item.codigo_acb
                            # Caminho da imagem do item para exibição no dashboard
                            status_info['item_imagem_path'] = getattr(item, 'imagem_path', None)
                            logger.debug(f"Status {status.id}: item encontrado via item_atual_id - nome='{item.nome}', imagem='{getattr(item, 'imagem_path', None)}'")
                            item_encontrado = True
                        else:
                            logger.debug(f"Status {status.id}: item com ID {status.item_atual_id} não encontrado no banco")
                    else:
                        logger.debug(f"Status {status.id}: sem item_atual_id definido")
                    
                    # Fallback: buscar via OS → Pedido → Item se não encontrou item_atual_id
                    if not item_encontrado:
                        logger.debug(f"Status {status.id}: tentando fallback via OS → Pedido → Item")
                        os_obj_fallback = getattr(status, 'ordem_servico', None)
                        if os_obj_fallback and getattr(os_obj_fallback, 'pedidos', None):
                            pedido_os = os_obj_fallback.pedidos[0]
                            pedido = getattr(pedido_os, 'pedido', None)
                            item = getattr(pedido, 'item', None) if pedido else None
                            if item:
                                status_info['item_id'] = item.id
                                status_info['item_nome'] = item.nome
                                status_info['item_codigo'] = item.codigo_acb
                                status_info['item_imagem_path'] = getattr(item, 'imagem_path', None)
                                logger.debug(f"Status {status.id}: item encontrado via fallback - nome='{item.nome}', imagem='{getattr(item, 'imagem_path', None)}'")
                                item_encontrado = True
                        
                        if not item_encontrado:
                            logger.debug(f"Status {status.id}: nenhum item encontrado (nem via item_atual_id nem via fallback)")
                    
                except Exception as e_item:
                    logger.error(f"Status {status.id}: falha ao buscar item: {e_item}")
                
                # Buscar trabalho atual (pré-carregado)
                try:
                    trabalho = getattr(status, 'trabalho_atual', None)
                    if trabalho:
                        status_info['trabalho_id'] = trabalho.id
                        status_info['trabalho_nome'] = trabalho.nome
                except Exception as e_trab:
                    logger.error(f"Falha ao buscar trabalho: {e_trab}")
                
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
                    logger.error(f"Falha ao calcular ultima_quantidade: {e_q}")
                
                # Adicionar timestamp de início da ação
                status_info['inicio_acao'] = to_brt_iso(getattr(status, 'inicio_acao', None))

                # Analytics por OS/item/trabalho para o Dashboard
                try:
                    analytics = {
                        'tempo_setup_estimado': None,
                        'tempo_setup_utilizado': None,
                        'setup_status': None,
                        'tempo_peca_estimado': None,
                        'tempo_producao_utilizado': None,
                        'tempo_pausas_utilizado': None,
                        'media_seg_por_peca': None,
                        'producao_status': None
                    }

                    cronometro = {
                        'tipo': None,
                        'inicio': None
                    }

                    tolerancia = 0.15  # 15%
                    agora_utc = datetime.utcnow()

                    if getattr(status, 'item_atual_id', None) and getattr(status, 'trabalho_atual_id', None):
                        # Estimativas do ItemTrabalho
                        try:
                            it_rel = ItemTrabalho.query.filter_by(
                                item_id=status.item_atual_id,
                                trabalho_id=status.trabalho_atual_id
                            ).first()
                            if it_rel:
                                analytics['tempo_setup_estimado'] = int(it_rel.tempo_setup) if it_rel.tempo_setup else None
                                analytics['tempo_peca_estimado'] = int(it_rel.tempo_peca) if it_rel.tempo_peca else None
                        except Exception:
                            pass

                        # Setup: calcular tempo utilizado (último ciclo)
                        try:
                            inicio_setup = ApontamentoProducao.query.filter(
                                ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                ApontamentoProducao.item_id == status.item_atual_id,
                                ApontamentoProducao.trabalho_id == status.trabalho_atual_id,
                                ApontamentoProducao.tipo_acao == 'inicio_setup'
                            ).order_by(ApontamentoProducao.data_hora.desc()).first()
                            tempo_setup_util = None
                            if inicio_setup:
                                fim_setup = ApontamentoProducao.query.filter(
                                    ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                    ApontamentoProducao.item_id == status.item_atual_id,
                                    ApontamentoProducao.trabalho_id == status.trabalho_atual_id,
                                    ApontamentoProducao.tipo_acao == 'fim_setup',
                                    ApontamentoProducao.data_hora > inicio_setup.data_hora
                                ).order_by(ApontamentoProducao.data_hora.asc()).first()
                                if fim_setup:
                                    tempo_setup_util = int((fim_setup.data_hora - inicio_setup.data_hora).total_seconds())
                                else:
                                    tempo_setup_util = int((agora_utc - inicio_setup.data_hora).total_seconds())
                                analytics['tempo_setup_utilizado'] = max(0, tempo_setup_util)
                                # Status de setup
                                if analytics['tempo_setup_estimado']:
                                    est = analytics['tempo_setup_estimado']
                                    usado = analytics['tempo_setup_utilizado']
                                    if usado <= est * (1 - tolerancia):
                                        analytics['setup_status'] = 'Excelente'
                                    elif usado <= est * (1 + tolerancia):
                                        analytics['setup_status'] = 'Dentro do esperado'
                                    else:
                                        analytics['setup_status'] = 'Abaixo do esperado'
                        except Exception as e_set:
                            logger.error(f"Analytics setup: {e_set}")

                        # Produção: calcular tempo de produção + pausas desde o último início
                        try:
                            inicio_prod = ApontamentoProducao.query.filter(
                                ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                ApontamentoProducao.item_id == status.item_atual_id,
                                ApontamentoProducao.trabalho_id == status.trabalho_atual_id,
                                ApontamentoProducao.tipo_acao == 'inicio_producao'
                            ).order_by(ApontamentoProducao.data_hora.desc()).first()

                            tempo_producao_util = 0
                            tempo_pausa_util = 0

                            if inicio_prod:
                                # Verificar se há pausa aberta após esse início
                                pausa_aberta = ApontamentoProducao.query.filter(
                                    ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                    ApontamentoProducao.item_id == status.item_atual_id,
                                    ApontamentoProducao.trabalho_id == status.trabalho_atual_id,
                                    ApontamentoProducao.tipo_acao.in_(['pausa', 'stop']),
                                    ApontamentoProducao.data_hora >= inicio_prod.data_hora,
                                    ApontamentoProducao.data_fim == None
                                ).order_by(ApontamentoProducao.data_hora.desc()).first()

                                if pausa_aberta:
                                    # produção até início da pausa + tempo da pausa até agora
                                    tempo_producao_util = int((pausa_aberta.data_hora - inicio_prod.data_hora).total_seconds())
                                    tempo_pausa_util = int((agora_utc - pausa_aberta.data_hora).total_seconds())
                                    cronometro['tipo'] = 'pausa'
                                    cronometro['inicio'] = to_brt_iso(pausa_aberta.data_hora)
                                else:
                                    # verificar se produção ainda aberta
                                    fim_prod = ApontamentoProducao.query.filter(
                                        ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                        ApontamentoProducao.item_id == status.item_atual_id,
                                        ApontamentoProducao.trabalho_id == status.trabalho_atual_id,
                                        ApontamentoProducao.tipo_acao == 'inicio_producao',
                                        ApontamentoProducao.data_fim == None
                                    ).order_by(ApontamentoProducao.data_hora.desc()).first()
                                    if fim_prod:
                                        tempo_producao_util = int((agora_utc - inicio_prod.data_hora).total_seconds())
                                        cronometro['tipo'] = 'producao'
                                        cronometro['inicio'] = to_brt_iso(inicio_prod.data_hora)
                                    else:
                                        # produção encerrada; usar último tempo_decorrido se disponível
                                        tempo_producao_util = int(getattr(inicio_prod, 'tempo_decorrido', 0) or 0)

                            analytics['tempo_producao_utilizado'] = max(0, tempo_producao_util)
                            analytics['tempo_pausas_utilizado'] = max(0, tempo_pausa_util)

                            # Cronômetro de setup se em setup
                            if status.status_atual == 'Setup em andamento' and not cronometro['tipo']:
                                if 'inicio_acao' in status_info and status_info['inicio_acao']:
                                    cronometro['tipo'] = 'setup'
                                    # status_info['inicio_acao'] já está em BRT ISO
                                    cronometro['inicio'] = status_info['inicio_acao']

                            # Média por peça
                            qtd = status_info.get('ultima_quantidade') or 0
                            total_seg = (analytics['tempo_producao_utilizado'] or 0) + (analytics['tempo_pausas_utilizado'] or 0)
                            if qtd and total_seg:
                                media = int(total_seg / max(qtd, 1))
                                analytics['media_seg_por_peca'] = media
                                if analytics['tempo_peca_estimado']:
                                    estp = analytics['tempo_peca_estimado']
                                    if media <= estp * (1 - tolerancia):
                                        analytics['producao_status'] = 'Excelente'
                                    elif media <= estp * (1 + tolerancia):
                                        analytics['producao_status'] = 'Dentro do esperado'
                                    else:
                                        analytics['producao_status'] = 'Abaixo do esperado'
                        except Exception as e_prod:
                            logger.error(f"Analytics produção: {e_prod}")

                    status_info['analytics'] = analytics
                    status_info['cronometro'] = cronometro
                except Exception as e_an:
                    logger.error(f"Falha ao montar analytics do status {getattr(status,'id',None)}: {e_an}")

                # Nome da lista Kanban atual (ex.: MAZAK, GLM, SERRA) e normalização/canonização
                try:
                    # Primeiro, tentar buscar da OS atual se estiver em uma máquina
                    os_obj = OrdemServico.query.get(status.ordem_servico_id) if status.ordem_servico_id else None
                    nome_lista_raw = None
                    
                    if os_obj and hasattr(os_obj, 'status') and getattr(os_obj, 'status'):
                        os_status = getattr(os_obj, 'status')
                        # Verificar se o status da OS corresponde a uma lista Kanban conhecida
                        if os_status.strip().lower() in map_lista_por_lower:
                            nome_lista_raw = os_status
                            logger.debug(f"Status {status.id}: usando status da OS '{os_status}' como lista_kanban")
                    
                    # Se não conseguiu da OS, buscar do último apontamento
                    if not nome_lista_raw:
                        ap_last_list = ApontamentoProducao.query.filter(
                            ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                            ApontamentoProducao.lista_kanban != None
                        ).order_by(ApontamentoProducao.data_hora.desc()).first()
                        nome_lista_raw = getattr(ap_last_list, 'lista_kanban', None)
                        logger.debug(f"Status {status.id}: usando apontamento '{nome_lista_raw}' como lista_kanban")
                    
                    if nome_lista_raw:
                        nome_norm = nome_lista_raw.strip().lower()
                        kl = map_lista_por_lower.get(nome_norm)
                        if kl:
                            status_info['lista_kanban'] = getattr(kl, 'nome', None)
                            status_info['lista_tipo'] = getattr(kl, 'tipo_servico', None)
                            status_info['lista_cor'] = getattr(kl, 'cor', None)
                            logger.debug(f"Status {status.id}: normalizado para lista_kanban='{status_info['lista_kanban']}'")
                        else:
                            status_info['lista_kanban'] = nome_lista_raw
                            logger.debug(f"Status {status.id}: usando raw lista_kanban='{nome_lista_raw}' (não encontrado no mapa)")
                except Exception as e:
                    logger.error(f"Falha ao determinar lista_kanban para status {status.id}: {e}")
                    pass

                # Aplicar filtros (lista, lista_tipo, status) considerando cartões fantasma
                try:
                    logger.debug(f"Verificando filtros para status {status.id}: lista_kanban='{status_info.get('lista_kanban')}', lista_tipo='{status_info.get('lista_tipo')}', status_atual='{status_info.get('status_atual')}'")
                    logger.debug(f"Filtros ativos: lista_filter={lista_filter}, lista_tipo_filter={lista_tipo_filter}, status_filter_set={status_filter_set}")
                    
                    # Aplicar filtro de lista kanban (considerando listas dos cartões fantasma desta OS)
                    if lista_filter is not None:
                        listas_ghost = ghost_por_os.get(status.ordem_servico_id, {}).get('listas_lower', set())
                        lista_principal = status_info.get('lista_kanban')
                        lista_principal_ok = lista_principal and lista_principal.lower() == lista_filter
                        ghost_ok = lista_filter in listas_ghost if listas_ghost else False
                        if not (lista_principal_ok or ghost_ok):
                            logger.debug(f"Status {status.id} excluído por filtro de lista (principal/ghost não correspondem)")
                            continue
                    
                    # Aplicar filtro de tipo (considerando tipos das listas dos cartões fantasma)
                    if lista_tipo_filter is not None:
                        tipos_ghost = ghost_por_os.get(status.ordem_servico_id, {}).get('tipos_lower', set())
                        tipo_principal = status_info.get('lista_tipo')
                        tipo_principal_ok = tipo_principal and str(tipo_principal).strip().lower() == lista_tipo_filter
                        ghost_tipo_ok = lista_tipo_filter in tipos_ghost if tipos_ghost else False
                        if not (tipo_principal_ok or ghost_tipo_ok):
                            logger.debug(f"Status {status.id} excluído por filtro de tipo (principal/ghost não correspondem)")
                            continue
                    
                    # Aplicar filtro de status (inclui 'fantasma' se houver cartão fantasma associado)
                    if status_filter_set is not None:
                        st_atual = (status_info.get('status_atual') or '').strip().lower()
                        tem_ghost = status.ordem_servico_id in ghost_por_os
                        ok_status = (st_atual in status_filter_set) or ('fantasma' in status_filter_set and tem_ghost)
                        if not ok_status:
                            logger.debug(f"Status {status.id} excluído por filtro de status (sem correspondência nem fantasma associado)")
                            continue
                    
                    logger.debug(f"Status {status.id} passou em todos os filtros, será incluído")
                except Exception as e:
                    logger.error(f"Erro ao aplicar filtros para status {status.id}: {e}")

                # Mapear apontamentos ativos por (item, trabalho) para indicar múltiplos simultâneos
                try:
                    ativos = ApontamentoProducao.query.filter(
                        ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                        ApontamentoProducao.data_fim == None,
                        ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa', 'stop'])
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
                        item_imagem_path = None
                        trabalho_nome = None
                        try:
                            it = Item.query.get(ap.item_id) if ap.item_id else None
                            if it:
                                item_nome = getattr(it, 'nome', None)
                                item_codigo = getattr(it, 'codigo_acb', None)
                                item_imagem_path = getattr(it, 'imagem_path', None)
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
                            'item_imagem_path': item_imagem_path if 'item_imagem_path' in locals() else None,
                            'trabalho_id': ap.trabalho_id,
                            'trabalho_nome': trabalho_nome,
                            'status': 'Setup em andamento' if ap.tipo_acao == 'inicio_setup' else ('Pausado' if ap.tipo_acao in ['pausa', 'stop'] else 'Produção em andamento'),
                            'inicio_acao': to_brt_iso(ap.data_hora),
                            'operador_id': operador_id,
                            'operador_nome': operador_nome,
                            'operador_codigo': operador_codigo,
                            'ultima_quantidade': ultima_q_combo,
                            # Motivo da pausa (somente quando tipo_acao == 'pausa')
                            'motivo_pausa': getattr(ap, 'motivo_parada', None) if ap.tipo_acao in ['pausa', 'stop'] else None
                        })

                        # Analytics por trabalho (aproximação baseada no mesmo critério do cartão principal)
                        try:
                            analytics_t = {}

                            # Estimativas (reutilizar do nível do status quando disponível)
                            try:
                                base_an = status_info.get('analytics', {}) if isinstance(status_info, dict) else {}
                                analytics_t['tempo_setup_estimado'] = base_an.get('tempo_setup_estimado')
                                analytics_t['tempo_peca_estimado'] = base_an.get('tempo_peca_estimado')
                            except Exception:
                                pass

                            # Setup utilizado para este item/trabalho
                            try:
                                inicio_setup_t = ApontamentoProducao.query.filter(
                                    ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                    ApontamentoProducao.item_id == ap.item_id,
                                    ApontamentoProducao.trabalho_id == ap.trabalho_id,
                                    ApontamentoProducao.tipo_acao == 'inicio_setup'
                                ).order_by(ApontamentoProducao.data_hora.desc()).first()
                                if inicio_setup_t:
                                    fim_setup_t = ApontamentoProducao.query.filter(
                                        ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                        ApontamentoProducao.item_id == ap.item_id,
                                        ApontamentoProducao.trabalho_id == ap.trabalho_id,
                                        ApontamentoProducao.tipo_acao == 'fim_setup',
                                        ApontamentoProducao.data_hora > inicio_setup_t.data_hora
                                    ).order_by(ApontamentoProducao.data_hora.asc()).first()
                                    if fim_setup_t:
                                        analytics_t['tempo_setup_utilizado'] = int((fim_setup_t.data_hora - inicio_setup_t.data_hora).total_seconds())
                                    else:
                                        analytics_t['tempo_setup_utilizado'] = int((agora_utc - inicio_setup_t.data_hora).total_seconds())
                            except Exception:
                                pass

                            # Produção utilizada e pausas para este item/trabalho
                            tempo_producao_util_t = 0
                            tempo_pausa_util_t = 0
                            try:
                                inicio_prod_t = ApontamentoProducao.query.filter(
                                    ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                    ApontamentoProducao.item_id == ap.item_id,
                                    ApontamentoProducao.trabalho_id == ap.trabalho_id,
                                    ApontamentoProducao.tipo_acao == 'inicio_producao'
                                ).order_by(ApontamentoProducao.data_hora.desc()).first()

                                if inicio_prod_t:
                                    pausa_aberta_t = ApontamentoProducao.query.filter(
                                        ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                        ApontamentoProducao.item_id == ap.item_id,
                                        ApontamentoProducao.trabalho_id == ap.trabalho_id,
                                        ApontamentoProducao.tipo_acao.in_(['pausa', 'stop']),
                                        ApontamentoProducao.data_hora >= inicio_prod_t.data_hora,
                                        ApontamentoProducao.data_fim == None
                                    ).order_by(ApontamentoProducao.data_hora.desc()).first()

                                    if pausa_aberta_t:
                                        tempo_producao_util_t = int((pausa_aberta_t.data_hora - inicio_prod_t.data_hora).total_seconds())
                                        tempo_pausa_util_t = int((agora_utc - pausa_aberta_t.data_hora).total_seconds())
                                    else:
                                        fim_prod_t = ApontamentoProducao.query.filter(
                                            ApontamentoProducao.ordem_servico_id == status.ordem_servico_id,
                                            ApontamentoProducao.item_id == ap.item_id,
                                            ApontamentoProducao.trabalho_id == ap.trabalho_id,
                                            ApontamentoProducao.tipo_acao == 'inicio_producao',
                                            ApontamentoProducao.data_fim == None
                                        ).order_by(ApontamentoProducao.data_hora.desc()).first()
                                        if fim_prod_t:
                                            tempo_producao_util_t = int((agora_utc - inicio_prod_t.data_hora).total_seconds())
                                        else:
                                            tempo_producao_util_t = int(getattr(inicio_prod_t, 'tempo_decorrido', 0) or 0)
                            except Exception:
                                pass

                            analytics_t['tempo_producao_utilizado'] = max(0, tempo_producao_util_t)
                            analytics_t['tempo_pausas_utilizado'] = max(0, tempo_pausa_util_t)

                            # Média por peça e status de performance
                            try:
                                qtd_t = ultima_q_combo or 0
                                total_seg_t = (analytics_t.get('tempo_producao_utilizado') or 0) + (analytics_t.get('tempo_pausas_utilizado') or 0)
                                if qtd_t and total_seg_t:
                                    media_t = int(total_seg_t / max(qtd_t, 1))
                                    analytics_t['media_seg_por_peca'] = media_t
                                    if analytics_t.get('tempo_peca_estimado'):
                                        estp_t = analytics_t['tempo_peca_estimado']
                                        if media_t <= estp_t * (1 - tolerancia):
                                            analytics_t['producao_status'] = 'Excelente'
                                        elif media_t <= estp_t * (1 + tolerancia):
                                            analytics_t['producao_status'] = 'Dentro do esperado'
                                        else:
                                            analytics_t['producao_status'] = 'Abaixo do esperado'
                            except Exception:
                                pass

                            # Status de setup baseado na estimativa
                            try:
                                if analytics_t.get('tempo_setup_estimado') is not None and analytics_t.get('tempo_setup_utilizado') is not None:
                                    est_t = analytics_t['tempo_setup_estimado']
                                    usado_t = analytics_t['tempo_setup_utilizado']
                                    if usado_t <= est_t * (1 - tolerancia):
                                        analytics_t['setup_status'] = 'Excelente'
                                    elif usado_t <= est_t * (1 + tolerancia):
                                        analytics_t['setup_status'] = 'Dentro do esperado'
                                    else:
                                        analytics_t['setup_status'] = 'Abaixo do esperado'
                            except Exception:
                                pass

                            # Anexar
                            try:
                                ativos_info[-1]['analytics'] = analytics_t
                            except Exception:
                                pass
                        except Exception as e_an_t:
                            logger.error(f"Analytics por trabalho (item={ap.item_id}, trab={ap.trabalho_id}): {e_an_t}")

                    status_info['ativos_por_trabalho'] = ativos_info
                    status_info['qtd_ativos'] = len(ativos_info)
                    status_info['multiplo_ativos'] = len(ativos_info) > 1
                except Exception as e_mult:
                    logger.error(f"Falha ao montar ativos_por_trabalho: {e_mult}")

                # Resumo de contagens por status (setup, pausa, producao)
                try:
                    counts = {'setup': 0, 'pausado': 0, 'producao': 0}
                    for a in status_info.get('ativos_por_trabalho', []) or []:
                        s = (a.get('status') or '').lower()
                        if 'setup' in s:
                            counts['setup'] += 1
                        elif 'pausado' in s:
                            counts['pausado'] += 1
                        elif 'produção' in s or 'producao' in s:
                            counts['producao'] += 1
                    status_info['resumo_status'] = counts
                except Exception as e_cnt:
                    logger.error(f"Falha ao calcular resumo_status: {e_cnt}")

                # Montar lista completa de trabalhos do item com status e tempos somados
                try:
                    trabalhos_list = []
                    # Preferir item atual pré-carregado; fallback para item do primeiro pedido da OS
                    item_obj = getattr(status, 'item_atual', None)
                    if not item_obj:
                        os_obj_local = getattr(status, 'ordem_servico', None)
                        if os_obj_local and getattr(os_obj_local, 'pedidos', None):
                            pedido_os = os_obj_local.pedidos[0]
                            pedido_local = getattr(pedido_os, 'pedido', None)
                            item_obj = getattr(pedido_local, 'item', None) if pedido_local else None
                    if item_obj and getattr(item_obj, 'trabalhos', None):
                        ativos_lista = status_info.get('ativos_por_trabalho', []) or []
                        for it in item_obj.trabalhos:
                            trab = getattr(it, 'trabalho', None)
                            if not trab:
                                continue
                            trab_id = getattr(trab, 'id', None)
                            trab_nome = getattr(trab, 'nome', '')
                            relacionados = [a for a in ativos_lista if a.get('trabalho_id') == trab_id]
                            # Agregar tempos
                            tempo_setup = 0
                            tempo_pausas = 0
                            tempo_producao = 0
                            ultima_q = 0
                            status_trab = 'Aguardando'
                            inicio_mais_recente = None
                            for a in relacionados:
                                an = a.get('analytics') or {}
                                tempo_setup += int(an.get('tempo_setup_utilizado') or 0)
                                tempo_pausas += int(an.get('tempo_pausas_utilizado') or 0)
                                tempo_producao += int(an.get('tempo_producao_utilizado') or 0)
                                # última quantidade: pegar da entrada mais recente
                                try:
                                    ini = a.get('inicio_acao')
                                    if ini:
                                        if not inicio_mais_recente or str(ini) > str(inicio_mais_recente):
                                            inicio_mais_recente = ini
                                            ultima_q = int(a.get('ultima_quantidade') or 0)
                                            status_trab = a.get('status') or status_trab
                                except Exception:
                                    pass
                            trabalhos_list.append({
                                'trabalho_id': trab_id,
                                'trabalho_nome': trab_nome,
                                'status': status_trab,
                                'ultima_quantidade': int(ultima_q or 0),
                                'tempo_setup_utilizado': int(tempo_setup or 0),
                                'tempo_pausas_utilizado': int(tempo_pausas or 0),
                                'tempo_producao_utilizado': int(tempo_producao or 0)
                            })
                        status_info['trabalhos_do_item'] = trabalhos_list
                except Exception as e_trabs:
                    logger.error(f"Falha ao montar trabalhos_do_item: {e_trabs}")

                # Anexar metadados de cartões fantasma (se houver) e adicionar ao resultado
                try:
                    if status.ordem_servico_id in ghost_por_os:
                        bucket = ghost_por_os.get(status.ordem_servico_id) or {}
                        # Listas únicas e cards
                        status_info['ghost_cards'] = bucket.get('cards', [])
                        status_info['ghost_listas_kanban'] = sorted(list(bucket.get('listas_lower', set())))
                except Exception:
                    pass
                # Adicionar ao resultado
                resultado['status_ativos'].append(status_info)
                # Marcar esta OS como já processada
                os_com_status_ativo.add(status.ordem_servico_id)
                logger.debug(f"Status ID={status.id} processado com sucesso e adicionado ao resultado")
            except Exception as e_status:
                logger.error(f"Falha ao montar status_info para status ID {getattr(status, 'id', None)}: {e_status}")
                # Continua para o próximo status
                continue
        timings['build_status_loop_ms'] = int((time.perf_counter() - t0) * 1000)
        
        # Adicionar OS que estão em máquinas mas NÃO têm status ativo (para mostrar todas as máquinas)
        logger.debug("Adicionando OS sem status ativo...")
        t0 = time.perf_counter()
        for ordem in todas_os_em_maquinas:
            logger.debug(f"Processando OS {ordem.id} - Status: {getattr(ordem, 'status', None)}")
            if ordem.id in os_com_status_ativo:
                logger.debug(f"OS {ordem.id} já tem status ativo, pulando...")
                continue  # Já foi processada acima
                
            try:
                # Criar status_info básico para OS sem apontamento ativo
                status_info = {
                    'id': f"os_{ordem.id}",
                    'ordem_servico_id': ordem.id,
                    'ordem_id': ordem.id,
                    'status_atual': 'Aguardando'
                }
                
                # Número da OS
                try:
                    os_num = getattr(ordem, 'numero', None) or getattr(ordem, 'codigo', None) or f"OS-{ordem.id}"
                    status_info['os_numero'] = os_num
                except Exception:
                    status_info['os_numero'] = f"OS-{ordem.id}"
                
                # Lista Kanban (status da OS) com normalização/canonização
                status_info['lista_kanban'] = getattr(ordem, 'status', None)
                try:
                    nome_raw = status_info.get('lista_kanban')
                    if nome_raw:
                        kl = map_lista_por_lower.get(nome_raw.strip().lower())
                        if kl:
                            status_info['lista_kanban'] = getattr(kl, 'nome', None)
                            status_info['lista_tipo'] = getattr(kl, 'tipo_servico', None)
                            status_info['lista_cor'] = getattr(kl, 'cor', None)
                except Exception:
                    pass
                
                # Aplicar filtros (considerando cartões fantasma associados à OS)
                try:
                    if lista_filter is not None:
                        listas_ghost = ghost_por_os.get(ordem.id, {}).get('listas_lower', set())
                        lista_principal = status_info.get('lista_kanban')
                        lista_principal_ok = lista_principal and lista_principal.lower() == lista_filter
                        ghost_ok = lista_filter in listas_ghost if listas_ghost else False
                        if not (lista_principal_ok or ghost_ok):
                            continue
                    
                    if lista_tipo_filter is not None:
                        tipos_ghost = ghost_por_os.get(ordem.id, {}).get('tipos_lower', set())
                        tipo_principal = status_info.get('lista_tipo')
                        tipo_principal_ok = tipo_principal and str(tipo_principal).strip().lower() == lista_tipo_filter
                        ghost_tipo_ok = lista_tipo_filter in tipos_ghost if tipos_ghost else False
                        if not (tipo_principal_ok or ghost_tipo_ok):
                            continue
                    
                    if status_filter_set is not None:
                        st_atual = (status_info.get('status_atual') or '').strip().lower()
                        tem_ghost = ordem.id in ghost_por_os
                        ok_status = (st_atual in status_filter_set) or ('fantasma' in status_filter_set and tem_ghost)
                        if not ok_status:
                            continue
                except Exception:
                    pass
                
                # Buscar item/trabalho da OS (mesmo sem apontamento ativo)
                try:
                    logger.debug(f"OS {ordem.id}: buscando informações do item via pedidos")
                    if ordem.pedidos:
                        # Agregar clientes e total usando relações já carregadas
                        try:
                            clientes_map = {}
                            total_q = 0
                            for po in getattr(ordem, 'pedidos', []) or []:
                                ped = getattr(po, 'pedido', None)
                                if not ped:
                                    continue
                                q = int(getattr(ped, 'quantidade', 0) or 0)
                                total_q += q
                                cli = getattr(ped, 'cliente', None)
                                nome_cli = getattr(cli, 'nome', None) or 'Cliente'
                                clientes_map[nome_cli] = clientes_map.get(nome_cli, 0) + q
                            status_info['quantidade_total'] = int(total_q)
                            if clientes_map:
                                status_info['clientes_quantidades'] = [
                                    {'cliente_nome': k, 'quantidade': v} for k, v in clientes_map.items()
                                ]
                                status_info['cliente_nome'] = next(iter(clientes_map.keys()))
                        except Exception as e_cli2:
                            logger.error(f"OS {ordem.id}: falha ao agregar clientes/quantidades: {e_cli2}")

                        pedido_os = ordem.pedidos[0]
                        logger.debug(f"OS {ordem.id}: encontrado pedido_os com pedido_id={getattr(pedido_os, 'pedido_id', None)}")
                        pedido = pedido_os.pedido
                        item = pedido.item if pedido else None
                        if item:
                            logger.debug(f"OS {ordem.id}: encontrado item via relação pre-carregada com item_id={item.id}")
                            status_info['item_id'] = item.id
                            status_info['item_nome'] = item.nome
                            status_info['item_codigo'] = item.codigo_acb
                            # Caminho da imagem do item para exibição quando não há status ativo
                            status_info['item_imagem_path'] = getattr(item, 'imagem_path', None)
                            logger.debug(f"OS {ordem.id}: item encontrado - nome='{item.nome}', imagem='{getattr(item, 'imagem_path', None)}'")
                            
                            # Buscar trabalho do item
                            if item.trabalhos:
                                trabalho_rel = item.trabalhos[0]
                                trabalho = trabalho_rel.trabalho
                                if trabalho:
                                    status_info['trabalho_id'] = trabalho.id
                                    status_info['trabalho_nome'] = trabalho.nome
                                    logger.debug(f"OS {ordem.id}: trabalho encontrado - nome='{trabalho.nome}'")
                                
                                # clientes_quantidades e quantidade_total já definidos acima
                                # Montar trabalhos_do_item mesmo sem ativos, deixando todos visíveis
                                try:
                                    trabalhos_list = []
                                    for it in item.trabalhos:
                                        trab = it.trabalho
                                        if not trab:
                                            continue
                                        trabalhos_list.append({
                                            'trabalho_id': trab.id,
                                            'trabalho_nome': trab.nome,
                                            'status': 'Aguardando',
                                            'ultima_quantidade': 0,
                                            'tempo_setup_utilizado': 0,
                                            'tempo_pausas_utilizado': 0,
                                            'tempo_producao_utilizado': 0
                                        })
                                    if trabalhos_list:
                                        status_info['trabalhos_do_item'] = trabalhos_list
                                except Exception as e_trabs2:
                                    logger.error(f"OS {ordem.id}: falha ao montar trabalhos_do_item sem ativos: {e_trabs2}")
                            else:
                                logger.debug(f"OS {ordem.id}: item com ID {pedido.item_id} não encontrado no banco")
                        else:
                            logger.debug(f"OS {ordem.id}: pedido não encontrado ou sem item_id")
                    else:
                        logger.debug(f"OS {ordem.id}: sem pedidos associados")
                except Exception as e:
                    logger.error(f"OS {ordem.id}: falha ao buscar item via pedidos: {e}")
                
                # Valores padrão para campos obrigatórios
                status_info.setdefault('ultima_quantidade', 0)
                status_info.setdefault('ativos_por_trabalho', [])
                status_info.setdefault('qtd_ativos', 0)
                status_info.setdefault('multiplo_ativos', False)
                status_info.setdefault('analytics', {})
                status_info.setdefault('quantidade_total', 0)
                status_info.setdefault('cliente_nome', None)
                status_info.setdefault('resumo_status', {'setup': 0, 'pausado': 0, 'producao': 0})
                status_info.setdefault('trabalhos_do_item', [])
                
                # Anexar metadados de cartões fantasma (se houver) e adicionar ao resultado
                try:
                    if ordem.id in ghost_por_os:
                        bucket = ghost_por_os.get(ordem.id) or {}
                        status_info['ghost_cards'] = bucket.get('cards', [])
                        status_info['ghost_listas_kanban'] = sorted(list(bucket.get('listas_lower', set())))
                except Exception:
                    pass
                # Adicionar ao resultado
                resultado['status_ativos'].append(status_info)
                
            except Exception as e_os:
                logger.error(f"Falha ao processar OS {ordem.id}: {e_os}")
                continue
        timings['build_os_sem_ativos_loop_ms'] = int((time.perf_counter() - t0) * 1000)
        
        logger.debug(f"Status ativos formatados (com cartões fantasma mesclados): {len(resultado['status_ativos'])}")
        # Anexar timings apenas quando explicitamente solicitado
        try:
            if (request.args.get('timing') or '').strip().lower() in ['1', 'true', 'yes']:
                timings['total_ms'] = int((time.perf_counter() - t_start) * 1000)
                resultado['timings'] = timings
                logger.info(f"/status-ativos timings: {timings}")
        except Exception:
            pass
        return jsonify(resultado)
    except Exception as e:
        logger.exception(f"Falha ao buscar status ativos: {e}")
        return jsonify({'error': str(e), 'message': 'Falha ao buscar status ativos'}), 500

@apontamento_bp.route('/detalhes/<int:ordem_id>', methods=['GET'])
def detalhes_ordem_servico(ordem_id):
    """Retorna análise detalhada completa de uma ordem de serviço"""
    try:
        # Buscar OS
        ordem = OrdemServico.query.get_or_404(ordem_id)
        
        # Buscar todos os apontamentos desta OS
        apontamentos = ApontamentoProducao.query.filter_by(ordem_servico_id=ordem_id).order_by(ApontamentoProducao.data_hora.asc()).all()
        
        # Buscar informações do item
        item_info = {}
        if ordem.pedidos:
            pedido_os = ordem.pedidos[0]
            pedido = Pedido.query.get(pedido_os.pedido_id)
            if pedido and pedido.item_id:
                item = Item.query.get(pedido.item_id)
                if item:
                    item_info = {
                        'id': item.id,
                        'nome': item.nome,
                        'codigo': item.codigo_acb,
                        'tempo_estimado_peca': getattr(item, 'tempo_estimado_peca', None),
                        'tempo_setup_estimado': getattr(item, 'tempo_setup_estimado', None)
                    }
        
        # Agrupar apontamentos por tipo de trabalho
        trabalhos_analytics = {}
        
        for ap in apontamentos:
            trabalho_key = f"{ap.item_id}_{ap.trabalho_id}"
            
            if trabalho_key not in trabalhos_analytics:
                trabalho = Trabalho.query.get(ap.trabalho_id) if ap.trabalho_id else None
                trabalhos_analytics[trabalho_key] = {
                    'item_id': ap.item_id,
                    'trabalho_id': ap.trabalho_id,
                    'trabalho_nome': trabalho.nome if trabalho else 'N/A',
                    'apontamentos': [],
                    'setup_total': 0,
                    'producao_total': 0,
                    'pausas_total': 0,
                    'pausas_por_motivo': {},
                    'ultima_quantidade': 0,
                    'operadores': set()
                }
            
            trabalhos_analytics[trabalho_key]['apontamentos'].append({
                'id': ap.id,
                'data_hora': ap.data_hora.isoformat() if ap.data_hora else None,
                'data_fim': ap.data_fim.isoformat() if ap.data_fim else None,
                'tipo_acao': ap.tipo_acao,
                'operador_id': ap.operador_id,
                'operador_nome': Usuario.query.get(ap.operador_id).nome if ap.operador_id else 'N/A',
                'quantidade': ap.quantidade,
                'motivo_pausa': ap.motivo_parada,
                'duracao_segundos': None
            })
            
            if ap.operador_id:
                trabalhos_analytics[trabalho_key]['operadores'].add(ap.operador_id)
                
            if ap.quantidade:
                trabalhos_analytics[trabalho_key]['ultima_quantidade'] = ap.quantidade
        
        # Calcular durações e analytics
        for trabalho_key, dados in trabalhos_analytics.items():
            apts = dados['apontamentos']
            
            # Calcular durações
            for i, ap in enumerate(apts):
                if ap['data_fim']:
                    inicio = datetime.fromisoformat(ap['data_hora'])
                    fim = datetime.fromisoformat(ap['data_fim'])
                    duracao = int((fim - inicio).total_seconds())
                    ap['duracao_segundos'] = duracao
                    
                    # Somar aos totais
                    if ap['tipo_acao'] in ['inicio_setup', 'fim_setup']:
                        dados['setup_total'] += duracao
                    elif ap['tipo_acao'] in ['inicio_producao', 'fim_producao']:
                        dados['producao_total'] += duracao
                    elif ap['tipo_acao'] in ['pausa', 'stop']:
                        dados['pausas_total'] += duracao
                        motivo = ap['motivo_pausa'] or 'Não informado'
                        dados['pausas_por_motivo'][motivo] = dados['pausas_por_motivo'].get(motivo, 0) + duracao
            
            # Converter set para lista
            dados['operadores'] = list(dados['operadores'])
        
        # Calcular analytics gerais
        total_setup = sum(t['setup_total'] for t in trabalhos_analytics.values())
        total_producao = sum(t['producao_total'] for t in trabalhos_analytics.values())
        total_pausas = sum(t['pausas_total'] for t in trabalhos_analytics.values())
        
        # Calcular eficiência
        tempo_estimado_total = 0
        if item_info.get('tempo_estimado_peca') and trabalhos_analytics:
            for dados in trabalhos_analytics.values():
                if dados['ultima_quantidade']:
                    tempo_estimado_total += item_info['tempo_estimado_peca'] * dados['ultima_quantidade']
        
        # Analytics por operador
        analytics_operadores = {}
        for trabalho_key, dados in trabalhos_analytics.items():
            for ap in dados['apontamentos']:
                if ap['operador_id'] and ap['duracao_segundos']:
                    op_id = ap['operador_id']
                    if op_id not in analytics_operadores:
                        analytics_operadores[op_id] = {
                            'nome': ap['operador_nome'],
                            'tempo_setup': 0,
                            'tempo_producao': 0,
                            'tempo_pausas': 0,
                            'trabalhos': {}
                        }
                    
                    if ap['tipo_acao'] in ['inicio_setup', 'fim_setup']:
                        analytics_operadores[op_id]['tempo_setup'] += ap['duracao_segundos']
                    elif ap['tipo_acao'] in ['inicio_producao', 'fim_producao']:
                        analytics_operadores[op_id]['tempo_producao'] += ap['duracao_segundos']
                    elif ap['tipo_acao'] in ['pausa', 'stop']:
                        analytics_operadores[op_id]['tempo_pausas'] += ap['duracao_segundos']
                    
                    # Por trabalho
                    trabalho_nome = dados['trabalho_nome']
                    if trabalho_nome not in analytics_operadores[op_id]['trabalhos']:
                        analytics_operadores[op_id]['trabalhos'][trabalho_nome] = {
                            'tempo_setup': 0,
                            'tempo_producao': 0,
                            'tempo_pausas': 0
                        }
                    
                    if ap['tipo_acao'] in ['inicio_setup', 'fim_setup']:
                        analytics_operadores[op_id]['trabalhos'][trabalho_nome]['tempo_setup'] += ap['duracao_segundos']
                    elif ap['tipo_acao'] in ['inicio_producao', 'fim_producao']:
                        analytics_operadores[op_id]['trabalhos'][trabalho_nome]['tempo_producao'] += ap['duracao_segundos']
                    elif ap['tipo_acao'] in ['pausa', 'stop']:
                        analytics_operadores[op_id]['trabalhos'][trabalho_nome]['tempo_pausas'] += ap['duracao_segundos']
        
        resultado = {
            'ordem_servico': {
                'id': ordem.id,
                'numero': getattr(ordem, 'numero', None) or f"OS-{ordem.id}",
                'status': ordem.status
            },
            'item': item_info,
            'analytics_gerais': {
                'tempo_setup_total': total_setup,
                'tempo_producao_total': total_producao,
                'tempo_pausas_total': total_pausas,
                'tempo_estimado_total': tempo_estimado_total,
                'eficiencia_percentual': round((tempo_estimado_total / total_producao * 100) if total_producao > 0 else 0, 1)
            },
            'trabalhos': list(trabalhos_analytics.values()),
            'analytics_operadores': analytics_operadores
        }
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.exception(f"Falha ao buscar detalhes da OS {ordem_id}: {e}")
        return jsonify({'error': str(e)}), 500

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
            logger.exception("Falha ao obter última quantidade para validação")

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
        agora = datetime.utcnow()
        
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
                'data_hora': to_brt_iso(apontamento.data_hora),
                'data_fim': to_brt_iso(getattr(apontamento, 'data_fim', None)) if hasattr(apontamento, 'data_fim') else None,
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
                logger.exception("Falha ao buscar operador para log %s", apontamento.id)
            
            # Adicionar informações do item
            try:
                if apontamento.item_id:
                    item = Item.query.get(apontamento.item_id)
                    if item:
                        log_info['item_id'] = item.id
                        log_info['item_nome'] = item.nome
                        log_info['item_codigo'] = item.codigo_acb
            except Exception as e_item:
                logger.exception("Falha ao buscar item para log %s", apontamento.id)
            
            # Adicionar informações do trabalho
            try:
                if apontamento.trabalho_id:
                    trabalho = Trabalho.query.get(apontamento.trabalho_id)
                    if trabalho:
                        log_info['trabalho_id'] = trabalho.id
                        log_info['trabalho_nome'] = trabalho.nome
            except Exception as e_trab:
                logger.exception("Falha ao buscar trabalho para log %s", apontamento.id)
            
            logs.append(log_info)
        
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        logger.exception("Falha ao buscar logs de apontamento para OS %s", ordem_id)
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar logs de apontamento: {str(e)}'
        }), 500
