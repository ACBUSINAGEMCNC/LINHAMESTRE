"""
Dashboard de Apontamentos - Timeline Visual
Mostra linha do tempo de apontamentos por lista Kanban
"""

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, flash
from models import db, ApontamentoProducao, KanbanLista, OrdemServico, Item, Trabalho, Usuario, PedidoOrdemServico, Pedido, ItemTrabalho
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

dashboard_apontamentos_bp = Blueprint('dashboard_apontamentos', __name__, url_prefix='/dashboard/apontamentos')


def _get_dashboard_listas_visiveis(usuario):
    if not usuario or not getattr(usuario, 'preferencias', None):
        return []
    try:
        prefs = json.loads(usuario.preferencias)
        listas = prefs.get('dashboard_apontamentos', {}).get('listas_visiveis', [])
        return [int(lista_id) for lista_id in listas if str(lista_id).isdigit()]
    except Exception:
        return []


def _calcular_timeline_lista(lista_id, data_inicio, data_fim):
    """
    Calcula a timeline de apontamentos para uma lista específica
    
    Retorna lista de segmentos com:
    - inicio: datetime
    - fim: datetime
    - status: 'producao', 'parada', 'stop', 'manutencao'
    - apontamento_id: ID do apontamento
    - detalhes: informações do cartão/OS
    """
    
    # Buscar nome da lista
    lista = KanbanLista.query.get(lista_id)
    if not lista:
        return []
    
    # Buscar todos os apontamentos da lista no período
    # Nota: lista_kanban é String com o nome da lista, não FK
    apontamentos = ApontamentoProducao.query.options(
        joinedload(ApontamentoProducao.ordem_servico)
            .joinedload(OrdemServico.pedidos)
            .joinedload(PedidoOrdemServico.pedido),
        joinedload(ApontamentoProducao.item),
        joinedload(ApontamentoProducao.trabalho),
        joinedload(ApontamentoProducao.usuario)
    ).filter(
        ApontamentoProducao.lista_kanban == lista.nome,
        ApontamentoProducao.data_hora >= data_inicio,
        ApontamentoProducao.data_hora <= data_fim
    ).order_by(ApontamentoProducao.data_hora).all()
    
    timeline = []
    
    for apontamento in apontamentos:
        # Determinar status
        if apontamento.tipo_acao == 'inicio_producao':
            status = 'producao'
        elif apontamento.tipo_acao == 'pausa':
            # Verificar se é manutenção pelo motivo
            motivo = (apontamento.motivo_parada or '').lower()
            if 'manutencao' in motivo or 'manutenção' in motivo:
                status = 'manutencao'
            else:
                status = 'parada'
        elif apontamento.tipo_acao == 'inicio_setup':
            status = 'setup'
        else:
            status = 'stop'
        
        # Calcular fim do apontamento
        fim = apontamento.data_fim if apontamento.data_fim else datetime.now()
        
        # Buscar detalhes da OS
        detalhes = None
        if apontamento.ordem_servico:
            os = apontamento.ordem_servico
            
            # Buscar quantidade do pedido associado
            pecas_total = 1
            cliente_nome = None
            if os.pedidos and len(os.pedidos) > 0:
                pedido_os = os.pedidos[0]
                if pedido_os.pedido:
                    pecas_total = pedido_os.pedido.quantidade or 1
                    if pedido_os.pedido.cliente:
                        cliente_nome = pedido_os.pedido.cliente.nome
            
            # Calcular progresso
            pecas_feitas = apontamento.quantidade or 0
            
            # Calcular previsão
            tempo_decorrido_min = 0
            if apontamento.data_hora:
                delta = (fim - apontamento.data_hora).total_seconds() / 60
                tempo_decorrido_min = int(delta)
            
            media_min_peca = 0
            previsao_termino = None
            if pecas_feitas > 0 and tempo_decorrido_min > 0:
                media_min_peca = tempo_decorrido_min / pecas_feitas
                pecas_faltantes = pecas_total - pecas_feitas
                if pecas_faltantes > 0:
                    minutos_faltantes = pecas_faltantes * media_min_peca
                    previsao_termino = fim + timedelta(minutes=minutos_faltantes)
            
            detalhes = {
                'os_numero': str(os.id),
                'item_codigo': apontamento.item.codigo_acb if apontamento.item else 'N/A',
                'item_nome': apontamento.item.nome if apontamento.item else 'N/A',
                'cliente': cliente_nome or 'N/A',
                'servico': apontamento.trabalho.nome if apontamento.trabalho else 'N/A',
                'pecas_feitas': pecas_feitas,
                'pecas_total': pecas_total,
                'tempo_decorrido_min': tempo_decorrido_min,
                'media_min_peca': round(media_min_peca, 2),
                'previsao_termino': previsao_termino.isoformat() if previsao_termino else None,
                'operador': apontamento.usuario.nome if apontamento.usuario else 'N/A',
                'motivo_parada': apontamento.motivo_parada
            }
        
        timeline.append({
            'inicio': apontamento.data_hora.isoformat(),
            'fim': fim.isoformat(),
            'status': status,
            'apontamento_id': apontamento.id,
            'detalhes': detalhes
        })
    
    return timeline


