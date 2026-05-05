from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, make_response, abort, g
from models import db, Usuario, OrdemServico, Pedido, PedidoOrdemServico, Item, Trabalho, ItemTrabalho, RegistroMensal, KanbanLista, CartaoFantasma, ApontamentoProducao
from utils import validate_form_data, get_kanban_lists, get_kanban_categories, format_seconds_to_time
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json
import re

# Imports opcionais para otimizações (não quebrar se não disponíveis)
try:
    from utils.cache_manager import cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    cache = None

try:
    from utils.query_monitor import query_monitor, monitor_route_performance
    MONITOR_AVAILABLE = True
except ImportError:
    MONITOR_AVAILABLE = False
    # Decorator vazio se monitor não disponível
    def monitor_route_performance(f):
        return f

kanban = Blueprint('kanban', __name__)

# Listas Kanban que nunca podem ser removidas, renomeadas ou movimentadas
PROTECTED_LISTS = ['Entrada', 'Expedição']

# Verificação de permissão para todo o blueprint Kanban
@kanban.before_request
def verificar_permissao_kanban():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    # Otimização: Usar objeto usuário leve do g para evitar query desnecessária ao banco
    usuario = getattr(g, 'usuario', None)
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('auth.login'))

    # Admin possui acesso total
    if usuario.nivel_acesso == 'admin':
        return

    # Usuários comuns precisam ter acesso_kanban habilitado
    if not usuario.acesso_kanban:
        flash('Você não tem permissão para acessar a área Kanban', 'danger')
        return redirect(url_for('main.index'))

# Cache em memória simples para desenvolvimento (TTL: 5 minutos via chave temporal)
_kanban_memory_cache = {}

