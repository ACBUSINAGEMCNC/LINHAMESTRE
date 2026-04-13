from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, make_response, abort
from models import db, Usuario, OrdemServico, Pedido, PedidoOrdemServico, Item, Trabalho, ItemTrabalho, RegistroMensal, KanbanLista, CartaoFantasma, ApontamentoProducao
from utils import validate_form_data, get_kanban_lists, get_kanban_categories, format_seconds_to_time
from utils.cache_manager import cache
from utils.query_monitor import query_monitor, monitor_route_performance
from datetime import datetime
from collections import defaultdict
import json
import re

kanban = Blueprint('kanban', __name__)

# Listas Kanban que nunca podem ser removidas, renomeadas ou movimentadas
PROTECTED_LISTS = ['Entrada', 'Expedição']

# Verificação de permissão para todo o blueprint Kanban
@kanban.before_request
def verificar_permissao_kanban():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    usuario = Usuario.query.get(session['usuario_id'])
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

@kanban.route('/kanban')
@monitor_route_performance
def index():
    """Rota para a página principal do Kanban"""
    # Tentar buscar do cache (TTL: 2 minutos)
    usuario_id = session.get('usuario_id')
    cache_key = f"kanban:metricas:{usuario_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        current_app.logger.info(f"📦 Cache HIT para Kanban (usuário {usuario_id})")
        return render_template('kanban/index.html', **cached_data, Item=Item)
    
    current_app.logger.info(f"🔄 Cache MISS para Kanban (usuário {usuario_id})")
    listas = get_kanban_lists()
    categorias = get_kanban_categories()
    
    ordens = {}
    cartoes_fantasma = {}
    tempos_listas = {}
    quantidades_listas = {}
    metricas_listas = {}

    turnos_por_dia = 3
    horas_por_turno = 8
    segundos_por_turno = horas_por_turno * 3600

    def _to_int(value, default=0):
        try:
            if value is None:
                return default
            return int(value)
        except Exception:
            return default

    def _tempo_label(segundos):
        total = max(0, _to_int(segundos, 0))
        horas = total // 3600
        minutos = (total % 3600) // 60
        if horas > 0:
            return f"{horas}h {minutos:02d}m"
        return f"{minutos}m"

    def _badge_label(nome):
        base = (nome or '').strip()
        if not base:
            return 'Serviço'
        return base if len(base) <= 18 else f"{base[:18].rstrip()}…"

    def _card_title(ordem):
        pedido_os = (getattr(ordem, 'pedidos', None) or [None])[0]
        pedido = getattr(pedido_os, 'pedido', None)
        item = getattr(pedido, 'item', None)
        item_nome = ''
        if item and getattr(item, 'nome', None):
            item_nome = item.nome
        elif pedido and getattr(pedido, 'nome_item', None):
            item_nome = pedido.nome_item
        return (item_nome or ordem.numero or f"OS {ordem.id}").strip()

    def _card_qty(ordem):
        total = 0
        for pedido_os in getattr(ordem, 'pedidos', []) or []:
            pedido = getattr(pedido_os, 'pedido', None)
            total += _to_int(getattr(pedido, 'quantidade', 0), 0)
        return total

    # Buscar IDs de todas as OS no Kanban para filtrar apontamentos
    todas_os_ids = db.session.query(OrdemServico.id).filter(
        OrdemServico.status.in_(listas)
    ).all()
    os_ids_set = {os_id for (os_id,) in todas_os_ids}
    
    # Query otimizada: apenas apontamentos das OS visíveis no Kanban
    apontado_rows = (
        db.session.query(
            ApontamentoProducao.ordem_servico_id,
            ApontamentoProducao.trabalho_id,
            db.func.coalesce(db.func.sum(ApontamentoProducao.tempo_decorrido), 0)
        )
        .filter(ApontamentoProducao.ordem_servico_id.in_(os_ids_set))
        .group_by(ApontamentoProducao.ordem_servico_id, ApontamentoProducao.trabalho_id)
        .all()
    )
    apontado_por_os_trabalho = defaultdict(dict)
    for ordem_id, trabalho_id, tempo_total in apontado_rows:
        if ordem_id is None or trabalho_id is None:
            continue
        apontado_por_os_trabalho[int(ordem_id)][int(trabalho_id)] = _to_int(tempo_total, 0)

    for lista in listas:
        # Buscar ordens normais com eager loading para evitar N+1 queries
        ordens[lista] = OrdemServico.query.filter_by(status=lista)\
            .options(
                db.joinedload(OrdemServico.pedidos)
                  .joinedload(PedidoOrdemServico.pedido)
                  .joinedload(Pedido.item),
                db.joinedload(OrdemServico.pedidos)
                  .joinedload(PedidoOrdemServico.pedido)
                  .joinedload(Pedido.cliente)
            )\
            .order_by(OrdemServico.posicao.asc(), OrdemServico.id.asc()).all()
        
        # Buscar cartões fantasma ativos para esta lista
        cartoes_fantasma[lista] = CartaoFantasma.query.filter_by(
            lista_kanban=lista, 
            ativo=True
        ).order_by(CartaoFantasma.posicao_fila).all()
        
        # Calcular tempos e quantidades para cada lista
        tempo_total = 0
        quantidade_total = 0
        tempo_apontado_total = 0
        tempo_restante_total = 0
        servicos_lista = {}
        cards_metricas = []
        categorias_da_lista = [categoria for categoria, listas_categoria in categorias.items() if lista in listas_categoria]
        categorias_norm = {str(cat).strip().lower() for cat in categorias_da_lista if cat}
        
        # Contar ordens normais
        for ordem in ordens[lista]:
            card_estimado = 0
            card_apontado = 0
            card_qtd = 0
            card_servicos = []
            for pedido_os in ordem.pedidos:
                pedido = pedido_os.pedido
                if pedido.item_id:
                    quantidade_total += pedido.quantidade
                    card_qtd += _to_int(pedido.quantidade, 0)
                    
                    # Calcular tempo total para os trabalhos da categoria correspondente
                    for item_trabalho in ItemTrabalho.query.filter_by(item_id=pedido.item_id).all():
                        trabalho = Trabalho.query.get(item_trabalho.trabalho_id)
                        if not trabalho:
                            continue
                        trabalho_categoria = (trabalho.categoria or '').strip().lower()
                        incluir = False
                        
                        # Verificar se o trabalho pertence à categoria da lista atual
                        for categoria, listas_categoria in categorias.items():
                            categoria_norm = (categoria or '').strip().lower()
                            if lista in listas_categoria and (trabalho_categoria == categoria_norm or not trabalho.categoria):
                                incluir = True
                                break
                        if not incluir:
                            continue

                        tempo_peca = _to_int(item_trabalho.tempo_real or item_trabalho.tempo_peca, 0)
                        tempo_setup = _to_int(item_trabalho.tempo_setup, 0)
                        qtd_pedido = _to_int(pedido.quantidade, 0)
                        tempo_estimado_servico = (tempo_peca * qtd_pedido) + tempo_setup
                        tempo_apontado_servico = apontado_por_os_trabalho.get(ordem.id, {}).get(item_trabalho.trabalho_id, 0)
                        tempo_restante_servico = max(0, tempo_estimado_servico - tempo_apontado_servico)

                        tempo_total += tempo_estimado_servico
                        card_estimado += tempo_estimado_servico
                        card_apontado += tempo_apontado_servico

                        chave_servico = str(item_trabalho.trabalho_id)
                        if chave_servico not in servicos_lista:
                            servicos_lista[chave_servico] = {
                                'id': item_trabalho.trabalho_id,
                                'nome': trabalho.nome,
                                'nome_curto': _badge_label(trabalho.nome),
                                'categoria': trabalho.categoria or '',
                                'tempo_estimado_total': 0,
                                'tempo_apontado_total': 0,
                                'quantidade_total': 0,
                                'cards_count': 0
                            }
                        servicos_lista[chave_servico]['tempo_estimado_total'] += tempo_estimado_servico
                        servicos_lista[chave_servico]['tempo_apontado_total'] += tempo_apontado_servico
                        servicos_lista[chave_servico]['quantidade_total'] += qtd_pedido
                        servicos_lista[chave_servico]['cards_count'] += 1

                        card_servicos.append({
                            'id': item_trabalho.trabalho_id,
                            'nome': trabalho.nome,
                            'nome_curto': _badge_label(trabalho.nome),
                            'categoria': trabalho.categoria or '',
                            'tempo_estimado': tempo_estimado_servico,
                            'tempo_apontado': tempo_apontado_servico,
                            'tempo_restante': tempo_restante_servico,
                            'quantidade': qtd_pedido
                        })

            card_restante = max(0, card_estimado - card_apontado)
            tempo_apontado_total += card_apontado
            tempo_restante_total += card_restante
            cards_metricas.append({
                'ordem_id': ordem.id,
                'ordem_numero': ordem.numero,
                'titulo': _card_title(ordem),
                'quantidade_total': card_qtd,
                'tempo_estimado_total': card_estimado,
                'tempo_apontado_total': card_apontado,
                'tempo_restante_total': card_restante,
                'servicos': card_servicos
            })
        
        # Contar cartões fantasma (apenas para visualização, não duplicar tempo/quantidade)
        for cartao_fantasma in cartoes_fantasma[lista]:
            # Os cartões fantasma não adicionam tempo/quantidade pois são referências
            pass
        
        tempos_listas[lista] = tempo_total
        quantidades_listas[lista] = quantidade_total
        cards_metricas_ordenados = sorted(cards_metricas, key=lambda card: ((card.get('ordem_numero') or ''), card.get('ordem_id') or 0))
        primeiro_card = cards_metricas_ordenados[0] if cards_metricas_ordenados else None
        if primeiro_card:
            turnos_primeiro = (primeiro_card['tempo_restante_total'] / segundos_por_turno) if segundos_por_turno else 0
        else:
            turnos_primeiro = 0

        for serv in servicos_lista.values():
            serv['tempo_restante_total'] = max(0, serv['tempo_estimado_total'] - serv['tempo_apontado_total'])

        servicos_ordenados = sorted(
            servicos_lista.values(),
            key=lambda serv: (-serv['tempo_restante_total'], serv['nome'])
        )
        for serv in servicos_ordenados:
            serv['tempo_estimado_label'] = _tempo_label(serv['tempo_estimado_total'])
            serv['tempo_apontado_label'] = _tempo_label(serv['tempo_apontado_total'])
            serv['tempo_restante_label'] = _tempo_label(serv['tempo_restante_total'])

        cards_topo = sorted(cards_metricas_ordenados, key=lambda card: (-card['tempo_restante_total'], card['ordem_numero'] or ''))[:3]
        for card in cards_topo:
            card['tempo_estimado_label'] = _tempo_label(card['tempo_estimado_total'])
            card['tempo_apontado_label'] = _tempo_label(card['tempo_apontado_total'])
            card['tempo_restante_label'] = _tempo_label(card['tempo_restante_total'])

        if primeiro_card:
            primeiro_card = dict(primeiro_card)
            primeiro_card['tempo_estimado_label'] = _tempo_label(primeiro_card['tempo_estimado_total'])
            primeiro_card['tempo_apontado_label'] = _tempo_label(primeiro_card['tempo_apontado_total'])
            primeiro_card['tempo_restante_label'] = _tempo_label(primeiro_card['tempo_restante_total'])

        metricas_listas[lista] = {
            'lista': lista,
            'cards_total': len(ordens[lista]),
            'quantidade_total': quantidade_total,
            'tempo_estimado_total': tempo_total,
            'tempo_apontado_total': tempo_apontado_total,
            'tempo_restante_total': tempo_restante_total,
            'tempo_estimado_label': _tempo_label(tempo_total),
            'tempo_apontado_label': _tempo_label(tempo_apontado_total),
            'tempo_restante_label': _tempo_label(tempo_restante_total),
            'servicos': servicos_ordenados,
            'servicos_ids': [serv['id'] for serv in servicos_ordenados],
            'cards_topo': cards_topo,
            'primeiro_card': primeiro_card,
            'turnos_primeiro_card': round(turnos_primeiro, 1),
            'turnos_primeiro_card_label': f"{round(turnos_primeiro, 1):.1f}" if primeiro_card else '0.0',
            'turnos_por_dia': turnos_por_dia,
            'horas_por_turno': horas_por_turno,
            'categorias': list(categorias_da_lista),
            'cards_metricas': cards_metricas_ordenados
        }

    template_obj = current_app.jinja_env.get_template('kanban/index.html')
    template_filename = getattr(template_obj, 'filename', None)
    current_app.logger.warning('KANBAN_TEMPLATE_FILE=%s', template_filename)

    # Preparar dados para cache e template
    template_data = {
        'listas': listas,
        'ordens': ordens,
        'cartoes_fantasma': cartoes_fantasma,
        'tempos_listas': tempos_listas,
        'quantidades_listas': quantidades_listas,
        'metricas_listas': metricas_listas,
        'metricas_listas_json': json.dumps(metricas_listas)
    }
    
    # Cachear dados por 2 minutos (120 segundos)
    cache.set(cache_key, template_data, ttl=120)
    current_app.logger.info(f" Dados do Kanban cacheados para usuário {usuario_id}")
    
    return render_template('kanban/index.html', **template_data, Item=Item)