def _calcular_resumo_dia(timeline):
    """Calcula resumo do dia com tempos por status"""
    resumo = {
        'tempo_producao_min': 0,
        'tempo_setup_min': 0,
        'tempo_parado_min': 0,
        'tempo_stop_min': 0,
        'tempo_manutencao_min': 0
    }
    
    for segmento in timeline:
        inicio = datetime.fromisoformat(segmento['inicio'])
        fim = datetime.fromisoformat(segmento['fim'])
        duracao_min = int((fim - inicio).total_seconds() / 60)
        
        if segmento['status'] == 'producao':
            resumo['tempo_producao_min'] += duracao_min
        elif segmento['status'] == 'setup':
            resumo['tempo_setup_min'] += duracao_min
        elif segmento['status'] == 'parada':
            resumo['tempo_parado_min'] += duracao_min
        elif segmento['status'] == 'manutencao':
            resumo['tempo_manutencao_min'] += duracao_min
        else:
            resumo['tempo_stop_min'] += duracao_min
    
    return resumo


def _to_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _tempo_label_segundos(segundos):
    total = max(0, _to_int(segundos, 0))
    horas = total // 3600
    minutos = (total % 3600) // 60
    if horas > 0:
        return f"{horas}h {minutos:02d}m"
    return f"{minutos}m"


