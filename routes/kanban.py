from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from models import db, Usuario, OrdemServico, Pedido, PedidoOrdemServico, Item, Trabalho, ItemTrabalho, RegistroMensal
from utils import validate_form_data, get_kanban_lists, get_kanban_categories, format_seconds_to_time
from datetime import datetime

kanban = Blueprint('kanban', __name__)

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
def index():
    """Rota para a página principal do Kanban"""
    listas = get_kanban_lists()
    categorias = get_kanban_categories()
    
    ordens = {}
    tempos_listas = {}
    quantidades_listas = {}
    
    for lista in listas:
        ordens[lista] = OrdemServico.query.filter_by(status=lista).all()
        
        # Calcular tempos e quantidades para cada lista
        tempo_total = 0
        quantidade_total = 0
        
        for ordem in ordens[lista]:
            for pedido_os in ordem.pedidos:
                pedido = pedido_os.pedido
                if pedido.item_id:
                    quantidade_total += pedido.quantidade
                    
                    # Calcular tempo total para os trabalhos da categoria correspondente
                    for item_trabalho in ItemTrabalho.query.filter_by(item_id=pedido.item_id).all():
                        trabalho = Trabalho.query.get(item_trabalho.trabalho_id)
                        
                        # Verificar se o trabalho pertence à categoria da lista atual
                        for categoria, listas_categoria in categorias.items():
                            if lista in listas_categoria and (trabalho.categoria == categoria or not trabalho.categoria):
                                # Usar tempo real se disponível, senão usar tempo estimado
                                tempo_peca = item_trabalho.tempo_real or item_trabalho.tempo_peca
                                tempo_total += (tempo_peca * pedido.quantidade) + item_trabalho.tempo_setup
        
        tempos_listas[lista] = tempo_total
        quantidades_listas[lista] = quantidade_total
    
    return render_template('kanban/index.html', listas=listas, ordens=ordens, 
                          tempos_listas=tempos_listas, quantidades_listas=quantidades_listas,
                          Item=Item)

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
    ordem.status = nova_lista
    db.session.commit()
    
    return jsonify({'success': True})

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
    ordem.status = lista_destino
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
    for pedido_os in ordem.pedidos:
        pedido = Pedido.query.get(pedido_os.pedido_id)
        pedido.data_entrega = datetime.now().date()
    
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
    
    # Obter mês selecionado (padrão: mês atual)
    data_atual = datetime.now().date()
    mes_atual = f"{data_atual.year}-{data_atual.month:02d}"
    mes_selecionado = request.args.get('mes', mes_atual)
    
    # Obter registros do mês selecionado
    registros = RegistroMensal.query.filter_by(mes_referencia=mes_selecionado).all()
    
    return render_template('kanban/registros_mensais.html', 
                          registros=registros, 
                          meses_disponiveis=meses_disponiveis,
                          mes_selecionado=mes_selecionado)
