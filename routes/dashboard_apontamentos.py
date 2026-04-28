"""
Dashboard de Apontamentos - Timeline Visual
Mostra linha do tempo de apontamentos por lista Kanban
"""

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, flash
from models import db, ApontamentoProducao, KanbanLista, OrdemServico, Item, Trabalho, Usuario, PedidoOrdemServico, Pedido
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

dashboard_apontamentos_bp = Blueprint('dashboard_apontamentos', __name__, url_prefix='/dashboard/apontamentos')


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
            status = 'producao'  # Setup conta como produção
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
        elif segmento['status'] == 'parada':
            resumo['tempo_parado_min'] += duracao_min
        elif segmento['status'] == 'manutencao':
            resumo['tempo_manutencao_min'] += duracao_min
        else:
            resumo['tempo_stop_min'] += duracao_min
    
    return resumo


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
    
    return render_template('dashboard_apontamentos/index.html', 
                         listas=listas,
                         usuario=usuario)


@dashboard_apontamentos_bp.route('/timeline')
def timeline():
    """API: Retorna dados da timeline de apontamentos"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Não autorizado'}), 401
    
    try:
        # Parâmetros
        data_str = request.args.get('data', datetime.now().strftime('%Y-%m-%d'))
        listas_ids = request.args.get('listas', '')  # IDs separados por vírgula
        
        # Parse da data
        data = datetime.strptime(data_str, '%Y-%m-%d')
        data_inicio = data.replace(hour=0, minute=0, second=0, microsecond=0)
        data_fim = data.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Parse das listas
        if listas_ids:
            lista_ids = [int(id.strip()) for id in listas_ids.split(',') if id.strip()]
        else:
            # Se não especificou, pegar todas as listas ativas
            listas = KanbanLista.query.filter_by(ativa=True).all()
            lista_ids = [lista.id for lista in listas]
        
        # Calcular timeline para cada lista
        resultado = []
        for lista_id in lista_ids:
            lista = KanbanLista.query.get(lista_id)
            if not lista:
                continue
            
            timeline_lista = _calcular_timeline_lista(lista_id, data_inicio, data_fim)
            resumo = _calcular_resumo_dia(timeline_lista)
            
            resultado.append({
                'lista_id': lista.id,
                'lista_nome': lista.nome,
                'lista_cor': lista.cor,
                'timeline': timeline_lista,
                'resumo_dia': resumo
            })
        
        return jsonify({
            'success': True,
            'data': data_str,
            'listas': resultado
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
        # Salvar configuração de listas visíveis
        # TODO: Implementar salvamento de preferências por usuário
        flash('Configuração salva com sucesso!', 'success')
        return redirect(url_for('dashboard_apontamentos.index'))
    
    # Buscar todas as listas
    listas = KanbanLista.query.filter_by(ativa=True).order_by(KanbanLista.ordem).all()
    
    return render_template('dashboard_apontamentos/configurar.html',
                         listas=listas,
                         usuario=usuario)