def _get_primeira_os_atual_lista(lista):
    ordem = OrdemServico.query.options(
        joinedload(OrdemServico.pedidos)
            .joinedload(PedidoOrdemServico.pedido)
            .joinedload(Pedido.cliente),
        joinedload(OrdemServico.pedidos)
            .joinedload(PedidoOrdemServico.pedido)
            .joinedload(Pedido.item)
            .joinedload(Item.trabalhos)
            .joinedload(ItemTrabalho.trabalho)
    ).filter_by(status=lista.nome).order_by(OrdemServico.posicao.asc(), OrdemServico.id.asc()).first()

    if not ordem:
        return None

    pedido = None
    for pedido_os in ordem.pedidos or []:
        if pedido_os.pedido:
            pedido = pedido_os.pedido
            break

    item = pedido.item if pedido and pedido.item else None
    cliente = pedido.cliente if pedido and pedido.cliente else None
    pecas_total = _to_int(pedido.quantidade if pedido else 0, 0)
    tempo_previsto_seg = 0
    tempo_apontado_seg = 0
    servicos = []
    servicos_detalhes = []
    apontado_rows = db.session.query(
        ApontamentoProducao.trabalho_id,
        db.func.coalesce(db.func.sum(ApontamentoProducao.tempo_decorrido), 0)
    ).filter(
        ApontamentoProducao.ordem_servico_id == ordem.id
    ).group_by(ApontamentoProducao.trabalho_id).all()
    apontado_por_trabalho = {
        int(trabalho_id): _to_int(tempo_total, 0)
        for trabalho_id, tempo_total in apontado_rows
        if trabalho_id is not None
    }

    if item:
        for item_trabalho in item.trabalhos or []:
            trabalho = item_trabalho.trabalho
            tempo_peca = _to_int(item_trabalho.tempo_real or item_trabalho.tempo_peca, 0)
            tempo_setup = _to_int(item_trabalho.tempo_setup, 0)
            tempo_servico = tempo_setup + (tempo_peca * (pecas_total or 0))
            tempo_apontado_servico = apontado_por_trabalho.get(item_trabalho.trabalho_id, 0)
            tempo_restante_servico = max(0, tempo_servico - tempo_apontado_servico)
            progresso_servico = min(100, round((tempo_apontado_servico / tempo_servico) * 100, 1)) if tempo_servico > 0 else 0
            tempo_previsto_seg += tempo_servico
            tempo_apontado_seg += tempo_apontado_servico
            if trabalho:
                servicos.append(trabalho.nome)
                servicos_detalhes.append({
                    'id': item_trabalho.trabalho_id,
                    'nome': trabalho.nome,
                    'tempo_previsto_seg': tempo_servico,
                    'tempo_apontado_seg': tempo_apontado_servico,
                    'tempo_restante_seg': tempo_restante_servico,
                    'tempo_previsto_label': _tempo_label_segundos(tempo_servico),
                    'tempo_apontado_label': _tempo_label_segundos(tempo_apontado_servico),
                    'tempo_restante_label': _tempo_label_segundos(tempo_restante_servico),
                    'progresso_percent': progresso_servico
                })

    tempo_restante_seg = max(0, tempo_previsto_seg - tempo_apontado_seg)
    progresso_total = min(100, round((tempo_apontado_seg / tempo_previsto_seg) * 100, 1)) if tempo_previsto_seg > 0 else 0
    segundos_por_turno = 8 * 3600
    turnos_restantes = round(tempo_restante_seg / segundos_por_turno, 1) if segundos_por_turno else 0

    return {
        'os_numero': ordem.numero or str(ordem.id),
        'item_codigo': item.codigo_acb if item else 'N/A',
        'item_nome': item.nome if item else (pedido.nome_item if pedido else 'N/A'),
        'item_imagem_path': item.imagem_path if item else None,
        'cliente': cliente.nome if cliente else 'N/A',
        'servico': ', '.join(servicos[:3]) if servicos else 'N/A',
        'pecas_feitas': 0,
        'pecas_total': pecas_total or 0,
        'tempo_decorrido_min': int(tempo_apontado_seg / 60) if tempo_apontado_seg else 0,
        'tempo_previsto_min': int(tempo_previsto_seg / 60) if tempo_previsto_seg else 0,
        'tempo_previsto_label': _tempo_label_segundos(tempo_previsto_seg),
        'tempo_apontado_label': _tempo_label_segundos(tempo_apontado_seg),
        'tempo_restante_label': _tempo_label_segundos(tempo_restante_seg),
        'turnos_restantes': turnos_restantes,
        'progresso_percent': progresso_total,
        'servicos_detalhes': servicos_detalhes,
        'media_min_peca': 0,
        'previsao_termino': None,
        'operador': 'N/A',
        'motivo_parada': None,
        'posicao': ordem.posicao,
        'status_kanban': ordem.status
    }


@dashboard_apontamentos_bp.route('/')
def index():
    """Página principal do dashboard de apontamentos"""
    # Verificar se usuário está logado
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login'))
    
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('kanban.index'))
    
    # Dashboard é visível para todos (não precisa ser admin)
    
    # Buscar todas as listas Kanban ativas
    listas = KanbanLista.query.filter_by(ativa=True).order_by(KanbanLista.ordem).all()
    
    # Filtrar por preferências do usuário (se configurado)
    listas_visiveis = _get_dashboard_listas_visiveis(usuario)
    if listas_visiveis:
        listas = [l for l in listas if l.id in listas_visiveis]
    
    return render_template('dashboard_apontamentos/index.html', 
                         listas=listas,
                         usuario=usuario)