@kanban.route('/kanban')
@monitor_route_performance
@kanban.route('/kanban')
@monitor_route_performance
def index():
    """Rota para a página principal do Kanban otimizada para evitar N+1 queries"""
    # Limpar cache se solicitado
    if request.args.get('clear_cache') == '1':
        _kanban_memory_cache.clear()
        current_app.logger.info('🧹 Cache do Kanban limpo manualmente')

    listas = get_kanban_lists()

    if request.args.get('legacy') != '1':
        empty_cards = {lista: [] for lista in listas}
        return render_template(
            'kanban/index.html',
            listas=listas,
            ordens=empty_cards,
            cartoes_fantasma=empty_cards.copy(),
            tempos_listas={},
            quantidades_listas={},
            metricas_listas={},
            metricas_listas_json='{}',
            frontend_shell=True,
            Item=Item
        )

    # Tentar buscar do cache (TTL: 5 minutos)
    import time
    cache_key_global = f"kanban:global:{int(time.time() / 300)}"
    cached_data = _kanban_memory_cache.get(cache_key_global)
    if cached_data:
        current_app.logger.info(f"📦 Memory Cache HIT para Kanban")
        return render_template('kanban/index.html', **cached_data, Item=Item)
    
    current_app.logger.info(f"🔄 Cache MISS para Kanban - Iniciando processamento otimizado")
    
    categorias = get_kanban_categories()
    ordens = {lista: [] for lista in listas}
    cartoes_fantasma = {lista: [] for lista in listas}

    # 1. Buscar todas as OS ativas com Eager Loading completo
    all_active_os = OrdemServico.query.filter(OrdemServico.status.in_(listas))\
        .options(
            db.joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.item),
            db.joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.cliente)
        ).order_by(OrdemServico.posicao.asc(), OrdemServico.id.asc()).all()

    os_ids = [o.id for o in all_active_os]
    item_ids = set()
    for o in all_active_os:
        for p_os in o.pedidos:
            if p_os.pedido and p_os.pedido.item_id:
                item_ids.add(p_os.pedido.item_id)
        ordens[o.status].append(o)

    # 2. Batch query para ItemTrabalho e Trabalho
    todos_item_trabalhos = defaultdict(list)
    todos_trabalhos = {}
    if item_ids:
        it_rows = ItemTrabalho.query.filter(ItemTrabalho.item_id.in_(list(item_ids)))\
            .options(db.joinedload(ItemTrabalho.trabalho)).all()
        for it in it_rows:
            todos_item_trabalhos[it.item_id].append(it)
            if it.trabalho:
                todos_trabalhos[it.trabalho_id] = it.trabalho

    # 3. Batch query para Apontamentos (Sum decorrido)
    apontado_por_os_trabalho = defaultdict(lambda: defaultdict(int))
    if os_ids:
        apontado_rows = db.session.query(
            ApontamentoProducao.ordem_servico_id,
            ApontamentoProducao.trabalho_id,
            db.func.coalesce(db.func.sum(ApontamentoProducao.tempo_decorrido), 0)
        ).filter(ApontamentoProducao.ordem_servico_id.in_(os_ids))\
         .group_by(ApontamentoProducao.ordem_servico_id, ApontamentoProducao.trabalho_id).all()
        
        for os_id, trab_id, tempo in apontado_rows:
            if os_id and trab_id:
                apontado_por_os_trabalho[int(os_id)][int(trab_id)] = int(tempo or 0)

    # 4. Batch query para Cartões Fantasma
    all_fantasmas = CartaoFantasma.query.filter(CartaoFantasma.lista_kanban.in_(listas), CartaoFantasma.ativo == True)\
        .order_by(CartaoFantasma.posicao_fila).all()
    for f in all_fantasmas:
        cartoes_fantasma[f.lista_kanban].append(f)

    # 5. Cálculos de métricas por lista
    metricas_listas = {}
    tempos_listas = {}
    quantidades_listas = {}
    segundos_por_turno = 8 * 3600

    def _to_int(v, d=0):
        try: return int(v or d)
        except: return d

    def _tempo_label(s):
        total = max(0, _to_int(s))
        h, m = total // 3600, (total % 3600) // 60
        return f"{h}h {m:02d}m" if h > 0 else f"{m}m"

    def _badge_label(n):
        n = (n or '').strip()
        return n if len(n) <= 18 else f"{n[:18]}…"

    for lista in listas:
        l_tempo_estimado = 0
        l_tempo_apontado = 0
        l_quantidade = 0
        servicos_map = {}
        cards_data = []
        
        # Filtros de categoria
        categorias_norm = {c.lower().strip() for c, ls in categorias.items() if lista in ls}

        for os in ordens[lista]:
            c_estimado = 0
            c_apontado = 0
            c_qtd = 0
            c_servicos = []
            setup_seen = set()

            for p_os in os.pedidos:
                p = p_os.pedido
                if not p or not p.item_id: continue

                c_qtd += _to_int(p.quantidade)
                for it in todos_item_trabalhos.get(p.item_id, []):
                    trab = todos_trabalhos.get(it.trabalho_id)
                    if not trab: continue

                    # Validar se o serviço pertence a esta coluna
                    trab_cat = (trab.categoria or '').lower().strip()
                    if not any(ls_cat == lista and (not trab_cat or trab_cat == cat.lower().strip()) for cat, ls_cat in categorias.items() if lista in ls_cat):
                        continue

                    # Cálculo de tempos
                    t_peca = _to_int(it.tempo_real or it.tempo_peca)
                    t_setup = _to_int(it.tempo_setup)
                    q = _to_int(p.quantidade)

                    t_prod = t_peca * q
                    t_est = t_prod + (t_setup if it.trabalho_id not in setup_seen else 0)
                    setup_seen.add(it.trabalho_id)

                    t_ap = apontado_por_os_trabalho[os.id][it.trabalho_id]
                    t_rest = max(0, t_est - t_ap)

                    c_estimado += t_est
                    c_apontado += t_ap

                    # Agregar no serviço da lista
                    sk = str(it.trabalho_id)
                    if sk not in servicos_map:
                        servicos_map[sk] = {'id': it.trabalho_id, 'nome': trab.nome, 'nome_curto': _badge_label(trab.nome), 'tempo_estimado_total': 0, 'tempo_apontado_total': 0, 'quantidade_total': 0, 'cards_count': 0}
                    s = servicos_map[sk]
                    s['tempo_estimado_total'] += t_est
                    s['tempo_apontado_total'] += t_ap
                    s['quantidade_total'] += q
                    s['cards_count'] += 1

            l_tempo_estimado += c_estimado
            l_tempo_apontado += c_apontado
            l_quantidade += c_qtd

            cards_data.append({
                'ordem_id': os.id, 'ordem_numero': os.numero, 'quantidade_total': c_qtd,
                'tempo_estimado_total': c_estimado, 'tempo_apontado_total': c_apontado, 'tempo_restante_total': max(0, c_estimado - c_apontado)
            })

        # Finalizar métricas da lista
        servicos_list = sorted(servicos_map.values(), key=lambda x: (-(x['tempo_estimado_total'] - x['tempo_apontado_total']), x['nome']))
        for s in servicos_list:
            s['tempo_restante_total'] = max(0, s['tempo_estimado_total'] - s['tempo_apontado_total'])
            s['tempo_estimado_label'] = _tempo_label(s['tempo_estimado_total'])
            s['tempo_apontado_label'] = _tempo_label(s['tempo_apontado_total'])
            s['tempo_restante_label'] = _tempo_label(s['tempo_restante_total'])

        metricas_listas[lista] = {
            'lista': lista, 'cards_total': len(ordens[lista]), 'quantidade_total': l_quantidade,
            'tempo_estimado_total': l_tempo_estimado, 'tempo_apontado_total': l_tempo_apontado,
            'tempo_restante_total': max(0, l_tempo_estimado - l_tempo_apontado),
            'tempo_estimado_label': _tempo_label(l_tempo_estimado),
            'tempo_apontado_label': _tempo_label(l_tempo_apontado),
            'tempo_restante_label': _tempo_label(l_tempo_estimado - l_tempo_apontado),
            'servicos': servicos_list, 'servicos_ids': [s['id'] for s in servicos_list]
        }
        tempos_listas[lista] = l_tempo_estimado
        quantidades_listas[lista] = l_quantidade

    template_data = {
        'listas': listas, 'ordens': ordens, 'cartoes_fantasma': cartoes_fantasma,
        'tempos_listas': tempos_listas, 'quantidades_listas': quantidades_listas,
        'metricas_listas': metricas_listas, 'metricas_listas_json': json.dumps(metricas_listas)
    }
    _kanban_memory_cache[cache_key_global] = template_data
    return render_template('kanban/index.html', **template_data, Item=Item)
def mover_kanban():
    """Rota para mover uma ordem de serviço entre listas do Kanban"""
    # Validação de dados
    errors = validate_form_data(request.form, ['ordem_id', 'nova_lista'])
    if errors:
        return jsonify({'success': False, 'errors': errors})
    
    ordem_id = request.form['ordem_id']
    nova_lista = request.form['nova_lista']
    
    ordem = OrdemServico.query.get_or_404(ordem_id)
    old_status = ordem.status
    
    # Validar se pode mover para Expedição - não pode ter apontamentos abertos
    if nova_lista == 'Expedição':
        from models import ApontamentoProducao
        apontamentos_abertos = ApontamentoProducao.query.filter(
            ApontamentoProducao.ordem_servico_id == ordem_id,
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
        ).count()
        
        if apontamentos_abertos > 0:
            return jsonify({
                'success': False,
                'message': f'Não é possível mover para Expedição. Esta OS possui {apontamentos_abertos} apontamento(s) em aberto. Finalize todos os apontamentos antes de enviar para expedição.'
            })
    
    # Atualiza lista e posiciona no fim da lista de destino
    ordem.status = nova_lista
    max_pos = db.session.query(db.func.max(OrdemServico.posicao)).filter_by(status=nova_lista).scalar()
    ordem.posicao = (max_pos or 0) + 1
    
    # Reindexa a lista de origem para manter posições sequenciais
    if old_status and old_status != nova_lista:
        cards_origem = OrdemServico.query.filter_by(status=old_status)\
            .order_by(OrdemServico.posicao.asc(), OrdemServico.id.asc()).all()
        for idx, card in enumerate(cards_origem, start=1):
            card.posicao = idx
    
    db.session.commit()
    
    return jsonify({'success': True})

