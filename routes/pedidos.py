from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from models import db, Pedido, Cliente, UnidadeEntrega, Item, PedidoOrdemServico, OrdemServico, Material, Trabalho, PedidoMaterial, ItemPedidoMaterial, ItemMaterial
from utils import validate_form_data, parse_json_field, generate_next_code, generate_next_os_code
from datetime import datetime
import logging

pedidos = Blueprint('pedidos', __name__)
logger = logging.getLogger(__name__)

@pedidos.route('/pedidos/gerar-os-multipla', methods=['POST'])
def gerar_ordem_servico_multipla():
    """Rota para gerar ordens de serviço para vários pedidos selecionados"""
    pedidos_ids = request.form.getlist('pedidos[]')
    if not pedidos_ids:
        flash('Selecione pelo menos um pedido para gerar ordens de serviço', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    # Verificar se há pedidos cancelados
    pedidos_cancelados = []
    pedidos_validos = []
    
    for pid in pedidos_ids:
        pedido = Pedido.query.get(pid)
        if not pedido:
            continue
            
        # Verificar se o pedido está cancelado
        if hasattr(pedido, 'cancelado') and pedido.cancelado:
            pedidos_cancelados.append(pedido.id)
        else:
            if pedido.item_id:  # Verificar se tem item cadastrado
                pedidos_validos.append(pedido)
    
    # Se houver pedidos cancelados, informar ao usuário
    if pedidos_cancelados:
        flash(f'Pedidos cancelados foram ignorados (IDs: {", ".join(map(str, pedidos_cancelados))})', 'warning')
    
    # Se não há pedidos válidos, redirecionar de volta
    if not pedidos_validos:
        flash('Não há pedidos válidos para gerar ordens de serviço', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
        
    # Agrupar pedidos por item
    grupos = {}
    for pedido in pedidos_validos:
        grupos.setdefault(pedido.item_id, []).append(pedido)
    # Verificar se há múltiplos itens
    if len(grupos) != 1:
        flash('Selecione apenas pedidos do mesmo item para gerar uma Ordem de Serviço', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))
    pedidos_grupo = list(grupos.values())[0]
    # Impedir gerar nova OS se já existe
    if any(p.ordens_servico for p in pedidos_grupo):
        # Recuperar número de OS existente
        existing_num = pedidos_grupo[0].ordens_servico[0].ordem_servico.numero
        # Atualizar numero_oc para todos pedidos do grupo
        for p in pedidos_grupo:
            p.numero_oc = existing_num
        db.session.commit()
        flash(f'Ordem de Serviço {existing_num} já existe para este item', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))
    # Gerar número de OS
    numero_os = generate_next_os_code()
    # Criar Ordem de Serviço
    os_nova = OrdemServico(numero=numero_os, data_criacao=datetime.now().date())
    db.session.add(os_nova)
    db.session.flush()
    # Associar pedidos à OS e atualizar campo numero_oc
    for pedido in pedidos_grupo:
        assoc = PedidoOrdemServico(pedido_id=pedido.id, ordem_servico_id=os_nova.id)
        pedido.numero_oc = numero_os
        db.session.add(assoc)
    db.session.commit()
    flash(f'Ordem de Serviço {numero_os} gerada com sucesso', 'success')
    return redirect(url_for('pedidos.listar_pedidos'))