@dashboard_apontamentos_bp.route('/tv')
def tv():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login'))

    return render_template('dashboard_apontamentos/tv.html')


@dashboard_apontamentos_bp.route('/timeline')
def timeline():
    """API: Retorna dados da timeline de apontamentos"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 401
    
    try:
        # Parâmetros
        data_str = request.args.get('data', datetime.now().strftime('%Y-%m-%d'))
        listas_ids = request.args.get('listas', '')  # IDs separados por vírgula
        usuario = Usuario.query.get(session['usuario_id'])
        
        # Parse da data
        data = datetime.strptime(data_str, '%Y-%m-%d')
        data_inicio = data.replace(hour=0, minute=0, second=0, microsecond=0)
        data_fim = data.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Parse das listas
        if listas_ids:
            lista_ids = [int(id.strip()) for id in listas_ids.split(',') if id.strip()]
        else:
            # Se não especificou, pegar listas configuradas pelo usuário; se vazio, todas as listas ativas
            listas = KanbanLista.query.filter_by(ativa=True).all()
            listas_visiveis = _get_dashboard_listas_visiveis(usuario)
            lista_ids = listas_visiveis if listas_visiveis else [lista.id for lista in listas]
        
        # Calcular timeline para cada lista
        resultado = []
        resumo_geral = {
            'tempo_producao_min': 0,
            'tempo_setup_min': 0,
            'tempo_parado_min': 0,
            'tempo_stop_min': 0,
            'tempo_manutencao_min': 0
        }
        for lista_id in lista_ids:
            lista = KanbanLista.query.get(lista_id)
            if not lista:
                continue
            
            timeline_lista = _calcular_timeline_lista(lista_id, data_inicio, data_fim)
            resumo = _calcular_resumo_dia(timeline_lista)
            for chave in resumo_geral:
                resumo_geral[chave] += resumo.get(chave, 0)
            
            resultado.append({
                'lista_id': lista.id,
                'lista_nome': lista.nome,
                'lista_cor': lista.cor,
                'timeline': timeline_lista,
                'resumo_dia': resumo,
                'primeira_os_atual': _get_primeira_os_atual_lista(lista)
            })
        
        return jsonify({
            'success': True,
            'data': data_str,
            'listas': resultado,
            'resumo_geral': resumo_geral
        })
        
    except Exception as e:
        logger.exception("Erro ao buscar timeline de apontamentos")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar timeline: {str(e)}'
        }), 500


@dashboard_apontamentos_bp.route('/configurar', methods=['GET', 'POST'])
def configurar():
    """Tela de configuração de listas visíveis no dashboard"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login'))
    
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('kanban.index'))
    
    if request.method == 'POST':
        try:
            # Obter listas selecionadas do formulário
            listas_selecionadas = request.form.getlist('listas_visiveis')
            
            # Carregar preferências atuais ou criar novo dict
            preferencias = {}
            if usuario.preferencias:
                try:
                    preferencias = json.loads(usuario.preferencias)
                except:
                    preferencias = {}
            
            # Atualizar preferências de dashboard
            preferencias['dashboard_apontamentos'] = {
                'listas_visiveis': [int(lid) for lid in listas_selecionadas if lid.isdigit()]
            }
            
            # Salvar no banco
            usuario.preferencias = json.dumps(preferencias)
            db.session.commit()
            
            flash('Configuração salva com sucesso!', 'success')
            return redirect(url_for('dashboard_apontamentos.index'))
        except Exception as e:
            flash(f'Erro ao salvar configuração: {str(e)}', 'danger')
            return redirect(url_for('dashboard_apontamentos.configurar'))
    
    # Buscar todas as listas
    listas = KanbanLista.query.filter_by(ativa=True).order_by(KanbanLista.ordem).all()
    
    # Obter listas visíveis atuais
    listas_visiveis = _get_dashboard_listas_visiveis(usuario)
    
    return render_template('dashboard_apontamentos/configurar.html',
                         listas=listas,
                         listas_visiveis=listas_visiveis,
                         usuario=usuario)
