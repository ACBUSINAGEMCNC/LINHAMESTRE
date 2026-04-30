from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from models import db, Usuario, ApontamentoProducao, StatusProducaoOS, OrdemServico, ItemTrabalho, PedidoOrdemServico, Pedido, Item, Trabalho, KanbanLista, CartaoFantasma
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sqlalchemy.orm import joinedload
from sqlalchemy import func, select
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
    Smart detection: if datetime seems to be from before timezone fix, treat as UTC.
    """
    if not dt:
        return None
    
    if dt.tzinfo is None:
        # Detectar se é um registro antigo (naive UTC) ou novo (naive BRT).
        # Problema comum: servidor roda em UTC e gravou timestamp naive em UTC.
        # Heurística: se o timestamp estiver "no futuro" em relação ao agora BRT,
        # é forte indício de que foi gravado em UTC (ex.: +3h).
        agora_brt = datetime.now(LOCAL_TZ).replace(tzinfo=None)
        if dt > agora_brt + timedelta(minutes=10):
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.replace(tzinfo=LOCAL_TZ)
    
    try:
        return dt.astimezone(LOCAL_TZ).isoformat()
    except Exception:
        return dt.isoformat()


def _query_apontamento_aberto(os_id, item_id, trab_id, tipo_acao):
    return (
        ApontamentoProducao.query.filter(
            ApontamentoProducao.ordem_servico_id == os_id,
            ApontamentoProducao.item_id == item_id,
            ApontamentoProducao.trabalho_id == trab_id,
            ApontamentoProducao.tipo_acao == tipo_acao,
            ApontamentoProducao.data_fim.is_(None)
        )
        .order_by(ApontamentoProducao.data_hora.desc())
        .first()
    )


def _buscar_ultima_quantidade(os_id, item_id, trab_id):
    ultimo_ap = (
        ApontamentoProducao.query.with_entities(ApontamentoProducao.quantidade)
        .filter(
            ApontamentoProducao.ordem_servico_id == os_id,
            ApontamentoProducao.item_id == item_id,
            ApontamentoProducao.trabalho_id == trab_id,
            ApontamentoProducao.quantidade.isnot(None)
        )
        .order_by(ApontamentoProducao.data_hora.desc())
        .first()
    )
    if not ultimo_ap or ultimo_ap[0] is None:
        return 0
    return int(ultimo_ap[0])


def _buscar_apontamento_aberto_operador(usuario_id, ordem_servico_id=None):
    query = (
        ApontamentoProducao.query.filter(
            ApontamentoProducao.usuario_id == usuario_id,
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
        )
        .order_by(ApontamentoProducao.data_hora.desc())
    )
    if ordem_servico_id is not None:
        query = query.filter(ApontamentoProducao.ordem_servico_id != ordem_servico_id)
    return query.first()


def _buscar_apontamento_ativo_operador_na_os(usuario_id, ordem_servico_id):
    return (
        ApontamentoProducao.query.filter(
            ApontamentoProducao.usuario_id == usuario_id,
            ApontamentoProducao.ordem_servico_id == ordem_servico_id,
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
        )
        .order_by(
            ApontamentoProducao.data_hora.desc(),
            ApontamentoProducao.id.desc()
        )
        .first()
    )


def _obter_estados_batch(ordem_servico_ids):
    """
    OTIMIZAÇÃO: Batch processing de estados para múltiplas OS
    Busca todos os apontamentos abertos de uma vez usando IN query,
    eliminando N+1 queries e processando em memória O(1) por OS
    """
    if not ordem_servico_ids:
        return {}
    
    # Buscar TODOS os apontamentos abertos de TODAS as OS em UMA query
    apontamentos_abertos = (
        ApontamentoProducao.query.filter(
            ApontamentoProducao.ordem_servico_id.in_(ordem_servico_ids),
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
        )
        .order_by(ApontamentoProducao.ordem_servico_id, ApontamentoProducao.data_hora.desc())
        .all()
    )
    
    # Agrupar apontamentos por OS em memória usando defaultdict
    from collections import defaultdict
    apontamentos_por_os = defaultdict(list)
    for ap in apontamentos_abertos:
        apontamentos_por_os[ap.ordem_servico_id].append(ap)
    
    # Processar estado de cada OS em memória (O(1) por OS)
    estados = {}
    for os_id in ordem_servico_ids:
        aps = apontamentos_por_os.get(os_id, [])
        
        inicio_setup = next((ap for ap in aps if ap.tipo_acao == 'inicio_setup'), None)
        inicio_producao = next((ap for ap in aps if ap.tipo_acao == 'inicio_producao'), None)
        pausa = next((ap for ap in aps if ap.tipo_acao == 'pausa'), None)
        
        apontamento_base = pausa or inicio_producao or inicio_setup
        status_real = 'Aguardando'
        if pausa:
            status_real = 'Pausado'
        elif inicio_producao:
            status_real = 'Produção em andamento'
        elif inicio_setup:
            status_real = 'Setup em andamento'
        
        estados[os_id] = {
            'status_atual': status_real,
            'apontamento_base': apontamento_base,
            'setup_aberto': inicio_setup,
            'producao_aberta': inicio_producao,
            'pausa_aberta': pausa,
            'item_id': getattr(apontamento_base, 'item_id', None),
            'trabalho_id': getattr(apontamento_base, 'trabalho_id', None),
            'usuario_id': getattr(apontamento_base, 'usuario_id', None),
            'inicio_acao': getattr(apontamento_base, 'data_hora', None)
        }
    
    return estados


def _obter_estado_real_os(ordem_servico_id):
    """
    Função legada mantida para compatibilidade
    Usa batch processing internamente para melhor performance
    """
    estados = _obter_estados_batch([ordem_servico_id])
    return estados.get(ordem_servico_id, {
        'status_atual': 'Aguardando',
        'apontamento_base': None,
        'setup_aberto': None,
        'producao_aberta': None,
        'pausa_aberta': None,
        'item_id': None,
        'trabalho_id': None,
        'usuario_id': None,
        'inicio_acao': None
    })


def _aplicar_estado_real_status(status, estado_real):
    if not status or not estado_real:
        return status

    status.status_atual = estado_real['status_atual']
    status.operador_atual_id = estado_real['usuario_id']
    status.item_atual_id = estado_real['item_id']
    status.trabalho_atual_id = estado_real['trabalho_id']
    status.inicio_acao = estado_real['inicio_acao']
    if estado_real['status_atual'] != 'Pausado':
        status.motivo_pausa = None
    return status

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
        status_list_raw = (
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

        status_list = []
        for status in status_list_raw:
            estado_real = _obter_estado_real_os(status.ordem_servico_id)
            _aplicar_estado_real_status(status, estado_real)
            if estado_real['status_atual'] in ['Setup em andamento', 'Produção em andamento', 'Pausado']:
                status_list.append(status)

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
    
    # Cache rápido para evitar múltiplas queries do mesmo código
    from flask import current_app
    cache_key = f"op_valid:{codigo}"
    
    try:
        if hasattr(current_app, 'cache_store'):
            cached = current_app.cache_store.get(cache_key)
            if cached:
                return jsonify(cached)
    except:
        pass
    
    # Query otimizada e direta (sem retry para evitar lentidão)
    try:
        # Usar filter_by que é mais rápido que where para igualdade simples
        usuario = Usuario.query.filter_by(codigo_operador=codigo).first()
        
        if not usuario:
            result = {'valid': False, 'message': 'Código não encontrado'}
        else:
            result = {
                'valid': True, 
                'usuario_id': usuario.id,
                'nome': usuario.nome,
                'message': f'Operador: {usuario.nome}'
            }
        
        # Cachear resultado por 60 segundos (aumentado para reduzir queries)
        try:
            if hasattr(current_app, 'cache_store'):
                current_app.cache_store.set(cache_key, result, timeout=60)
        except:
            pass
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erro ao validar código {codigo}: {e}")
        return jsonify({'valid': False, 'message': 'Erro ao validar código'}), 500

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

# Rota removida - usando detalhes_ordem_servico() que retorna dados completos

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
@apontamento_bp.route('/status-ativos', methods=['GET'])
def status_ativos():
    """Retorna todos os status de produção ativos para apontamentos (usado para persistência frontend) de forma altamente otimizada."""
    try:
        from flask import current_app
        cache_key = f"status_ativos:{request.query_string.decode('utf-8')}"
        
        try:
            if hasattr(current_app, 'cache_store'):
                cached = current_app.cache_store.get(cache_key)
                if cached:
                    return jsonify(cached)
        except:
            pass
        
        t_start = time.perf_counter()
        timings = {}

        excluir_entregues = str(request.args.get('excluir_entregues', '')).strip().lower() in ('1', 'true', 'yes')

        # Filtros
        lista_filters_set = None
        lista_raw = (request.args.get('lista') or '').strip().lower()
        if lista_raw and lista_raw != 'todas':
            lista_filters = [s.strip() for s in lista_raw.split(',') if s.strip() and s.strip() != 'todas']
            if lista_filters:
                lista_filters_set = set(lista_filters)
            
        lista_tipo_filter = None
        if request.args.get('lista_tipo') and request.args.get('lista_tipo').strip():
            lista_tipo_filter = request.args.get('lista_tipo').strip().lower()
            
        status_filter_raw = request.args.get('status', '').strip().lower()
        status_filter_set = None
        if status_filter_raw and status_filter_raw != 'todos':
            status_filter_set = set([s.strip() for s in status_filter_raw.split(',') if s.strip()])

        # 1. Buscar Listas Kanban
        t0 = time.perf_counter()
        listas_kanban = KanbanLista.query.filter_by(ativa=True).all()
        nomes_listas_lower = [lista.nome.strip().lower() for lista in listas_kanban]
        map_lista_por_lower = {lista.nome.strip().lower(): lista for lista in listas_kanban}
        timings['listas_kanban_ms'] = int((time.perf_counter() - t0) * 1000)

        # 2. Buscar Cartões Fantasma ativos
        t0 = time.perf_counter()
        ghost_por_os = defaultdict(lambda: {'cards': [], 'listas_lower': set(), 'tipos_lower': set(), 'trabalhos_ids': set()})
        cartoes_fantasma_all = CartaoFantasma.query.options(
            joinedload(CartaoFantasma.trabalho),
            joinedload(CartaoFantasma.criado_por)
        ).filter(CartaoFantasma.ativo == True).all()

        for cf in cartoes_fantasma_all:
            lista_cf = (cf.lista_kanban or '').strip()
            lista_cf_lower = lista_cf.lower()
            kl_cf = map_lista_por_lower.get(lista_cf_lower)

            info_cf = {
                'id': cf.id,
                'lista_kanban': lista_cf,
                'lista_tipo': kl_cf.tipo_servico if kl_cf else None,
                'lista_cor': kl_cf.cor if kl_cf else None,
                'trabalho_id': cf.trabalho_id,
                'trabalho_nome': cf.trabalho.nome if cf.trabalho else None,
                'posicao_fila': cf.posicao_fila,
                'data_criacao': cf.data_criacao.isoformat() if cf.data_criacao else None,
            }
            bucket = ghost_por_os[cf.ordem_servico_id]
            bucket['cards'].append(info_cf)
            if lista_cf_lower:
                bucket['listas_lower'].add(lista_cf_lower)
                if kl_cf and kl_cf.tipo_servico:
                    bucket['tipos_lower'].add(str(kl_cf.tipo_servico).strip().lower())
            if cf.trabalho_id:
                bucket['trabalhos_ids'].add(cf.trabalho_id)
        timings['ghost_cards_ms'] = int((time.perf_counter() - t0) * 1000)

        # 3. Buscar OS em máquinas (e carregar relacionamentos críticos)
        t0 = time.perf_counter()
        os_em_maquinas_query = OrdemServico.query.options(
            joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.cliente),
            joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.item).joinedload(Item.trabalhos).joinedload(ItemTrabalho.trabalho),
            joinedload(OrdemServico.status_producao).joinedload(StatusProducaoOS.operador_atual),
            joinedload(OrdemServico.status_producao).joinedload(StatusProducaoOS.item_atual),
            joinedload(OrdemServico.status_producao).joinedload(StatusProducaoOS.trabalho_atual)
        ).filter(func.lower(func.trim(OrdemServico.status)).in_(nomes_listas_lower))

        all_os = os_em_maquinas_query.all()
        os_ids = [os.id for os in all_os]
        timings['query_os_ms'] = int((time.perf_counter() - t0) * 1000)

        # 4. Batch query para Apontamentos abertos e últimos apontamentos (evita N+1 inside loop)
        t0 = time.perf_counter()
        apontamentos_ativos_os = defaultdict(list)
        if os_ids:
            # Apontamentos abertos (timer ativo)
            ativos_raw = ApontamentoProducao.query.options(
                joinedload(ApontamentoProducao.usuario)
            ).filter(
                ApontamentoProducao.ordem_servico_id.in_(os_ids),
                ApontamentoProducao.data_fim.is_(None),
                ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
            ).all()
            for ap in ativos_raw:
                apontamentos_ativos_os[ap.ordem_servico_id].append(ap)
                
            # Últimos apontamentos com quantidade (para progresso)
            # Usando query otimizada com window function ou subquery para pegar o mais recente de cada OS
            subq = db.session.query(
                ApontamentoProducao.ordem_servico_id,
                func.max(ApontamentoProducao.data_hora).label('max_dt')
            ).filter(
                ApontamentoProducao.ordem_servico_id.in_(os_ids),
                ApontamentoProducao.quantidade.isnot(None)
            ).group_by(ApontamentoProducao.ordem_servico_id).subquery()

            ultimos_aps_raw = ApontamentoProducao.query.join(
                subq, (ApontamentoProducao.ordem_servico_id == subq.c.ordem_servico_id) & (ApontamentoProducao.data_hora == subq.c.max_dt)
            ).all()
            ultimos_aps_map = {ap.ordem_servico_id: ap for ap in ultimos_aps_raw}
        else:
            ultimos_aps_map = {}
        timings['query_apontamentos_ms'] = int((time.perf_counter() - t0) * 1000)

        # 5. Processar dados (Batch Build)
        t0 = time.perf_counter()
        resultado_status = []
        agora_brt = datetime.now(LOCAL_TZ).replace(tzinfo=None)
        tolerancia = 0.15

        for os in all_os:
            # Filtro de pedidos entregues
            if excluir_entregues and any(p.pedido.status == 'entregue' for p in os.pedidos if p.pedido):
                continue

            # Identificar estado ativo
            ativos = apontamentos_ativos_os.get(os.id, [])
            status_obj = os.status_producao

            # Determinar status principal (se houver múltiplos, prioriza o mais recente)
            ap_principal = ativos[0] if ativos else None
            status_atual_label = 'Aguardando'
            if ap_principal:
                if ap_principal.tipo_acao == 'pausa': status_atual_label = 'Pausado'
                elif ap_principal.tipo_acao == 'inicio_producao': status_atual_label = 'Produção em andamento'
                elif ap_principal.tipo_acao == 'inicio_setup': status_atual_label = 'Setup em andamento'

            # Dados básicos
            info = {
                'id': os.id,
                'ordem_id': os.id,
                'os_numero': os.numero or f"OS-{os.id}",
                'status_atual': status_atual_label,
                'lista_kanban': os.status,
                'posicao': os.posicao
            }

            # Normalizar lista
            kl = map_lista_por_lower.get((os.status or '').strip().lower())
            if kl:
                info['lista_tipo'] = kl.tipo_servico
                info['lista_cor'] = kl.cor

            # Aplicar filtros de busca
            if lista_filters_set:
                ghost_listas = ghost_por_os[os.id]['listas_lower']
                if not ((os.status or '').lower() in lista_filters_set or ghost_listas.intersection(lista_filters_set)):
                    continue

            if lista_tipo_filter:
                ghost_tipos = ghost_por_os[os.id]['tipos_lower']
                if not (str(info.get('lista_tipo')).lower() == lista_tipo_filter or lista_tipo_filter in ghost_tipos):
                    continue

            # Agregação de clientes
            clientes_map = defaultdict(int)
            total_q = 0
            for po in os.pedidos:
                p = po.pedido
                if not p: continue
                q = p.quantidade or 0
                total_q += q
                clientes_map[p.cliente.nome if p.cliente else 'N/A'] += q

            info['quantidade_total'] = total_q
            info['clientes_quantidades'] = [{'cliente_nome': k, 'quantidade': v} for k, v in clientes_map.items()]
            info['cliente_nome'] = next(iter(clientes_map.keys())) if clientes_map else 'N/A'

            # Último apontamento e item/trabalho
            ult_ap = ultimos_aps_map.get(os.id)
            info['ultima_quantidade'] = ult_ap.quantidade if ult_ap else 0

            # Item e Trabalho (preferir do apontamento ativo, senão do último, senão do primeiro pedido)
            target_item = None
            target_trab = None
            if ap_principal:
                target_item = ap_principal.item
                target_trab = ap_principal.trabalho
                info['operador_nome'] = ap_principal.usuario.nome if ap_principal.usuario else 'N/A'
                info['inicio_acao'] = to_brt_iso(ap_principal.data_hora)
            elif ult_ap:
                target_item = ult_ap.item
                target_trab = ult_ap.trabalho
            elif os.pedidos and os.pedidos[0].pedido and os.pedidos[0].pedido.item:
                target_item = os.pedidos[0].pedido.item
                if target_item.trabalhos: target_trab = target_item.trabalhos[0].trabalho

            if target_item:
                info['item_id'] = target_item.id
                info['item_nome'] = target_item.nome
                info['item_codigo'] = target_item.codigo_acb
                info['item_imagem_path'] = target_item.imagem_path

            if target_trab:
                info['trabalho_id'] = target_trab.id
                info['trabalho_nome'] = target_trab.nome

            # Analytics Simplificado (evitando subqueries)
            info['resumo_status'] = {'setup': 0, 'pausado': 0, 'producao': 0}
            info['ativos_por_trabalho'] = []
            for ap in ativos:
                s = ap.tipo_acao
                if 'setup' in s: info['resumo_status']['setup'] += 1
                elif 'pausa' in s: info['resumo_status']['pausado'] += 1
                elif 'producao' in s: info['resumo_status']['producao'] += 1
                
                info['ativos_por_trabalho'].append({
                    'status': 'Setup' if 'setup' in s else ('Pausado' if 'pausa' in s else 'Produzindo'),
                    'inicio_acao': to_brt_iso(ap.data_hora),
                    'operador_nome': ap.usuario.nome if ap.usuario else 'N/A',
                    'trabalho_nome': ap.trabalho.nome if ap.trabalho else 'N/A'
                })

            # Ghosts
            if os.id in ghost_por_os:
                info['ghost_cards'] = ghost_por_os[os.id]['cards']

            resultado_status.append(info)

        timings['processing_ms'] = int((time.perf_counter() - t0) * 1000)
        
        # Ordenação final
        resultado_status.sort(key=lambda x: ((x.get('lista_kanban') or '').lower(), x.get('posicao') or 0))
        
        final_res = {'status_ativos': resultado_status}
        if (request.args.get('timing') or '').lower() in ['1', 'true']:
            final_res['timings'] = timings

        if hasattr(current_app, 'cache_store'):
            current_app.cache_store.set(cache_key, final_res, timeout=5)

        return jsonify(final_res)

    except Exception as e:
        logger.exception(f"Erro em status_ativos: {e}")
        return jsonify({'error': str(e)}), 500

@apontamento_bp.route('/detalhes/<int:ordem_id>', methods=['GET'])
def detalhes_ordem_servico(ordem_id):
    """Retorna análise detalhada completa de uma ordem de serviço"""
    try:
        # Buscar OS com eager loading de pedidos, itens e trabalhos
        ordem = OrdemServico.query.options(
            joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.cliente),
            joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.item).joinedload(Item.trabalhos)
        ).get_or_404(ordem_id)
        
        # Buscar todos os apontamentos desta OS com eager loading do operador e trabalho
        apontamentos = ApontamentoProducao.query.options(
            joinedload(ApontamentoProducao.usuario),
            joinedload(ApontamentoProducao.trabalho)
        ).filter_by(ordem_servico_id=ordem_id).order_by(ApontamentoProducao.data_hora.asc()).all()
        
        # Buscar informações do item e estimativas dos trabalhos
        item_info = {}
        estimativas_trabalhos = {}
        pedidos_info = []
        quantidade_total_os = 0
        
        if ordem.pedidos:
            # Coletar informações de todos os pedidos (usando dados pré-carregados)
            for pedido_os in ordem.pedidos:
                pedido_obj = pedido_os.pedido
                if pedido_obj:
                    quantidade_total_os += pedido_obj.quantidade or 0
                    cliente_obj = pedido_obj.cliente
                    pedidos_info.append({
                        'id': pedido_obj.id,
                        'quantidade': pedido_obj.quantidade or 0,
                        'cliente_nome': cliente_obj.nome if cliente_obj else 'N/A',
                        'numero_pedido_cliente': getattr(pedido_obj, 'numero_pedido_cliente', None) or 'N/A'
                    })
            
            # Buscar informações do primeiro item (usando dados pré-carregados)
            pedido_os_primeiro = ordem.pedidos[0]
            item_obj = pedido_os_primeiro.pedido.item if (pedido_os_primeiro.pedido and pedido_os_primeiro.pedido.item) else None
            if item_obj:
                item_info = {
                    'id': item_obj.id,
                    'nome': item_obj.nome,
                    'codigo': item_obj.codigo_acb,
                    'imagem_path': getattr(item_obj, 'imagem_path', None),
                    'quantidade_total': quantidade_total_os,
                    'pedidos': pedidos_info
                }

                # Buscar estimativas de todos os trabalhos do item (usando dados pré-carregados)
                for it in item_obj.trabalhos:
                    estimativas_trabalhos[it.trabalho_id] = {
                        'tempo_setup': it.tempo_setup or 0,
                        'tempo_peca': it.tempo_peca or 0
                    }
        
        # Agrupar apontamentos por tipo de trabalho
        trabalhos_analytics = {}
        
        for ap in apontamentos:
            trabalho_key = f"{ap.item_id}_{ap.trabalho_id}"
            
            if trabalho_key not in trabalhos_analytics:
                trabalho_obj = ap.trabalho
                trabalhos_analytics[trabalho_key] = {
                    'item_id': ap.item_id,
                    'trabalho_id': ap.trabalho_id,
                    'trabalho_nome': trabalho_obj.nome if trabalho_obj else 'N/A',
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
                'operador_nome': ap.usuario.nome if ap.usuario else 'N/A',
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
        
        # Calcular tempos estimados totais
        tempo_setup_estimado_total = 0
        tempo_producao_estimado_total = 0
        
        # Quantidade total já calculada acima
        
        # Calcular estimativas baseadas na quantidade total da OS
        for trabalho_key, dados in trabalhos_analytics.items():
            trabalho_id = dados['trabalho_id']
            if trabalho_id in estimativas_trabalhos:
                est = estimativas_trabalhos[trabalho_id]
                # Setup: uma vez por trabalho (independente da quantidade)
                tempo_setup_estimado_total += est['tempo_setup']
                # Produção: tempo por peça × quantidade total da OS
                if quantidade_total_os > 0:
                    tempo_producao_estimado_total += est['tempo_peca'] * quantidade_total_os
        
        tempo_estimado_total = tempo_setup_estimado_total + tempo_producao_estimado_total
        
        # Analytics por operador (tempos e quantidade)
        analytics_operadores = {}
        # Controle de última quantidade por trabalho (cumulativo) para somar apenas incrementos
        last_qty_by_trabalho = {}
        for trabalho_key, dados in trabalhos_analytics.items():
            # Iterar ordenando por data para calcular incrementos corretamente
            apts_ordenados = sorted(dados['apontamentos'], key=lambda x: x['data_hora'] or '')
            for ap in apts_ordenados:
                if ap['operador_id'] and ap['duracao_segundos'] is not None:
                    op_id = ap['operador_id']
                    if op_id not in analytics_operadores:
                        analytics_operadores[op_id] = {
                            'nome': ap['operador_nome'],
                            'tempo_setup': 0,
                            'tempo_producao': 0,
                            'tempo_pausas': 0,
                            'quantidade_total': 0,
                            'trabalhos': {}
                        }
                    
                    # Somar tempos por tipo de ação
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
                            'tempo_pausas': 0,
                            'quantidade': 0
                        }
                    
                    if ap['tipo_acao'] in ['inicio_setup', 'fim_setup']:
                        analytics_operadores[op_id]['trabalhos'][trabalho_nome]['tempo_setup'] += ap['duracao_segundos']
                    elif ap['tipo_acao'] in ['inicio_producao', 'fim_producao']:
                        analytics_operadores[op_id]['trabalhos'][trabalho_nome]['tempo_producao'] += ap['duracao_segundos']
                    elif ap['tipo_acao'] in ['pausa', 'stop']:
                        analytics_operadores[op_id]['trabalhos'][trabalho_nome]['tempo_pausas'] += ap['duracao_segundos']

                    # Quantidade: somar apenas incrementos em eventos de fim de produção
                    if ap['tipo_acao'] == 'fim_producao' and ap.get('quantidade') is not None:
                        try:
                            qtd_atual = int(ap.get('quantidade') or 0)
                        except Exception:
                            qtd_atual = 0
                        # Usar a chave do trabalho para pegar delta cumulativo desta linha de produção
                        key_trab = trabalho_key
                        last = last_qty_by_trabalho.get(key_trab, 0)
                        delta = qtd_atual - last
                        if delta > 0:
                            analytics_operadores[op_id]['quantidade_total'] += delta
                            analytics_operadores[op_id]['trabalhos'][trabalho_nome]['quantidade'] += delta
                            last_qty_by_trabalho[key_trab] = qtd_atual
        
        # Analytics por tipo de trabalho (estimado vs alcançado)
        analytics_trabalhos = {}
        for trabalho_key, dados in trabalhos_analytics.items():
            trabalho_id = dados['trabalho_id']
            trabalho_nome = dados['trabalho_nome']
            
            # Tempos reais
            tempo_setup_real = dados['setup_total']
            tempo_producao_real = dados['producao_total']
            tempo_pausas_real = dados['pausas_total']
            
            # Tempos estimados para este trabalho específico
            tempo_setup_estimado = 0
            tempo_producao_estimado = 0
            
            if trabalho_id in estimativas_trabalhos:
                est = estimativas_trabalhos[trabalho_id]
                tempo_setup_estimado = est['tempo_setup']
                if quantidade_total_os > 0:
                    tempo_producao_estimado = est['tempo_peca'] * quantidade_total_os
            
            # Calcular eficiências específicas
            eficiencia_setup = 0
            if tempo_setup_estimado > 0:
                eficiencia_setup = round((tempo_setup_estimado / tempo_setup_real * 100) if tempo_setup_real > 0 else 0, 1)
            
            eficiencia_producao = 0
            if tempo_producao_estimado > 0:
                eficiencia_producao = round((tempo_producao_estimado / tempo_producao_real * 100) if tempo_producao_real > 0 else 0, 1)
            
            tempo_total_estimado = tempo_setup_estimado + tempo_producao_estimado
            tempo_total_real = tempo_setup_real + tempo_producao_real + tempo_pausas_real
            eficiencia_total = round((tempo_total_estimado / tempo_total_real * 100) if tempo_total_real > 0 else 0, 1)
            
            analytics_trabalhos[trabalho_nome] = {
                'trabalho_id': trabalho_id,
                'trabalho_nome': trabalho_nome,
                'tempos_estimados': {
                    'setup': tempo_setup_estimado,
                    'producao': tempo_producao_estimado,
                    'total': tempo_total_estimado
                },
                'tempos_reais': {
                    'setup': tempo_setup_real,
                    'producao': tempo_producao_real,
                    'pausas': tempo_pausas_real,
                    'total': tempo_total_real
                },
                'eficiencias': {
                    'setup': eficiencia_setup,
                    'producao': eficiencia_producao,
                    'total': eficiencia_total
                },
                'quantidade': quantidade_total_os,
                'ultima_quantidade_apontada': dados['ultima_quantidade']
            }

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
                'tempo_setup_estimado_total': tempo_setup_estimado_total,
                'tempo_producao_estimado_total': tempo_producao_estimado_total,
                'tempo_estimado_total': tempo_estimado_total,
                'eficiencia_percentual': round((total_producao / (total_setup + total_producao + total_pausas) * 100) if (total_setup + total_producao + total_pausas) > 0 else 0, 1)
            },
            'analytics_trabalhos': analytics_trabalhos,
            'trabalhos': list(trabalhos_analytics.values()),
            'analytics_operadores': analytics_operadores
        }
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.exception(f"Falha ao buscar detalhes da OS {ordem_id}: {e}")
        return jsonify({'error': str(e)}), 500


@apontamento_bp.route('/quantidades-por-trabalho/<int:ordem_id>', methods=['GET'])
def quantidades_por_trabalho(ordem_id):
    """Retorna apenas a última quantidade apontada por trabalho da OS."""
    try:
        # Cache curto de 3 segundos para evitar múltiplas queries idênticas
        from flask import current_app
        cache_key = f"qpt:{ordem_id}"
        
        # Tentar buscar do cache
        try:
            if hasattr(current_app, 'cache_store'):
                cached = current_app.cache_store.get(cache_key)
                if cached:
                    logger.debug(f"[CACHE HIT] quantidades-por-trabalho OS {ordem_id}")
                    return jsonify(cached)
        except:
            pass
        
        subquery = (
            db.session.query(
                ApontamentoProducao.trabalho_id.label('trabalho_id'),
                func.max(ApontamentoProducao.data_hora).label('max_data_hora')
            )
            .filter(
                ApontamentoProducao.ordem_servico_id == ordem_id,
                ApontamentoProducao.quantidade.isnot(None),
                ApontamentoProducao.trabalho_id.isnot(None)
            )
            .group_by(ApontamentoProducao.trabalho_id)
            .subquery()
        )

        rows = (
            db.session.query(
                ApontamentoProducao.trabalho_id,
                Trabalho.nome.label('trabalho_nome'),
                ApontamentoProducao.quantidade.label('ultima_quantidade')
            )
            .join(
                subquery,
                (ApontamentoProducao.trabalho_id == subquery.c.trabalho_id)
                & (ApontamentoProducao.data_hora == subquery.c.max_data_hora)
            )
            .join(Trabalho, Trabalho.id == ApontamentoProducao.trabalho_id)
            .filter(ApontamentoProducao.ordem_servico_id == ordem_id)
            .order_by(Trabalho.nome.asc())
            .all()
        )

        resultado = {
            'ordem_servico_id': ordem_id,
            'trabalhos': [
                {
                    'trabalho_id': row.trabalho_id,
                    'trabalho_nome': row.trabalho_nome,
                    'ultima_quantidade': int(row.ultima_quantidade or 0)
                }
                for row in rows
            ]
        }
        
        # Cachear resultado por 3 segundos
        try:
            if hasattr(current_app, 'cache_store'):
                current_app.cache_store.set(cache_key, resultado, timeout=3)
        except:
            pass
        
        return jsonify(resultado)
    except Exception as e:
        logger.exception(f"Falha ao buscar quantidades por trabalho da OS {ordem_id}: {e}")
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
        
        # Validar código do operador com retry para evitar timeouts
        max_retries = 3
        usuario = None
        
        for attempt in range(max_retries):
            try:
                with db.session.no_autoflush:
                    usuario = Usuario.query.filter_by(codigo_operador=dados['codigo_operador']).first()
                    break
            except Exception as e:
                logger.warning(f"Tentativa {attempt + 1} de validar operador falhou: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Erro ao validar operador após {max_retries} tentativas")
                    return jsonify({'success': False, 'message': 'Erro ao validar código do operador. Tente novamente.'})
                time.sleep(0.1)  # Pequeno delay entre tentativas
        
        if not usuario:
            return jsonify({'success': False, 'message': 'Código de operador inválido'})

        try:
            ordem_servico_id = int(dados['ordem_servico_id'])
            item_id = int(dados['item_id'])
            trabalho_id = int(dados['trabalho_id'])
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'OS, item e trabalho devem ser identificadores numéricos válidos'})

        # Buscar status atual da OS para validar transições de estado
        status_atual = StatusProducaoOS.query.filter_by(ordem_servico_id=ordem_servico_id).first()
        estado_real = _obter_estado_real_os(ordem_servico_id)
        if status_atual:
            _aplicar_estado_real_status(status_atual, estado_real)
        tipo_acao = dados['tipo_acao']

        item_id_status = int(estado_real['item_id']) if estado_real and estado_real.get('item_id') else None
        trabalho_id_status = int(estado_real['trabalho_id']) if estado_real and estado_real.get('trabalho_id') else None

        ap_setup_aberto = estado_real['setup_aberto']
        ap_prod_aberto = estado_real['producao_aberta']
        ap_pausa_aberta = estado_real['pausa_aberta']
        ap_outro_operador_aberto = None

        if tipo_acao in ['inicio_setup', 'inicio_producao']:
            ap_setup_aberto = _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'inicio_setup')
        if tipo_acao == 'inicio_producao':
            ap_prod_aberto = _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'inicio_producao')
        if tipo_acao == 'inicio_producao':
            ap_pausa_aberta = _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'pausa')
        if tipo_acao in ['inicio_setup', 'inicio_producao']:
            ap_outro_operador_aberto = _buscar_apontamento_aberto_operador(usuario.id, ordem_servico_id)

        usar_par_status = (
            tipo_acao in ['fim_setup', 'pausa', 'stop', 'fim_producao']
            and item_id_status is not None
            and trabalho_id_status is not None
            and (item_id_status != item_id or trabalho_id_status != trabalho_id)
        )
        if usar_par_status:
            ap_setup_status = estado_real['setup_aberto']
            ap_prod_status = estado_real['producao_aberta']
            ap_pausa_status = estado_real['pausa_aberta']

            if tipo_acao == 'fim_setup' and ap_setup_status:
                item_id = item_id_status
                trabalho_id = trabalho_id_status
                ap_setup_aberto = ap_setup_status
            elif tipo_acao == 'pausa' and ap_prod_status:
                item_id = item_id_status
                trabalho_id = trabalho_id_status
                ap_prod_aberto = ap_prod_status
            elif tipo_acao == 'fim_producao' and ap_prod_status:
                item_id = item_id_status
                trabalho_id = trabalho_id_status
                ap_prod_aberto = ap_prod_status
            elif tipo_acao == 'stop' and (ap_prod_status or ap_pausa_status or ap_setup_status):
                item_id = item_id_status
                trabalho_id = trabalho_id_status
                ap_setup_aberto = ap_setup_status
                ap_prod_aberto = ap_prod_status
                ap_pausa_aberta = ap_pausa_status

        # REMOVIDO: Restrição de 1 OS por operador - agora permite múltiplas OS simultâneas
        # if ap_outro_operador_aberto is not None:
        #     ordem_aberta = OrdemServico.query.get(ap_outro_operador_aberto.ordem_servico_id)
        #     item_aberto = Item.query.get(ap_outro_operador_aberto.item_id) if ap_outro_operador_aberto.item_id else None
        #     trabalho_aberto = Trabalho.query.get(ap_outro_operador_aberto.trabalho_id) if ap_outro_operador_aberto.trabalho_id else None
        #     os_nome = getattr(ordem_aberta, 'numero', None) or getattr(ordem_aberta, 'codigo', None) or f"OS-{ap_outro_operador_aberto.ordem_servico_id}"
        #     item_nome = getattr(item_aberto, 'codigo_acb', None) or f"Item {ap_outro_operador_aberto.item_id}"
        #     trabalho_nome = getattr(trabalho_aberto, 'nome', None) or f"Trabalho {ap_outro_operador_aberto.trabalho_id}"
        #     tipo_aberto = {
        #         'inicio_setup': 'setup em andamento',
        #         'inicio_producao': 'produção em andamento',
        #         'pausa': 'pausa em aberto'
        #     }.get(ap_outro_operador_aberto.tipo_acao, 'apontamento em aberto')
        #     return jsonify({
        #         'success': False,
        #         'message': f'Este operador já possui {tipo_aberto} na {os_nome} ({item_nome} / {trabalho_nome}). Finalize ou aplique STOP antes de iniciar outra OS.'
        #     })

        if tipo_acao == 'inicio_setup':
            # Bloquear somente se já houver um setup em andamento para MESMO item/trabalho
            if ap_setup_aberto is not None:
                return jsonify({
                    'success': False,
                    'message': 'Já existe um setup em andamento para este item/trabalho nesta OS.'
                })

        if tipo_acao == 'fim_setup':
            # Deve existir um início de setup aberto para este item/trabalho
            ap_setup = ap_setup_aberto
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
            if ap_prod_aberto is not None:
                return jsonify({
                    'success': False,
                    'message': 'Já existe produção em andamento para este item/trabalho nesta OS.'
                })
            # Se houve início de setup para esta combinação e ainda não há fim_setup, exigir conclusão
            if ap_setup_aberto and ap_setup_aberto.data_fim is None:
                return jsonify({
                    'success': False,
                    'message': 'Conclua o setup deste item/trabalho antes de iniciar a produção.'
                })

        if tipo_acao == 'pausa':
            # Deve existir uma produção em andamento para esta combinação
            ap_prod = ap_prod_aberto
            if not ap_prod:
                return jsonify({'success': False, 'message': 'Não é possível pausar: não há produção em andamento para este item/trabalho.'})
            if ap_prod.usuario_id != usuario.id:
                op = Usuario.query.get(ap_prod.usuario_id)
                return jsonify({'success': False, 'message': f'Apenas o operador que iniciou a produção ({op.nome}) pode pausá-la.'})

        if tipo_acao == 'stop':
            # Pode parar produção em andamento, pausa aberta, ou setup em andamento para este par
            ap_prod = ap_prod_aberto
            ap_pausa = ap_pausa_aberta
            ap_setup = ap_setup_aberto

            if not ap_prod and not ap_pausa and not ap_setup:
                ap_operador_os = _buscar_apontamento_ativo_operador_na_os(usuario.id, ordem_servico_id)
                if ap_operador_os:
                    item_id = ap_operador_os.item_id
                    trabalho_id = ap_operador_os.trabalho_id
                    if ap_operador_os.tipo_acao == 'inicio_producao':
                        ap_prod = ap_operador_os
                        ap_prod_aberto = ap_operador_os
                    elif ap_operador_os.tipo_acao == 'pausa':
                        ap_pausa = ap_operador_os
                        ap_pausa_aberta = ap_operador_os
                    elif ap_operador_os.tipo_acao == 'inicio_setup':
                        ap_setup = ap_operador_os
                        ap_setup_aberto = ap_operador_os

            if not ap_prod and not ap_pausa and not ap_setup:
                return jsonify({'success': False, 'message': 'Não é possível aplicar STOP: não há apontamento ativo (produção/pausa/setup) para este item/trabalho.'})

            # Validar operador que abriu o apontamento ativo
            ap_base = ap_prod or ap_pausa or ap_setup
            if ap_base and ap_base.usuario_id != usuario.id:
                op = Usuario.query.get(ap_base.usuario_id)
                return jsonify({'success': False, 'message': f'Apenas o operador que iniciou ({op.nome}) pode aplicar STOP.'})

        if tipo_acao == 'fim_producao':
            # Deve existir uma produção em andamento para esta combinação
            ap_prod = ap_prod_aberto
            if not ap_prod:
                return jsonify({'success': False, 'message': 'Não é possível finalizar: não há produção em andamento para este item/trabalho.'})
            if ap_prod.usuario_id != usuario.id:
                op = Usuario.query.get(ap_prod.usuario_id)
                return jsonify({'success': False, 'message': f'Apenas o operador que iniciou a produção ({op.nome}) pode finalizá-la.'})
        
        # Validar se a OS existe
        ordem = OrdemServico.query.get(ordem_servico_id)
        if not ordem:
            return jsonify({'success': False, 'message': 'Ordem de serviço não encontrada'})
        
        # Validar se o item existe
        item = Item.query.get(item_id)
        if not item:
            return jsonify({'success': False, 'message': 'Item não encontrado'})
        
        # Validar se o tipo de trabalho existe
        trabalho = Trabalho.query.get(trabalho_id)
        if not trabalho:
            return jsonify({'success': False, 'message': 'Tipo de trabalho não encontrado'})
        
        # Validar se o tipo de trabalho está vinculado ao item
        item_trabalho = ItemTrabalho.query.filter_by(
            item_id=item_id,
            trabalho_id=trabalho_id
        ).first()
        if not item_trabalho:
            return jsonify({
                'success': False, 
                'message': f'O tipo de trabalho "{trabalho.nome}" não está vinculado ao item "{item.codigo_acb}"'
            })
        
        # Calcular última quantidade (independente por trabalho) para validação do input de quantidade
        ultima_quantidade = 0
        try:
            ultima_quantidade = _buscar_ultima_quantidade(ordem_servico_id, item_id, trabalho_id)
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
        # NOTA: Removido with_for_update() temporariamente por causar travamentos
        # A integridade é garantida pela transação e validações de estado
        status_os = status_atual or StatusProducaoOS.query.filter_by(
            ordem_servico_id=ordem_servico_id
        ).first()
        
        if not status_os:
            status_os = StatusProducaoOS(
                ordem_servico_id=ordem_servico_id,
                status_atual='Aguardando',
                operador_atual_id=usuario.id
            )
            db.session.add(status_os)
        
        agora = datetime.now(LOCAL_TZ).replace(tzinfo=None)
        
        # Atualizar status - pessimistic lock já garante integridade
        # Garantir que data_atualizacao seja sempre atualizada
        status_os.data_atualizacao = agora
        
        if tipo_acao == 'inicio_setup':
            status_os.status_atual = 'Setup em andamento'
            status_os.operador_atual_id = usuario.id
            status_os.item_atual_id = item_id
            status_os.trabalho_atual_id = trabalho_id
            status_os.inicio_acao = agora
            
        elif tipo_acao == 'fim_setup':
            status_os.status_atual = 'Setup concluído'
            
        elif tipo_acao == 'inicio_producao':
            status_os.status_atual = 'Produção em andamento'
            status_os.operador_atual_id = usuario.id
            status_os.item_atual_id = item_id
            status_os.trabalho_atual_id = trabalho_id
            status_os.inicio_acao = agora
            if dados.get('quantidade'):
                status_os.quantidade_atual = int(dados['quantidade'])
            # Se houver pausa aberta para este par, encerrá-la
            try:
                pausa_aberta = ap_pausa_aberta or _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'pausa')
                if pausa_aberta:
                    delta_pausa = agora - pausa_aberta.data_hora
                    pausa_aberta.data_fim = agora
                    pausa_aberta.tempo_decorrido = int(delta_pausa.total_seconds())
            except Exception:
                pass
                
        elif tipo_acao == 'pausa':
            status_os.status_atual = 'Pausado'
            status_os.operador_atual_id = usuario.id
            status_os.item_atual_id = item_id
            status_os.trabalho_atual_id = trabalho_id
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
            # CORREÇÃO: Preservar quantidade informada no STOP
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
        
        if tipo_acao in ['fim_setup', 'fim_producao', 'stop']:
            # Determinar qual tipo de início procurar
            tipo_inicio = {
                'fim_setup': 'inicio_setup',
                'fim_producao': 'inicio_producao',
                'stop': 'inicio_producao'
            }.get(tipo_acao)
            
            # Buscar o último apontamento de início correspondente
            apontamento_inicio = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == ordem_servico_id,
                ApontamentoProducao.item_id == item_id,
                ApontamentoProducao.trabalho_id == trabalho_id,
                ApontamentoProducao.tipo_acao == tipo_inicio,
                ApontamentoProducao.data_fim.is_(None)
            ).order_by(ApontamentoProducao.data_hora.desc()).first()
            # Se STOP e não encontrou produção aberta, tentar encerrar setup aberto
            if tipo_acao == 'stop' and not apontamento_inicio:
                apontamento_inicio = ap_setup_aberto or _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'inicio_setup')
            
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
                    pausa_aberta = ap_pausa_aberta or _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'pausa')
                    if pausa_aberta:
                        delta_pausa = agora - pausa_aberta.data_hora
                        pausa_aberta.data_fim = agora
                        pausa_aberta.tempo_decorrido = int(delta_pausa.total_seconds())
                    setup_aberto = ap_setup_aberto or _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'inicio_setup')
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
                ap_inicio_prod = ap_prod_aberto or _query_apontamento_aberto(ordem_servico_id, item_id, trabalho_id, 'inicio_producao')
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
            ordem_servico_id=ordem_servico_id,
            usuario_id=usuario.id,
            operador_id=usuario.id,  # Salvar operador_id para facilitar consultas
            item_id=item_id,
            trabalho_id=trabalho_id,
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
        
        # Preparar dados do apontamento para feedback imediato no frontend
        apontamento_data = None
        if tipo_acao in ['inicio_setup', 'inicio_producao', 'pausa']:
            # Buscar dados do trabalho e item para o chip
            trabalho = Trabalho.query.get(trabalho_id)
            
            # Preparar timestamp para o timer
            inicio_timestamp = to_brt_iso(agora)
            logger.info(f"[TIMER DEBUG] Timestamp gerado: {inicio_timestamp}")
            logger.info(f"[TIMER DEBUG] Agora (datetime): {agora}")
            logger.info(f"[TIMER DEBUG] Agora (isoformat): {agora.isoformat()}")
            
            apontamento_data = {
                'item_id': item_id,
                'trabalho_id': trabalho_id,
                'trabalho_nome': trabalho.nome if trabalho else f'Trabalho #{trabalho_id}',
                'status': status_os.status_atual,
                'operador_codigo': usuario.codigo_operador,
                'operador_nome': usuario.nome,
                'inicio_acao': inicio_timestamp
            }
            
            logger.info(f"[TIMER DEBUG] Apontamento data completo: {apontamento_data}")
        
        return jsonify({
            'success': True,
            'message': f'{acao_nome} registrado com sucesso!',
            'status': status_os.status_atual,
            'ultima_quantidade': ultima_quantidade,
            'quantidade_atual': int(status_os.quantidade_atual) if getattr(status_os, 'quantidade_atual', None) is not None else None,
            'apontamento': apontamento_data  # Dados para renderizar chip imediatamente
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao registrar apontamento: {e}")
        
        # TENTATIVA DE EMERGÊNCIA: Salvar apenas o apontamento básico sem status
        try:
            logger.warning("Tentando fallback de emergência para apontamento...")
            
            # Criar apontamento básico sem atualizar status_os
            apontamento_emergencia = ApontamentoProducao(
                ordem_servico_id=ordem_servico_id,
                usuario_id=usuario.id,
                operador_id=usuario.id,
                item_id=item_id,
                trabalho_id=trabalho_id,
                tipo_acao=tipo_acao,
                data_hora=agora,
                quantidade=int(dados['quantidade']) if dados.get('quantidade') else None,
                motivo_parada=dados.get('motivo_parada'),
                observacoes=dados.get('observacoes'),
                lista_kanban=ordem.status if 'ordem' in locals() else 'Produção'
            )
            
            db.session.add(apontamento_emergencia)
            db.session.commit()
            
            logger.info("Fallback de emergência bem-sucedido!")
            
            return jsonify({
                'success': True,
                'message': f'{tipo_acao} registrado (modo emergência)! Status pode precisar de atualização manual.',
                'emergency_mode': True,
                'status': 'Desconhecido'
            })
            
        except Exception as e2:
            logger.error(f"Fallback de emergência também falhou: {e2}")
            return jsonify({
                'success': False,
                'message': 'Sistema temporariamente indisponível. Tente novamente em alguns segundos.'
            })

@apontamento_bp.route('/os/<int:ordem_id>/reset', methods=['POST'])
def reset_apontamentos_os(ordem_id):
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autenticado'}), 401

    usuario_atual = Usuario.query.get(session['usuario_id'])
    if not usuario_atual or (usuario_atual.nivel_acesso not in ['admin'] and not usuario_atual.acesso_cadastros):
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403

    try:
        ordem = OrdemServico.query.get(ordem_id)
        if not ordem:
            return jsonify({'success': False, 'message': 'Ordem de serviço não encontrada'}), 404

        agora = datetime.now(LOCAL_TZ).replace(tzinfo=None)
        apontamentos_abertos = (
            ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == ordem_id,
                ApontamentoProducao.data_fim.is_(None)
            )
            .order_by(ApontamentoProducao.data_hora.asc())
            .all()
        )

        resetados = []
        for apontamento in apontamentos_abertos:
            data_base = apontamento.data_hora or agora
            tempo_decorrido = int(max((agora - data_base).total_seconds(), 0))
            apontamento.data_fim = agora
            apontamento.tempo_decorrido = tempo_decorrido
            resetados.append({
                'id': apontamento.id,
                'tipo_acao': apontamento.tipo_acao,
                'item_id': apontamento.item_id,
                'trabalho_id': apontamento.trabalho_id,
                'usuario_id': apontamento.usuario_id
            })

        status_os = StatusProducaoOS.query.filter_by(ordem_servico_id=ordem_id).first()
        if status_os:
            status_os.status_atual = 'Aguardando'
            status_os.operador_atual_id = None
            status_os.item_atual_id = None
            status_os.trabalho_atual_id = None
            status_os.inicio_acao = None
            status_os.motivo_pausa = None

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Reset da OS {ordem_id} concluído com sucesso',
            'ordem_servico_id': ordem_id,
            'apontamentos_fechados': len(resetados),
            'apontamentos': resetados,
            'status_resetado': bool(status_os)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao resetar OS: {str(e)}'}), 500

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
        # OTIMIZAÇÃO: Buscar apontamentos com joinedload para evitar N+1 queries
        apontamentos = ApontamentoProducao.query.options(
            joinedload(ApontamentoProducao.usuario),
            joinedload(ApontamentoProducao.item),
            joinedload(ApontamentoProducao.trabalho)
        ).filter_by(
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
            
            # Adicionar informações do operador (já carregado via joinedload)
            try:
                if hasattr(apontamento, 'usuario') and apontamento.usuario:
                    log_info['operador_id'] = apontamento.usuario.id
                    log_info['operador_nome'] = apontamento.usuario.nome
                elif hasattr(apontamento, 'operador_id') and apontamento.operador_id:
                    # Fallback caso usuario não esteja carregado
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
            
            # Adicionar informações do item (pré-carregado)
            try:
                item_obj = apontamento.item
                if item_obj:
                    log_info['item_id'] = item_obj.id
                    log_info['item_nome'] = item_obj.nome
                    log_info['item_codigo'] = item_obj.codigo_acb
            except Exception as e_item:
                logger.exception("Falha ao processar item para log %s", apontamento.id)
            
            # Adicionar informações do trabalho (pré-carregado)
            try:
                trab_obj = apontamento.trabalho
                if trab_obj:
                    log_info['trabalho_id'] = trab_obj.id
                    log_info['trabalho_nome'] = trab_obj.nome
            except Exception as e_trab:
                logger.exception("Falha ao processar trabalho para log %s", apontamento.id)
            
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


@apontamento_bp.route('/gerenciar-ativos')
def gerenciar_apontamentos_ativos():
    """Tela de gerenciamento de apontamentos ativos"""
    # Verificar se usuário está logado
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login'))
    
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('kanban.index'))
    
    # Verificar se tem permissão (admin ou pode_gerenciar_apontamentos)
    if usuario.nivel_acesso != 'admin' and not usuario.pode_gerenciar_apontamentos:
        flash('Acesso negado. Você não tem permissão para gerenciar apontamentos.', 'danger')
        return redirect(url_for('kanban.index'))
    
    # Paginação "Mostrar Mais": carregar 20 iniciais, depois +20 a cada clique
    limit = request.args.get('limit', 20, type=int)
    
    # Buscar somente apontamentos em andamento
    # NOTA: 'stop' não é incluído pois é apenas um marcador de fechamento
    apontamentos_query = ApontamentoProducao.query.options(
        joinedload(ApontamentoProducao.ordem_servico)
            .joinedload(OrdemServico.pedidos)
            .joinedload(PedidoOrdemServico.pedido),
        joinedload(ApontamentoProducao.usuario),
        joinedload(ApontamentoProducao.item),
        joinedload(ApontamentoProducao.trabalho)
    ).filter(
        ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa']),
        ApontamentoProducao.data_fim.is_(None)
    ).order_by(
        ApontamentoProducao.data_hora.desc()
    ).limit(limit).all()
    
    # Contar total de apontamentos em andamento disponíveis
    total_apontamentos = ApontamentoProducao.query.filter(
        ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa']),
        ApontamentoProducao.data_fim.is_(None)
    ).count()
    
    # Passar hora atual do servidor para calcular tempo decorrido no template
    server_now = datetime.now(LOCAL_TZ).replace(tzinfo=None)
    
    return render_template('apontamento/gerenciar_ativos.html', 
                         apontamentos=apontamentos_query,
                         total_apontamentos=total_apontamentos,
                         limit_atual=limit,
                         usuario=usuario,
                         server_now=server_now)


@apontamento_bp.route('/gerenciar-ultimos')
def gerenciar_ultimos_apontamentos():
    """Tela de gerenciamento dos últimos apontamentos (ativos e finalizados) com paginação"""
    # Verificar se usuário está logado
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login'))
    
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('kanban.index'))
    
    # Verificar se tem permissão (admin ou pode_gerenciar_apontamentos)
    if usuario.nivel_acesso != 'admin' and not usuario.pode_gerenciar_apontamentos:
        flash('Acesso negado. Você não tem permissão para gerenciar apontamentos.', 'danger')
        return redirect(url_for('kanban.index'))
    
    # Paginação: 20 apontamentos por página
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Buscar apontamentos com paginação
    # NOTA: Excluir 'stop' e 'fim_setup'/'fim_producao' pois são apenas marcadores de fechamento
    pagination = ApontamentoProducao.query.options(
        joinedload(ApontamentoProducao.ordem_servico)
            .joinedload(OrdemServico.pedidos)
            .joinedload(PedidoOrdemServico.pedido),
        joinedload(ApontamentoProducao.usuario),
        joinedload(ApontamentoProducao.item),
        joinedload(ApontamentoProducao.trabalho)
    ).filter(
        ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
    ).order_by(ApontamentoProducao.data_hora.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('apontamento/gerenciar_ultimos.html', 
                         apontamentos=pagination.items,
                         pagination=pagination,
                         usuario=usuario)


@apontamento_bp.route('/fechar-apontamento/<int:apontamento_id>', methods=['POST'])
def fechar_apontamento(apontamento_id):
    """Fechar um apontamento ativo"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 401
    
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 403
    
    # Verificar permissão
    if usuario.nivel_acesso != 'admin' and not usuario.pode_gerenciar_apontamentos:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        apontamento = ApontamentoProducao.query.get_or_404(apontamento_id)
        
        if apontamento.data_fim:
            return jsonify({'success': False, 'message': 'Apontamento já está fechado'}), 400
        
        # Fechar o apontamento
        agora = datetime.now(LOCAL_TZ).replace(tzinfo=None)
        apontamento.data_fim = agora
        
        # Calcular tempo decorrido
        if apontamento.data_hora:
            delta = agora - apontamento.data_hora
            apontamento.tempo_decorrido = int(delta.total_seconds())
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Apontamento fechado com sucesso'
        })
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Erro ao fechar apontamento {apontamento_id}")
        return jsonify({
            'success': False,
            'message': f'Erro ao fechar apontamento: {str(e)}'
        }), 500