@pedidos.route('/pedidos/gerar-pedido-material-multiplo', methods=['POST'])
def gerar_pedido_material_multiplo():
    """Rota para gerar pedido de material a partir de pedidos selecionados"""
    try:
        logger.info("Iniciando geração de pedido de material múltiplo")
        current_app.logger.info("Rota pedidos/gerar-pedido-material-multiplo recebida")
        
        # Obter IDs dos pedidos selecionados
        form_data = request.form
        current_app.logger.info(f"Formulário completo: {form_data}")
        
        pedidos_ids = request.form.getlist('pedidos[]')
        current_app.logger.info(f"Pedidos IDs recebidos: {pedidos_ids}")
        logger.debug("Pedidos IDs recebidos: %s", pedidos_ids)
        
        # Verificar especificamente os pedidos 4 e 5
        if '4' in pedidos_ids or '5' in pedidos_ids:
            logger.info("*** DETECTADOS PEDIDOS 4 OU 5 NA SELEÇÃO ***")
            # Consultar diretamente no banco de dados
            try:
                conn = db.engine.connect()
                if '4' in pedidos_ids:
                    result = conn.execute(db.text("SELECT * FROM pedido WHERE id = 4"))
                    row = result.fetchone()
                    logger.debug("Pedido 4 no banco: %s", row)
                if '5' in pedidos_ids:
                    result = conn.execute(db.text("SELECT * FROM pedido WHERE id = 5"))
                    row = result.fetchone()
                    logger.debug("Pedido 5 no banco: %s", row)
                conn.close()
            except Exception as e:
                logger.exception("Erro ao consultar pedidos 4/5 diretamente")
            logger.info("*** FIM DA VERIFICAÇÃO ESPECIAL ***")
    except Exception as e:
        logger.exception("Erro ao iniciar o processo de geração de pedido de material")
        flash(f'Erro ao iniciar o processo: {str(e)}', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    if not pedidos_ids:
        flash('Selecione pelo menos um pedido para gerar pedido de material', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    # Verificar se há pedidos cancelados
    pedidos_cancelados = []
    pedidos_validos = []
    
    for pid in pedidos_ids:
        pedido = Pedido.query.get(pid)
        if not pedido:
            continue
            
        # Verificar se o pedido está cancelado
        if hasattr(pedido, 'cancelado') and pedido.cancelado:
            pedidos_cancelados.append(pedido.id)
        else:
            pedidos_validos.append(pedido)
    
    # Se houver pedidos cancelados, informar ao usuário
    if pedidos_cancelados:
        flash(f'Pedidos cancelados foram ignorados (IDs: {", ".join(map(str, pedidos_cancelados))})', 'warning')
    
    # Se não há pedidos válidos, redirecionar de volta
    if not pedidos_validos:
        flash('Não há pedidos válidos para gerar pedido de material', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    # Verificar se todos os pedidos válidos têm itens válidos
    logger.debug("Verificando pedidos válidos...")
    pedidos_sem_item = []
    pedidos_para_processar = []
    
    for pedido in pedidos_validos:
        if not pedido.item_id:
            pedidos_sem_item.append(pedido.id)
        else:
            pedidos_para_processar.append(pedido)
    
    if pedidos_sem_item:
        flash(f'Pedidos sem item associado foram ignorados (IDs: {", ".join(map(str, pedidos_sem_item))})', 'warning')
    
    if not pedidos_para_processar:
        flash('Não há pedidos com itens válidos para gerar pedido de material', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    # Agregar materiais de todos os pedidos válidos
    materiais_agrupados = {}
    for pedido in pedidos_para_processar:
        item_materiais = ItemMaterial.query.filter_by(item_id=pedido.item_id).all()
        for item_material in item_materiais:
            if item_material.material_id in materiais_agrupados:
                materiais_agrupados[item_material.material_id] += item_material.comprimento * pedido.quantidade if item_material.comprimento and pedido.quantidade else 0
            else:
                materiais_agrupados[item_material.material_id] = item_material.comprimento * pedido.quantidade if item_material.comprimento and pedido.quantidade else 0
    
    if not materiais_agrupados:
        flash('Nenhum material associado aos itens dos pedidos selecionados', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    # Gerar um único código de pedido de material
    codigo_pm = generate_next_code(PedidoMaterial, 'PM', 'numero', padding=5)
    logger.info("Gerando Pedido de Material %s", codigo_pm)
    
    # Criar um único pedido de material
    pm = PedidoMaterial(
        numero=codigo_pm,
        data_criacao=datetime.now().date()
    )
    db.session.add(pm)
    db.session.flush()
    logger.debug("Pedido de Material %s criado no banco", codigo_pm)
    
    # Criar associações ItemPedidoMaterial para cada material agrupado
    for material_id, comprimento_total in materiais_agrupados.items():
        assoc = ItemPedidoMaterial(
            pedido_material_id=pm.id,
            material_id=material_id,
            comprimento=comprimento_total
        )
        db.session.add(assoc)
    
    # Atualizar numero_pedido_material para todos os pedidos processados
    for pedido in pedidos_para_processar:
        pedido.numero_pedido_material = codigo_pm
    
    db.session.commit()
    for pedido in pedidos_para_processar:
        logger.debug("Pedido ID %s atualizado com numero_pedido_material: %s", pedido.id, pedido.numero_pedido_material)
    logger.info("Pedido de Material %s salvo com sucesso. Itens associados: %s materiais agrupados.", codigo_pm, len(materiais_agrupados))
    flash(f'Pedido de Material gerado com sucesso: {codigo_pm}', 'success')
    return redirect(url_for('pedidos.listar_pedidos'))

@pedidos.route('/pedidos/novo', methods=['GET', 'POST'])
def novo_pedido():
    """Rota para cadastrar um novo pedido"""
    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id')
        unidade_entrega_id = request.form.get('unidade_entrega_id')
        if not unidade_entrega_id:
            flash('Unidade de entrega não selecionada!', 'danger')
            return redirect(url_for('pedidos.novo_pedido'))
        
        data_entrada = request.form.get('data_entrada')
        
        # Verificar se há itens no formulário
        itens = []
        index = 0
        while True:
            item_id_key = f'itens[{index}][item_id]'
            if item_id_key not in request.form:
                break
            item_id = request.form.get(item_id_key)
            quantidade = request.form.get(f'itens[{index}][quantidade]')
            nome_item = request.form.get(f'itens[{index}][nome_item]', None)
            if item_id and quantidade:
                itens.append({
                    'item_id': item_id if item_id != 'sem_cadastro' else None,
                    'quantidade': int(quantidade),
                    'nome_item': nome_item
                })
            index += 1
        
        if not itens:
            flash('É necessário adicionar pelo menos um item ao pedido!', 'danger')
            return redirect(url_for('pedidos.novo_pedido'))
        
        # Converter datas
        try:
            data_entrada = datetime.strptime(data_entrada, '%Y-%m-%d').date() if data_entrada else None
            previsao_entrega = datetime.strptime(request.form['previsao_entrega'], '%Y-%m-%d').date() if request.form.get('previsao_entrega') else None
        except ValueError:
            flash('Formato de data inválido!', 'danger')
            return redirect(url_for('pedidos.novo_pedido'))
        
        # Gerar número do pedido
        ultimo_pedido = Pedido.query.order_by(Pedido.numero_pedido.desc()).first()
        if ultimo_pedido:
            ultimo_numero = int(ultimo_pedido.numero_pedido.split('-')[-1])
            novo_numero = f"PED-{str(ultimo_numero + 1).zfill(5)}"
        else:
            novo_numero = "PED-00001"
        
        # Criar pedidos para cada item
        for item in itens:
            novo_pedido = Pedido(
                numero_pedido=novo_numero,
                cliente_id=cliente_id,
                unidade_entrega_id=unidade_entrega_id,
                item_id=item['item_id'],
                nome_item=item['nome_item'] if not item['item_id'] else None,
                quantidade=item['quantidade'],
                data_entrada=data_entrada,
                previsao_entrega=previsao_entrega,
                descricao=request.form.get('descricao')
            )
            db.session.add(novo_pedido)
        
        db.session.commit()
        flash(f'Pedido {novo_numero} criado com sucesso com {len(itens)} item(ns)!', 'success')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    clientes = Cliente.query.all()
    itens = Item.query.all()
    return render_template('pedidos/novo.html', clientes=clientes, itens=itens)

@pedidos.route('/pedidos')
def listar_pedidos():
    """Rota para listar todos os pedidos"""
    pedidos = Pedido.query.all()
    for pedido in pedidos:
        logger.debug("Pedido ID %s: numero_pedido_material = %s", pedido.id, pedido.numero_pedido_material if pedido.numero_pedido_material else 'N/A')
    clientes = Cliente.query.all()
    return render_template('pedidos/listar.html', pedidos=pedidos, clientes=clientes)

@pedidos.route('/pedidos/editar/<int:pedido_id>', methods=['GET', 'POST'])
def editar_pedido(pedido_id):
    """Rota para editar um pedido existente"""
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['cliente_id', 'unidade_entrega_id', 'quantidade', 'data_entrada'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            clientes = Cliente.query.all()
            itens = Item.query.all()
            unidades = UnidadeEntrega.query.filter_by(cliente_id=pedido.cliente_id).all()
            return render_template('pedidos/editar.html', pedido=pedido, clientes=clientes, itens=itens, unidades=unidades)
        
        cliente_id = request.form['cliente_id']
        unidade_entrega_id = request.form['unidade_entrega_id']
        if not unidade_entrega_id:
            flash('Unidade de entrega não selecionada!', 'danger')
            clientes = Cliente.query.all()
            itens = Item.query.all()
            unidades = UnidadeEntrega.query.filter_by(cliente_id=pedido.cliente_id).all()
            return render_template('pedidos/editar.html', pedido=pedido, clientes=clientes, itens=itens, unidades=unidades)
        
        tipo_item = request.form.get('tipo_item')
        
        # Validar quantidade
        try:
            quantidade = int(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                clientes = Cliente.query.all()
                itens = Item.query.all()
                unidades = UnidadeEntrega.query.filter_by(cliente_id=pedido.cliente_id).all()
                return render_template('pedidos/editar.html', pedido=pedido, clientes=clientes, itens=itens, unidades=unidades)
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            clientes = Cliente.query.all()
            itens = Item.query.all()
            unidades = UnidadeEntrega.query.filter_by(cliente_id=pedido.cliente_id).all()
            return render_template('pedidos/editar.html', pedido=pedido, clientes=clientes, itens=itens, unidades=unidades)
        
        # Validar data de entrada
        try:
            data_entrada = datetime.strptime(request.form['data_entrada'], '%Y-%m-%d').date()
        except ValueError:
            flash('Data de entrada inválida', 'danger')
            clientes = Cliente.query.all()
            itens = Item.query.all()
            unidades = UnidadeEntrega.query.filter_by(cliente_id=pedido.cliente_id).all()
            return render_template('pedidos/editar.html', pedido=pedido, clientes=clientes, itens=itens, unidades=unidades)
        
        numero_pedido = request.form.get('numero_pedido', '')
        
        # Validar previsão de entrega
        previsao_entrega = None
        if 'previsao_entrega' in request.form and request.form['previsao_entrega']:
            try:
                previsao_entrega = datetime.strptime(request.form['previsao_entrega'], '%Y-%m-%d').date()
            except ValueError:
                flash('Data de previsão de entrega inválida', 'danger')
                clientes = Cliente.query.all()
                itens = Item.query.all()
                unidades = UnidadeEntrega.query.filter_by(cliente_id=pedido.cliente_id).all()
                return render_template('pedidos/editar.html', pedido=pedido, clientes=clientes, itens=itens, unidades=unidades)
            
        descricao = request.form.get('descricao', '')
        
        # Verificar se o material foi comprado
        material_comprado = 'material_comprado' in request.form
        
        # Atualizar dados básicos
        pedido.cliente_id = cliente_id
        pedido.unidade_entrega_id = unidade_entrega_id
        pedido.quantidade = quantidade
        pedido.data_entrada = data_entrada
        pedido.numero_pedido = numero_pedido
        pedido.previsao_entrega = previsao_entrega
        pedido.descricao = descricao
        pedido.material_comprado = material_comprado
        
        # Se não estiver associado a uma OS, permitir alterar o item
        if not pedido.numero_oc:
            if tipo_item == 'cadastrado':
                item_id = request.form.get('item_id')
                if item_id:
                    pedido.item_id = item_id
                    pedido.nome_item = None
            else:  # sem_cadastro
                nome_item = request.form.get('nome_item')
                if nome_item:
                    # Verificar se já existe um item com este nome
                    item_existente = Item.query.filter_by(nome=nome_item).first()
                    if item_existente:
                        pedido.item_id = item_existente.id
                        pedido.nome_item = None
                    else:
                        pedido.item_id = None
                        pedido.nome_item = nome_item
        
        db.session.commit()
        flash('Pedido atualizado com sucesso!', 'success')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    clientes = Cliente.query.all()
    itens = Item.query.all()
    unidades = UnidadeEntrega.query.filter_by(cliente_id=pedido.cliente_id).all()
    
    return render_template('pedidos/editar.html', 
                          pedido=pedido, 
                          clientes=clientes, 
                          itens=itens,
                          unidades=unidades)

@pedidos.route('/pedidos/toggle-compra/<int:pedido_id>', methods=['POST'])
def toggle_compra_material(pedido_id):
    """Rota para alternar o status de compra de material de um pedido"""
    pedido = Pedido.query.get_or_404(pedido_id)
    pedido.material_comprado = not pedido.material_comprado
    db.session.commit()
    
    status = "comprado" if pedido.material_comprado else "não comprado"
    flash(f'Material marcado como {status}!', 'success')
    
    # Se a requisição for AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True, 
            'material_comprado': pedido.material_comprado,
            'message': f'Material marcado como {status}!'
        })
    
    # Caso contrário, redirecionar para a página de listagem
    return redirect(url_for('pedidos.listar_pedidos'))

@pedidos.route('/pedidos/cancelar/<int:pedido_id>', methods=['POST'])
def cancelar_pedido(pedido_id):
    """Rota para cancelar um pedido (não exclui do banco)"""
    from flask import session
    pedido = Pedido.query.get_or_404(pedido_id)
    logger.info("Tentando cancelar pedido ID %s, status atual: cancelado=%s", pedido_id, pedido.cancelado)
    if pedido.ordens_servico:
        flash('Não é possível cancelar um pedido associado a uma Ordem de Serviço!', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
    motivo = request.form.get('motivo_cancelamento')
    if not motivo:
        flash('É necessário informar o motivo do cancelamento!', 'danger')
        return redirect(url_for('pedidos.listar_pedidos'))
    pedido.cancelado = True
    pedido.motivo_cancelamento = motivo
    pedido.cancelado_por = session.get('usuario_nome', 'Desconhecido')
    pedido.data_cancelamento = datetime.now()
    db.session.commit()
    logger.info("Cancelado pedido ID %s com sucesso, novo status: cancelado=%s", pedido_id, pedido.cancelado)
    flash(f'Pedido cancelado com sucesso!', 'success')
    return redirect(url_for('pedidos.listar_pedidos'))

@pedidos.route('/pedidos/cadastrar-item/<int:pedido_id>', methods=['GET', 'POST'])
def cadastrar_item_pedido(pedido_id):
    """Rota para cadastrar um item a partir de um pedido"""
    from routes.itens import novo_item
    
    pedido = Pedido.query.get_or_404(pedido_id)
    
    # Verificar se o pedido já tem um item cadastrado
    if pedido.item_id:
        flash('Este pedido já possui um item cadastrado!', 'warning')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    # Verificar se já existe um item com o mesmo nome
    item_existente = Item.query.filter_by(nome=pedido.nome_item).first()
    
    if item_existente:
        # Atualizar todos os pedidos com o mesmo nome_item
        pedidos_para_atualizar = Pedido.query.filter_by(nome_item=pedido.nome_item, item_id=None).all()
        for p in pedidos_para_atualizar:
            p.item_id = item_existente.id
            p.nome_item = None
        
        db.session.commit()
        flash(f'Item já existente! Todos os pedidos com "{pedido.nome_item}" foram atualizados.', 'success')
        return redirect(url_for('pedidos.listar_pedidos'))
    
    if request.method == 'POST':
        # Redirecionar para a função de novo item com os dados do pedido
        return novo_item()
    
    materiais = Material.query.all()
    trabalhos = Trabalho.query.all()
    return render_template('itens/cadastrar_pedido.html', pedido=pedido, materiais=materiais, trabalhos=trabalhos)