@kanban.route('/kanban/por-numero/<path:numero>')
def abrir_os_por_numero(numero):
    """Atalho: abrir o Kanban a partir do número da OS (ex: OS-00001)."""
    ordem = OrdemServico.query.filter_by(numero=numero).first()
    if not ordem:
        abort(404)
    return redirect(url_for('kanban.index', ordem_id=ordem.id))


@kanban.route('/kanban/por-pedido/<int:pedido_id>')
def abrir_os_por_pedido(pedido_id):
    """Atalho: abrir o Kanban a partir de um Pedido.

    - Se houver 1 OS associada ao pedido, abre direto.
    - Se houver várias OS (ex.: item composto), mostra uma tela para selecionar qual OS abrir.
    """
    pedido = Pedido.query.get_or_404(pedido_id)

    # OS diretamente associadas ao pedido (item simples)
    ordens_set = {}
    for assoc in getattr(pedido, 'ordens_servico', []) or []:
        os_obj = getattr(assoc, 'ordem_servico', None)
        if os_obj and os_obj.id not in ordens_set:
            ordens_set[os_obj.id] = os_obj

    # Para item composto, buscar OS através dos pedidos virtuais AUTO-...-{pedido_original_id}
    if (not ordens_set) and pedido and getattr(pedido, 'item', None) and getattr(pedido.item, 'eh_composto', False):
        virtuais = Pedido.query.filter(Pedido.numero_pedido.like(f"AUTO-%-{pedido.id}")).all()
        for pv in virtuais:
            for assoc in getattr(pv, 'ordens_servico', []) or []:
                os_obj = getattr(assoc, 'ordem_servico', None)
                if os_obj and os_obj.id not in ordens_set:
                    ordens_set[os_obj.id] = os_obj

    ordens = list(ordens_set.values())
    ordens.sort(key=lambda o: (o.numero or '', o.id))

    if not ordens:
        flash('Nenhuma OS encontrada para este pedido.', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))

    if len(ordens) == 1:
        return redirect(url_for('kanban.index', ordem_id=ordens[0].id))

    return render_template('kanban/selecionar_os.html', pedido=pedido, ordens=ordens)