@apontamento_bp.route('/editar-apontamento/<int:apontamento_id>', methods=['POST'])
def editar_apontamento(apontamento_id):
    """Editar um apontamento (Admin ou usuários com permissão)"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 401
    
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 403
    
    # Verificar permissão (admin OU pode_gerenciar_apontamentos)
    if usuario.nivel_acesso != 'admin' and not usuario.pode_gerenciar_apontamentos:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    try:
        apontamento = ApontamentoProducao.query.get_or_404(apontamento_id)
        dados = request.get_json()
        
        # Atualizar campos permitidos
        if 'quantidade' in dados:
            apontamento.quantidade = int(dados['quantidade'])
        
        if 'data_hora' in dados:
            # Parse do datetime
            try:
                nova_data = datetime.fromisoformat(dados['data_hora'].replace('Z', '+00:00'))
                apontamento.data_hora = nova_data.replace(tzinfo=None)
            except:
                return jsonify({'success': False, 'message': 'Formato de data inválido'}), 400
        
        if 'data_fim' in dados and dados['data_fim']:
            try:
                nova_data_fim = datetime.fromisoformat(dados['data_fim'].replace('Z', '+00:00'))
                apontamento.data_fim = nova_data_fim.replace(tzinfo=None)
                
                # Recalcular tempo decorrido
                if apontamento.data_hora and apontamento.data_fim:
                    delta = apontamento.data_fim - apontamento.data_hora
                    apontamento.tempo_decorrido = int(delta.total_seconds())
            except:
                return jsonify({'success': False, 'message': 'Formato de data fim inválido'}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Apontamento editado com sucesso'
        })
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Erro ao editar apontamento {apontamento_id}")
        return jsonify({
            'success': False,
            'message': f'Erro ao editar apontamento: {str(e)}'
        }), 500