@kanban.route('/kanban/reordenar', methods=['POST'])
def reordenar_kanban():
    """Rota para reordenar cartões dentro da mesma lista do Kanban"""
    try:
        # Validação de dados
        errors = validate_form_data(request.form, ['ordem_id', 'nova_posicao', 'lista'])
        if errors:
            return jsonify({'success': False, 'errors': errors})
        
        ordem_id = request.form['ordem_id']
        nova_posicao = int(request.form['nova_posicao'])
        lista = request.form['lista']
        
        # Verificar se a ordem existe e está na lista correta
        ordem = OrdemServico.query.get_or_404(ordem_id)
        if ordem.status != lista:
            return jsonify({'success': False, 'message': 'Ordem não está na lista especificada'})
        
        # Obter todas as ordens da lista (excluindo a atual), ordenadas pela posição atual
        cards = OrdemServico.query\
            .filter_by(status=lista)\
            .order_by(OrdemServico.posicao.asc(), OrdemServico.id.asc()).all()
        
        # Construir a nova ordem de IDs
        ids = [c.id for c in cards if c.id != ordem.id]
        # Garantir faixa válida (1..len(ids)+1)
        nova_posicao = max(1, min(nova_posicao, len(ids) + 1))
        ids.insert(nova_posicao - 1, ordem.id)
        
        # Mapear id -> objeto para atualização eficiente
        card_by_id = {c.id: c for c in cards}
        card_by_id[ordem.id] = ordem
        
        # Reindexar posições sequenciais
        for idx, oid in enumerate(ids, start=1):
            card_by_id[oid].posicao = idx
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Posição atualizada para {nova_posicao}'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao reordenar: {str(e)}'})

@kanban.route('/kanban/enviar-para', methods=['POST'])
def enviar_para_lista():
    """Rota para enviar um cartão diretamente para uma lista específica"""
    # Validação de dados
    errors = validate_form_data(request.form, ['ordem_id', 'lista_destino'])
    if errors:
        return jsonify({'success': False, 'errors': errors})
    
    ordem_id = request.form['ordem_id']
    lista_destino = request.form['lista_destino']
    
    ordem = OrdemServico.query.get_or_404(ordem_id)
    old_status = ordem.status
    
    # Validar se pode mover para Expedição - não pode ter apontamentos abertos
    if lista_destino == 'Expedição':
        from models import ApontamentoProducao
        apontamentos_abertos = ApontamentoProducao.query.filter(
            ApontamentoProducao.ordem_servico_id == ordem_id,
            ApontamentoProducao.data_fim.is_(None),
            ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
        ).count()
        
        if apontamentos_abertos > 0:
            return jsonify({
                'success': False,
                'message': f'Não é possível enviar para Expedição. Esta OS possui {apontamentos_abertos} apontamento(s) em aberto. Finalize todos os apontamentos antes de enviar para expedição.'
            })
    
    # Envia para a lista de destino e posiciona no final
    ordem.status = lista_destino
    max_pos = db.session.query(db.func.max(OrdemServico.posicao)).filter_by(status=lista_destino).scalar()
    ordem.posicao = (max_pos or 0) + 1
    
    # Reindexa a lista de origem, se aplicável
    if old_status and old_status != lista_destino:
        cards_origem = OrdemServico.query.filter_by(status=old_status)\
            .order_by(OrdemServico.posicao.asc(), OrdemServico.id.asc()).all()
        for idx, card in enumerate(cards_origem, start=1):
            card.posicao = idx
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Cartão movido para {lista_destino}'
    })

@kanban.route('/kanban/finalizar', methods=['POST'])
def finalizar_kanban():
    """Rota para finalizar uma ordem de serviço"""
    # Validação de dados
    errors = validate_form_data(request.form, ['ordem_id'])
    if errors:
        return jsonify({'success': False, 'errors': errors})
    
    ordem_id = request.form['ordem_id']
    
    ordem = OrdemServico.query.get_or_404(ordem_id)
    ordem.status = 'Finalizado'
    
    # Atualizar data de entrega dos pedidos associados
    pedidos_originais_ids = set()
    for pedido_os in ordem.pedidos:
        pedido = Pedido.query.get(pedido_os.pedido_id)
        pedido.data_entrega = datetime.now().date()

        # Se for pedido virtual (AUTO-*), tentar concluir o pedido original do item composto
        if pedido and pedido.numero_pedido and pedido.numero_pedido.startswith('AUTO-'):
            m = re.search(r'-(\d+)$', pedido.numero_pedido)
            if m:
                try:
                    pedidos_originais_ids.add(int(m.group(1)))
                except Exception:
                    pass

    # Concluir pedidos originais somente quando todas OS dos componentes estiverem finalizadas
    for original_id in sorted(list(pedidos_originais_ids)):
        pedido_original = Pedido.query.get(original_id)
        if not pedido_original or pedido_original.data_entrega:
            continue

        # Buscar todos pedidos virtuais gerados para este pedido original
        virtuais = Pedido.query.filter(Pedido.numero_pedido.like(f"AUTO-%-{original_id}")).all()
        if not virtuais:
            continue

        # Coletar status das OS associadas aos pedidos virtuais
        os_status = []
        for pv in virtuais:
            for assoc in pv.ordens_servico or []:
                if assoc.ordem_servico:
                    os_status.append((assoc.ordem_servico_id, assoc.ordem_servico.status))

        # Sem OS associada -> não dá pra inferir conclusão
        if not os_status:
            continue

        # Considera concluído se todas as OS vinculadas aos componentes estiverem Finalizado
        if all(st == 'Finalizado' for _, st in os_status):
            pedido_original.data_entrega = datetime.now().date()
    
    # Adicionar ao registro mensal
    data_atual = datetime.now().date()
    mes_referencia = f"{data_atual.year}-{data_atual.month:02d}"
    
    registro = RegistroMensal(
        ordem_servico_id=ordem.id,
        data_finalizacao=data_atual,
        mes_referencia=mes_referencia
    )
    
    db.session.add(registro)
    db.session.commit()
    
    return jsonify({'success': True})