@kanban.route('/kanban/mover', methods=['POST'])
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
    """Rota para obter detalhes de uma ordem de serviço no Kanban"""
    ordem = OrdemServico.query.get_or_404(ordem_id)
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

        # Garantir que posições extremas continuem protegidas
        listas_db = {l.id: l for l in KanbanLista.query.filter(KanbanLista.id.in_(ordem_ids)).all()}
        if not ordem_ids:
            return jsonify({'success': False, 'message': 'Lista de ordem vazia.'})

        # Só aplicar a regra de proteção se as listas protegidas existirem no payload.
        present_names = {listas_db[lid].nome for lid in ordem_ids if lid in listas_db}
        has_entrada = 'Entrada' in present_names
        has_expedicao = 'Expedição' in present_names
        if has_entrada and has_expedicao:
            first_name = listas_db[ordem_ids[0]].nome
            last_name = listas_db[ordem_ids[-1]].nome
            if first_name != 'Entrada' or last_name != 'Expedição':
                return jsonify({'success': False, 'message': 'Entrada deve permanecer primeiro e Expedição último.'})

        for i, lista_id in enumerate(ordem_ids):
            lista = listas_db.get(lista_id)
            if lista:
                # Impedir mudar ordem das protegidas (devem permanecer)
                if lista.nome in PROTECTED_LISTS and ((i == 0 and lista.nome != 'Entrada') or (i == len(ordem_ids)-1 and lista.nome != 'Expedição')):
                    return jsonify({'success': False, 'message': 'Não é permitido mover listas protegidas.'})
                lista.ordem = i + 1
                lista.data_atualizacao = datetime.utcnow()

        db.session.commit()
        return jsonify({'success': True, 'message': 'Ordem das listas atualizada com sucesso!'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao reordenar listas: {str(e)}'})
    """Rota para reordenar as listas Kanban"""
    try:
        ordem_ids = request.json.get('ordem', [])
        
        for i, lista_id in enumerate(ordem_ids):
            lista = KanbanLista.query.get(lista_id)
            if lista:
                lista.ordem = i + 1
                lista.data_atualizacao = datetime.utcnow()
        
        db.session.commit()
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
            .filter(OrdemServico.status != lista_destino)\
            .filter(~OrdemServico.id.in_(ordens_existentes_ids))\
            .filter(OrdemServico.status != 'Finalizado')\
            .all()
        
        ordens_data = []
        for ordem in ordens_disponiveis:
            for pedido_os in ordem.pedidos:
                pedido = pedido_os.pedido
                if pedido.item_id:
                    item = Item.query.get(pedido.item_id)
                    ordens_data.append({
                        'id': ordem.id,
                        'numero': ordem.numero,
                        'item_nome': item.nome if item else pedido.nome_item,
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