@kanban.route('/kanban/atualizar-tempo-real', methods=['POST'])
def atualizar_tempo_real():
    """Rota para atualizar o tempo real de um trabalho"""
    # Validação de dados
    errors = validate_form_data(request.form, ['item_trabalho_id', 'tempo_real'])
    if errors:
        return jsonify({'success': False, 'errors': errors})
    
    item_trabalho_id = request.form['item_trabalho_id']
    
    # Validar tempo real
    try:
        tempo_real = int(request.form['tempo_real'])
        if tempo_real < 0:
            return jsonify({'success': False, 'errors': ['O tempo real deve ser um número positivo']})
    except ValueError:
        return jsonify({'success': False, 'errors': ['O tempo real deve ser um número inteiro']})
    
    item_trabalho = ItemTrabalho.query.get_or_404(item_trabalho_id)
    item_trabalho.tempo_real = tempo_real
    db.session.commit()
    
    return jsonify({'success': True})

@kanban.route('/kanban/sincronizar-quantidade-pedido', methods=['POST'])
def sincronizar_quantidade_pedido():
    """Atualiza pedidos virtuais de componentes quando o pedido original do item composto foi alterado"""
    try:
        pedido_id = request.json.get('pedido_id')
        ordem_id = request.json.get('ordem_id')
        
        if not pedido_id or not ordem_id:
            return jsonify({'success': False, 'message': 'Pedido ID e Ordem ID são obrigatórios'}), 400
        
        pedido = Pedido.query.get_or_404(pedido_id)
        ordem = OrdemServico.query.get_or_404(ordem_id)
        
        # Verificar se é um pedido virtual de componente (AUTO-*)
        if pedido.numero_pedido and pedido.numero_pedido.startswith('AUTO-'):
            import re
            match = re.search(r'-(\d+)$', pedido.numero_pedido)
            if match:
                pedido_original_id = int(match.group(1))
                pedido_original = Pedido.query.get(pedido_original_id)
                
                if pedido_original and pedido_original.item_id:
                    item_composto = pedido_original.item
                    
                    if item_composto and item_composto.eh_composto:
                        # Encontrar a relação de componente
                        for comp_rel in item_composto.componentes:
                            if comp_rel.item_componente_id == pedido.item_id:
                                # Calcular nova quantidade
                                nova_quantidade = comp_rel.quantidade * pedido_original.quantidade
                                quantidade_antiga = pedido.quantidade
                                
                                # Atualizar quantidade do pedido virtual
                                pedido.quantidade = nova_quantidade
                                
                                # Atualizar snapshot
                                pedido_os = PedidoOrdemServico.query.filter_by(
                                    pedido_id=pedido.id,
                                    ordem_servico_id=ordem.id
                                ).first()
                                
                                if pedido_os:
                                    pedido_os.quantidade_snapshot = nova_quantidade
                                
                                db.session.commit()
                                
                                quantidade_total = sum(po.pedido.quantidade for po in ordem.pedidos)
                                
                                return jsonify({
                                    'success': True,
                                    'message': f'Quantidade atualizada de {quantidade_antiga} para {nova_quantidade} peças (baseado no pedido original: {pedido_original.quantidade} peças). Total na OS: {quantidade_total} peças',
                                    'quantidade_pedido': nova_quantidade,
                                    'quantidade_total_os': quantidade_total
                                })
        
        # Para pedidos normais (não AUTO), apenas retornar informação
        quantidade_total = sum(po.pedido.quantidade for po in ordem.pedidos)
        
        return jsonify({
            'success': True, 
            'message': f'Quantidade atual: {pedido.quantidade} peças. Total na OS: {quantidade_total} peças',
            'quantidade_pedido': pedido.quantidade,
            'quantidade_total_os': quantidade_total
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao sincronizar: {str(e)}'}), 500

@kanban.route('/kanban/detalhes/<int:ordem_id>')
def detalhes_kanban(ordem_id):
    """Rota para obter detalhes de uma ordem de serviço no Kanban otimizada"""
    ordem = OrdemServico.query.options(
        joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.cliente),
        joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.unidade_entrega),
        joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.item).joinedload(Item.trabalhos).joinedload(ItemTrabalho.trabalho)
    ).get_or_404(ordem_id)
    return render_template('kanban/detalhes_card.html', ordem=ordem, Item=Item)

@kanban.route('/registros-mensais')
def registros_mensais():
    """Rota para visualizar os registros mensais de cartões finalizados"""
    # Obter meses disponíveis
    meses_disponiveis = db.session.query(RegistroMensal.mes_referencia).distinct().all()
    meses_disponiveis = [mes[0] for mes in meses_disponiveis]
    meses_disponiveis = sorted([m for m in meses_disponiveis if m], reverse=True)
    
    # Obter mês selecionado (padrão: mês atual)
    data_atual = datetime.now().date()
    mes_atual = f"{data_atual.year}-{data_atual.month:02d}"
    mes_selecionado = (request.args.get('mes', mes_atual) or '').strip()
    if not meses_disponiveis:
        meses_disponiveis = [mes_atual]
    
    # Obter registros do mês selecionado (ou todos)
    if not mes_selecionado or mes_selecionado == 'todos':
        registros = RegistroMensal.query.order_by(RegistroMensal.data_finalizacao.desc(), RegistroMensal.id.desc()).all()
        mes_selecionado = 'todos'
    else:
        registros = RegistroMensal.query.filter_by(mes_referencia=mes_selecionado).all()
    
    return render_template('kanban/registros_mensais.html', 
                          registros=registros, 
                          meses_disponiveis=meses_disponiveis,
                          mes_selecionado=mes_selecionado)

# Rotas para gerenciar listas Kanban
@kanban.route('/listas')
def gerenciar_listas():
    """Rota para gerenciar as listas Kanban"""
    listas = KanbanLista.query.order_by(KanbanLista.ordem).all()
    tipos_servico = ['Serra', 'Torno CNC', 'Centro de Usinagem', 'Manual', 'Acabamento', 'Terceiros', 'Outros']
    return render_template('kanban/gerenciar_listas.html', listas=listas, tipos_servico=tipos_servico)

@kanban.route('/listas/criar', methods=['POST'])
def criar_lista():
    # Impedir criar lista com nome protegido
    if request.form['nome'].strip() in PROTECTED_LISTS:
        flash('Não é permitido criar uma lista com este nome reservado.', 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    """Rota para criar uma nova lista Kanban"""
    errors = validate_form_data(request.form, ['nome'])
    if errors:
        flash('Erro: ' + ', '.join(errors), 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    
    nome = request.form['nome'].strip()
    tipo_servico = request.form.get('tipo_servico', '')
    cor = request.form.get('cor', '#6c757d')
    
    # Verificar se já existe uma lista com esse nome
    if KanbanLista.query.filter_by(nome=nome).first():
        flash(f'Já existe uma lista com o nome "{nome}"', 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    
    # Obter a próxima ordem
    ultima_ordem = db.session.query(db.func.max(KanbanLista.ordem)).scalar() or 0
    
    nova_lista = KanbanLista(
        nome=nome,
        tipo_servico=tipo_servico,
        cor=cor,
        ordem=ultima_ordem + 1
    )
    
    db.session.add(nova_lista)
    db.session.commit()
    
    flash(f'Lista "{nome}" criada com sucesso!', 'success')
    return redirect(url_for('kanban.gerenciar_listas'))

@kanban.route('/listas/editar/<int:lista_id>', methods=['POST'])
def editar_lista(lista_id):
    lista = KanbanLista.query.get_or_404(lista_id)
    # Bloquear edição se lista protegida
    if lista.nome in PROTECTED_LISTS:
        flash('Esta lista é protegida e não pode ser editada.', 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    """Rota para editar uma lista Kanban"""
    lista = KanbanLista.query.get_or_404(lista_id)
    
    errors = validate_form_data(request.form, ['nome'])
    if errors:
        flash('Erro: ' + ', '.join(errors), 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    
    nome = request.form['nome'].strip()
    tipo_servico = request.form.get('tipo_servico', '')
    cor = request.form.get('cor', '#6c757d')
    ativa = 'ativa' in request.form
    
    # Verificar se já existe outra lista com esse nome
    lista_existente = KanbanLista.query.filter_by(nome=nome).first()
    if lista_existente and lista_existente.id != lista_id:
        flash(f'Já existe uma lista com o nome "{nome}"', 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    
    lista.nome = nome
    lista.tipo_servico = tipo_servico
    lista.cor = cor
    lista.ativa = ativa
    lista.data_atualizacao = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Lista "{nome}" atualizada com sucesso!', 'success')
    return redirect(url_for('kanban.gerenciar_listas'))

@kanban.route('/listas/reordenar', methods=['POST'])
def reordenar_listas():
    """Rota para reordenar as listas Kanban, mantendo listas protegidas nas posições extremas"""
    try:
        ordem_ids_raw = request.json.get('ordem', [])

        try:
            ordem_ids = [int(x) for x in ordem_ids_raw]
        except Exception:
            return jsonify({'success': False, 'message': 'Payload inválido: lista de IDs deve conter apenas números.'})

        # Buscar todas as listas no payload
        listas_db = {l.id: l for l in KanbanLista.query.filter(KanbanLista.id.in_(ordem_ids)).all()}
        if not ordem_ids:
            return jsonify({'success': False, 'message': 'Lista de ordem vazia.'})

        # FILTRAR: remover listas protegidas do payload - elas não podem ser reordenadas
        ordem_ids_filtrados = [lid for lid in ordem_ids if lid in listas_db and listas_db[lid].nome not in PROTECTED_LISTS]
        
        if not ordem_ids_filtrados:
            return jsonify({'success': False, 'message': 'Nenhuma lista válida para reordenar (listas protegidas não podem ser movidas).'})

        # Reordenar apenas as listas não protegidas
        for i, lista_id in enumerate(ordem_ids_filtrados):
            lista = listas_db.get(lista_id)
            if lista:
                # Listas não protegidas começam em 1
                lista.ordem = i + 1
                lista.data_atualizacao = datetime.utcnow()

        # Garantir que Entrada e Expedição tenham ordem correta (não podem ser alteradas)
        entrada = KanbanLista.query.filter_by(nome='Entrada').first()
        if entrada:
            entrada.ordem = 0
            entrada.data_atualizacao = datetime.utcnow()
        
        expedicao = KanbanLista.query.filter_by(nome='Expedição').first()
        if expedicao:
            expedicao.ordem = 1000
            expedicao.data_atualizacao = datetime.utcnow()

        db.session.commit()

        # Invalidar cache do Kanban para refletir a nova ordem imediatamente
        _kanban_memory_cache.clear()
        return jsonify({'success': True, 'message': 'Ordem das listas atualizada com sucesso!'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao reordenar listas: {str(e)}'})

@kanban.route('/listas/excluir/<int:lista_id>', methods=['POST'])
def excluir_lista(lista_id):
    lista = KanbanLista.query.get_or_404(lista_id)
    # Bloquear exclusão se lista protegida
    if lista.nome in PROTECTED_LISTS:
        flash('Esta lista é protegida e não pode ser excluída.', 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    """Rota para excluir uma lista Kanban"""
    lista = KanbanLista.query.get_or_404(lista_id)
    
    # Verificar se existem ordens de serviço nesta lista
    ordens_na_lista = OrdemServico.query.filter_by(status=lista.nome).count()
    if ordens_na_lista > 0:
        flash(f'Não é possível excluir a lista "{lista.nome}" pois existem {ordens_na_lista} cartões nela.', 'danger')
        return redirect(url_for('kanban.gerenciar_listas'))
    
    nome_lista = lista.nome
    db.session.delete(lista)
    db.session.commit()
    
    flash(f'Lista "{nome_lista}" excluída com sucesso!', 'success')
    return redirect(url_for('kanban.gerenciar_listas'))

# ===============================
# ROTAS PARA CARTÕES FANTASMA
# ===============================

@kanban.route('/cartao-fantasma/criar', methods=['POST'])
def criar_cartao_fantasma():
    """Criar um cartão fantasma em uma lista específica"""
    try:
        errors = validate_form_data(request.form, ['ordem_id', 'lista_destino'])
        if errors:
            return jsonify({
                'success': False,
                'errors': errors,
                'message': 'Dados inválidos: ' + ', '.join(errors)
            })
        
        try:
            ordem_id = int(request.form['ordem_id'])
        except Exception:
            return jsonify({
                'success': False,
                'message': 'Ordem de serviço inválida',
                'errors': ['ordem_id inválido']
            })
        lista_destino = request.form['lista_destino']
        trabalho_id = request.form.get('trabalho_id')
        posicao_fila = request.form.get('posicao_fila', 1)
        observacoes = request.form.get('observacoes', '')

        try:
            posicao_fila = int(posicao_fila)
        except Exception:
            return jsonify({
                'success': False,
                'message': 'Posição na fila inválida',
                'errors': ['posicao_fila inválida']
            })

        if trabalho_id:
            try:
                trabalho_id = int(trabalho_id)
            except Exception:
                return jsonify({
                    'success': False,
                    'message': 'Trabalho inválido',
                    'errors': ['trabalho_id inválido']
                })
        else:
            trabalho_id = None
        
        # Validar se a ordem existe
        ordem = OrdemServico.query.get_or_404(ordem_id)
        
        # Verificar se já existe um cartão fantasma nesta lista para esta OS
        fantasma_existente = CartaoFantasma.query.filter_by(
            ordem_servico_id=ordem_id,
            lista_kanban=lista_destino,
            ativo=True
        ).first()
        
        if fantasma_existente:
            return jsonify({
                'success': False, 
                'message': f'Já existe um cartão fantasma desta OS na lista {lista_destino}'
            })
        
        # Criar o cartão fantasma
        cartao_fantasma = CartaoFantasma(
            ordem_servico_id=ordem_id,
            lista_kanban=lista_destino,
            trabalho_id=trabalho_id,
            posicao_fila=posicao_fila,
            observacoes=observacoes,
            criado_por_id=session.get('usuario_id')
        )
        
        db.session.add(cartao_fantasma)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Cartão fantasma criado na lista {lista_destino}',
            'cartao_id': cartao_fantasma.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar cartão fantasma: {str(e)}'})

@kanban.route('/cartao-fantasma/remover/<int:cartao_id>', methods=['POST'])
def remover_cartao_fantasma(cartao_id):
    """Remover/desativar um cartão fantasma"""
    try:
        cartao = CartaoFantasma.query.get_or_404(cartao_id)
        cartao.ativo = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Cartão fantasma removido'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao remover cartão fantasma: {str(e)}'})

@kanban.route('/cartao-fantasma/mover', methods=['POST'])
def mover_cartao_fantasma():
    """Mover um cartão fantasma para outra posição na fila"""
    try:
        errors = validate_form_data(request.form, ['cartao_id', 'nova_posicao'])
        if errors:
            return jsonify({'success': False, 'errors': errors})
        
        try:
            cartao_id = int(request.form['cartao_id'])
            nova_posicao = int(request.form['nova_posicao'])
        except Exception:
            return jsonify({'success': False, 'message': 'Parâmetros inválidos'}), 400
        
        cartao = CartaoFantasma.query.get_or_404(cartao_id)
        lista_origem = cartao.lista_kanban
        lista_destino = request.form.get('nova_lista') or lista_origem

        current_app.logger.info(
            "Mover cartao fantasma id=%s lista_origem=%s lista_destino=%s nova_posicao=%s",
            cartao_id,
            lista_origem,
            lista_destino,
            nova_posicao,
        )

        # Se mudou de lista, aplicar a mudança antes de reordenar
        cartao.lista_kanban = lista_destino

        # Reordenar todos os cartões fantasma ativos da lista de destino para evitar posições duplicadas
        cartoes_destino = CartaoFantasma.query.filter_by(
            lista_kanban=lista_destino,
            ativo=True
        ).order_by(CartaoFantasma.posicao_fila.asc(), CartaoFantasma.id.asc()).all()

        ids = [c.id for c in cartoes_destino if c.id != cartao.id]
        nova_posicao = max(1, min(nova_posicao, len(ids) + 1))
        ids.insert(nova_posicao - 1, cartao.id)

        card_by_id = {c.id: c for c in cartoes_destino}
        card_by_id[cartao.id] = cartao

        for idx, cid in enumerate(ids, start=1):
            card_by_id[cid].posicao_fila = idx

        # Se mudou de lista, também reindexar a lista de origem para manter sequência
        if lista_origem != lista_destino:
            cartoes_origem = CartaoFantasma.query.filter_by(
                lista_kanban=lista_origem,
                ativo=True
            ).order_by(CartaoFantasma.posicao_fila.asc(), CartaoFantasma.id.asc()).all()
            for idx, c in enumerate(cartoes_origem, start=1):
                c.posicao_fila = idx

        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Cartão fantasma movido para posição {nova_posicao}',
            'nova_posicao': nova_posicao,
            'lista_origem': lista_origem,
            'lista_destino': lista_destino
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao mover cartão fantasma: {str(e)}'})

@kanban.route('/cartao-fantasma/detalhes/<int:cartao_id>')
def detalhes_cartao_fantasma(cartao_id):
    """Obter detalhes de um cartão fantasma"""
    cartao = CartaoFantasma.query.get_or_404(cartao_id)
    return render_template('kanban/detalhes_fantasma.html', cartao=cartao, Item=Item)

@kanban.route('/cartao-fantasma/listar-disponiveis/<lista_destino>')
def listar_ordens_disponiveis(lista_destino):
    """Listar ordens que podem virar cartão fantasma em uma lista"""
    try:
        # Buscar todas as ordens que não estão nesta lista e não têm cartão fantasma nela
        ordens_existentes_ids = db.session.query(CartaoFantasma.ordem_servico_id)\
            .filter_by(lista_kanban=lista_destino, ativo=True).subquery()
        
        ordens_disponiveis = OrdemServico.query\
            .options(db.joinedload(OrdemServico.pedidos).joinedload(PedidoOrdemServico.pedido).joinedload(Pedido.item))\
            .filter(OrdemServico.status != lista_destino)\
            .filter(~OrdemServico.id.in_(ordens_existentes_ids))\
            .filter(OrdemServico.status != 'Finalizado')\
            .all()
        
        ordens_data = []
        for ordem in ordens_disponiveis:
            for pedido_os in ordem.pedidos:
                pedido = pedido_os.pedido
                if not pedido: continue
                if pedido.item_id:
                    item_obj = pedido.item
                    ordens_data.append({
                        'id': ordem.id,
                        'numero': ordem.numero,
                        'item_nome': item_obj.nome if item_obj else pedido.nome_item,
                        'quantidade': pedido.quantidade,
                        'lista_atual': ordem.status
                    })
                    break  # Apenas o primeiro item para simplificar
        
        return jsonify({
            'success': True,
            'ordens': ordens_data
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao listar ordens: {str(e)}'})

@kanban.route('/cartao-fantasma/trabalhos/<int:ordem_id>')
def listar_trabalhos_ordem(ordem_id):
    """Listar trabalhos disponíveis para uma ordem específica"""
    try:
        ordem = OrdemServico.query.get_or_404(ordem_id)
        trabalhos_data = []
        
        for pedido_os in ordem.pedidos:
            pedido = pedido_os.pedido
            if pedido.item_id:
                item_trabalhos = ItemTrabalho.query.filter_by(item_id=pedido.item_id).all()
                for it in item_trabalhos:
                    trabalho = Trabalho.query.get(it.trabalho_id)
                    trabalhos_data.append({
                        'id': trabalho.id,
                        'nome': trabalho.nome,
                        'categoria': trabalho.categoria,
                        'tempo_setup': it.tempo_setup_formatado,
                        'tempo_peca': it.tempo_peca_formatado
                    })
                break  # Apenas o primeiro pedido para simplificar
        
        return jsonify({
            'success': True,
            'trabalhos': trabalhos_data
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao listar trabalhos: {str(e)}'})


# ===============================
# ROTAS PWA - CACHE E SYNC
# ===============================

@kanban.route('/kanban/full-data')
def full_data():
    """
    Retorna TODOS os dados do Kanban para cache local (PWA) de forma otimizada.
    Utiliza eager loading para evitar N+1 queries e reduzir latência com Vercel/Supabase.
    """
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 401
    
    try:
        # 1. Buscar todas as listas ativas
        listas = KanbanLista.query.filter_by(ativa=True).order_by(KanbanLista.ordem).all()
        listas_nomes = [l.nome for l in listas]
        listas_map = {l.nome: l for l in listas}
        
        # 2. Buscar TODOS os cartões reais ativos em uma única query com eager loading completo
        ordens_all = OrdemServico.query.filter(OrdemServico.status.in_(listas_nomes))\
            .options(
                db.joinedload(OrdemServico.pedidos)
                  .joinedload(PedidoOrdemServico.pedido)
                  .joinedload(Pedido.item),
                db.joinedload(OrdemServico.pedidos)
                  .joinedload(PedidoOrdemServico.pedido)
                  .joinedload(Pedido.cliente)
            ).all()

        cartoes = []
        for ordem in ordens_all:
            lista = listas_map.get(ordem.status)
            if lista:
                cartoes.append(_serialize_cartao(ordem, lista.id, False))
        
        # 3. Buscar TODOS os cartões fantasma em uma única query
        # Nota: models.py mostra lista_kanban como String, mas routes/kanban usava lista_kanban_id
        # Vamos usar o campo String conforme o model para garantir compatibilidade.
        fantasmas_all = CartaoFantasma.query.filter(
            CartaoFantasma.lista_kanban.in_(listas_nomes),
            CartaoFantasma.ativo == True
        ).options(
            db.joinedload(CartaoFantasma.ordem_servico)
              .joinedload(OrdemServico.pedidos)
              .joinedload(PedidoOrdemServico.pedido)
              .joinedload(Pedido.item)
        ).all()

        for fantasma in fantasmas_all:
            lista = listas_map.get(fantasma.lista_kanban)
            if lista:
                cartoes.append(_serialize_cartao_fantasma(fantasma, lista.id))

        # 4. Buscar apontamentos ativos (últimas 24h) de forma eficiente
        data_limite = datetime.now() - timedelta(days=1)
        apontamentos = ApontamentoProducao.query.filter(
            ApontamentoProducao.data_hora >= data_limite
        ).all()
        
        return jsonify({
            'success': True,
            'listas': [_serialize_lista(l) for l in listas],
            'cartoes': cartoes,
            'apontamentos': [_serialize_apontamento(a) for a in apontamentos],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        import traceback
        current_app.logger.error(f'[PWA] Erro no full-data otimizado: {str(e)}')
        current_app.logger.error(f'[PWA] Traceback: {traceback.format_exc()}')
        return jsonify({'success': False, 'message': f'Erro ao carregar dados: {str(e)}'}), 500


@kanban.route('/kanban/sync')
def sync():
    """
    Retorna apenas mudanças desde last_update (sync incremental)
    """
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 401
    
    try:
        last_update_str = request.args.get('last_update')
        if not last_update_str:
            return jsonify({'success': False, 'message': 'Parâmetro last_update obrigatório'}), 400
        
        # Parse do timestamp
        last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
        
        # Buscar cartões modificados/criados
        # Nota: Precisaria de campo updated_at em OrdemServico para isso funcionar perfeitamente
        # Por enquanto, retorna vazio (implementar depois)
        updated_cards = []
        deleted_cards = []
        new_cards = []
        
        # Buscar novos apontamentos
        new_apontamentos = ApontamentoProducao.query.filter(
            ApontamentoProducao.data_hora >= last_update
        ).all()
        
        has_changes = len(updated_cards) > 0 or len(deleted_cards) > 0 or len(new_cards) > 0 or len(new_apontamentos) > 0
        
        return jsonify({
            'success': True,
            'has_changes': has_changes,
            'updated_cards': updated_cards,
            'deleted_cards': deleted_cards,
            'new_cards': new_cards,
            'new_apontamentos': [_serialize_apontamento(a) for a in new_apontamentos],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f'Erro no sync: {str(e)}')
        return jsonify({'success': False, 'message': f'Erro ao sincronizar: {str(e)}'}), 500


# Helpers de serialização

def _serialize_lista(lista):
    """Serializa uma lista Kanban para JSON"""
    return {
        'id': lista.id,
        'nome': lista.nome,
        'cor': lista.cor,
        'ordem': lista.ordem,
        'tipo_servico': lista.tipo_servico,
        'ativa': lista.ativa
    }


def _serialize_cartao(ordem, lista_id, is_fantasma):
    """Serializa um cartão (OS) para JSON"""
    # Buscar primeiro pedido
    pedido_info = None
    item_id = None
    item_imagem_path = None
    itens = []
    search_parts = [ordem.numero or '']
    if ordem.pedidos and len(ordem.pedidos) > 0:
        pedido_os = ordem.pedidos[0]
        if pedido_os.pedido:
            pedido = pedido_os.pedido
            pedido_info = {
                'numero': pedido.numero_pedido,
                'quantidade': pedido.quantidade,
                'cliente': pedido.cliente.nome if pedido.cliente else None,
                'item_codigo': pedido.item.codigo_acb if pedido.item else None,
                'item_nome': pedido.item.nome if pedido.item else None
            }

    grouped_items = {}
    for pedido_os in getattr(ordem, 'pedidos', []) or []:
        pedido = getattr(pedido_os, 'pedido', None)
        if not pedido:
            continue

        cliente_nome = pedido.cliente.nome if pedido.cliente else ''
        numero_cliente = pedido.numero_pedido_cliente or ''
        item_codigo = pedido.item.codigo_acb if pedido.item else ''
        item_nome = pedido.item.nome if pedido.item else (pedido.nome_item or '')

        search_parts.extend([
            cliente_nome,
            numero_cliente,
            item_codigo,
            item_nome,
            pedido.nome_item or ''
        ])

        if pedido.item and not item_id:
            item_id = pedido.item.id
        if pedido.item and getattr(pedido.item, 'imagem_path', None) and not item_imagem_path:
            item_imagem_path = pedido.item.imagem_path

        item_key = pedido.item_id if pedido.item_id else (pedido.nome_item or f'pedido-{pedido.id}')
        item_label = f"{item_codigo} - {item_nome}".strip(' -') or pedido.nome_item or 'Item sem nome'

        if item_key not in grouped_items:
            grouped_items[item_key] = {
                'nome': item_label,
                'quantidade': pedido.quantidade or 0
            }
        else:
            grouped_items[item_key]['quantidade'] += pedido.quantidade or 0

    itens = list(grouped_items.values())
    
    # Converter data_criacao para string
    data_criacao_str = None
    if ordem.data_criacao:
        try:
            data_criacao_str = ordem.data_criacao.isoformat()
        except:
            data_criacao_str = str(ordem.data_criacao)
    
    return {
        'id': ordem.id,
        'ordem_id': ordem.id,
        'numero': ordem.numero,
        'lista_id': lista_id,
        'lista_nome': ordem.status,
        'posicao': ordem.posicao,
        'is_fantasma': is_fantasma,
        'pedido': pedido_info,
        'data_criacao': data_criacao_str,
        'item_id': item_id,
        'item_imagem_path': item_imagem_path,
        'itens': itens,
        'search_text': ' '.join([part for part in search_parts if part]).strip()
    }


def _serialize_cartao_fantasma(fantasma, lista_id=None):
    """Serializa um cartão fantasma para JSON de forma segura"""
    ordem = fantasma.ordem_servico
    if not ordem:
        return None

    return {
        'id': f'fantasma-{fantasma.id}',
        'fantasma_id': fantasma.id,
        'ordem_id': ordem.id,
        'numero': ordem.numero,
        'lista_id': lista_id,
        'lista_nome': fantasma.lista_kanban,
        'posicao': getattr(fantasma, 'posicao_fila', 0),
        'is_fantasma': True,
        'trabalho_id': fantasma.trabalho_id,
        'trabalho_nome': fantasma.trabalho.nome if fantasma.trabalho else None,
        'search_text': f"{ordem.numero} {fantasma.trabalho.nome if fantasma.trabalho else ''}".strip()
    }


def _serialize_apontamento(apontamento):
    """Serializa um apontamento para JSON"""
    # Converter data_hora para string
    data_hora_str = None
    if apontamento.data_hora:
        try:
            data_hora_str = apontamento.data_hora.isoformat()
        except:
            data_hora_str = str(apontamento.data_hora)
    
    return {
        'id': apontamento.id,
        'ordem_servico_id': apontamento.ordem_servico_id,
        'tipo_acao': apontamento.tipo_acao,
        'data_hora': data_hora_str,
        'quantidade': apontamento.quantidade,
        'lista_kanban': apontamento.lista_kanban
    }
