"""
Rotas para o módulo de Orçamentos
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload
from sqlalchemy import desc
from decimal import Decimal, InvalidOperation
from models import db, Orcamento, OrcamentoItem, Cliente, Item, Usuario, EstoquePecas, ListaRetirada, ListaRetiradaItem, Pedido, UnidadeEntrega
from utils import get_file_url

orcamentos_bp = Blueprint('orcamentos', __name__)

# Constantes
ADMIN_MASTER_EMAIL = 'admin@acbusinagem.com.br'


def _usuario_pode_ver_valores():
    """Verifica se usuário pode ver valores monetários"""
    if 'usuario_id' not in session:
        return False
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        return False
    return bool(
        ((getattr(usuario, 'email', '') or '').strip().lower() == ADMIN_MASTER_EMAIL 
         and getattr(usuario, 'nivel_acesso', None) == 'admin')
        or getattr(usuario, 'acesso_valores_itens', False)
    )


def _generate_next_pedido_code():
    ultimo_pedido = Pedido.query.filter(
        (Pedido.numero_pedido != None) & (~Pedido.numero_pedido.like('AUTO-%'))
    ).order_by(Pedido.numero_pedido.desc()).first()
    if ultimo_pedido and ultimo_pedido.numero_pedido:
        try:
            ultimo_numero = int(ultimo_pedido.numero_pedido.split('-')[-1])
            return f"PED-{str(ultimo_numero + 1).zfill(5)}"
        except Exception:
            return "PED-00001"
    return "PED-00001"


def _orcamento_ja_enviado_para_pedidos(orcamento: Orcamento) -> bool:
    if not orcamento or not getattr(orcamento, 'numero', None):
        return False
    # Compatibilidade:
    # - versão antiga: salvava orcamento.numero em Pedido.numero_oc (aparece como Nº OS na tela de pedidos)
    # - versão nova: salva orcamento.numero em Pedido.numero_pedido_cliente
    return (
        Pedido.query.filter_by(numero_oc=orcamento.numero).first() is not None
        or Pedido.query.filter_by(numero_pedido_cliente=orcamento.numero).first() is not None
    )


def _gerar_pedidos_do_orcamento(orcamento: Orcamento):
    """Gera pedidos (um Pedido por item), retornando (ok, mensagem, numero_pedido)."""
    if not orcamento.cliente_id:
        return False, 'Selecione um cliente cadastrado no orçamento.', None

    unidade = UnidadeEntrega.query.filter_by(cliente_id=orcamento.cliente_id).order_by(UnidadeEntrega.id.asc()).first()
    if not unidade:
        return False, 'Cadastre uma Unidade de Entrega para este cliente.', None

    if _orcamento_ja_enviado_para_pedidos(orcamento):
        return False, 'Este orçamento já foi enviado para Pedidos.', None

    numero_interno = _generate_next_pedido_code()
    gerados = 0
    for it in (orcamento.itens or []):
        try:
            qtd = Decimal(str(it.quantidade or 0))
        except Exception:
            qtd = Decimal('0')
        if qtd <= 0:
            continue

        novo_pedido = Pedido(
            numero_pedido=numero_interno,
            # Usar o campo "Nº Pedido Cliente" para rastrear o orçamento, sem poluir o campo de Nº OS
            numero_pedido_cliente=orcamento.numero,
            cliente_id=orcamento.cliente_id,
            unidade_entrega_id=unidade.id,
            item_id=it.item_id,
            nome_item=None,
            quantidade=int(qtd),
            data_entrada=datetime.now().date(),
            previsao_entrega=None,
            descricao=f"RETIRADA ESTOQUE - Gerado do orçamento {orcamento.numero} - {it.descricao_display}",
            numero_oc=None
        )
        db.session.add(novo_pedido)
        gerados += 1

    if gerados <= 0:
        return False, 'Nenhum item válido encontrado para gerar pedido.', None

    return True, f'Pedido(s) gerado(s) com sucesso ({gerados} item(ns)).', numero_interno


def _usuario_pode_aprovar():
    """Verifica se usuário pode aprovar orçamentos (apenas admin master)"""
    if 'usuario_id' not in session:
        return False
    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        return False
    return (
        (getattr(usuario, 'email', '') or '').strip().lower() == ADMIN_MASTER_EMAIL 
        and getattr(usuario, 'nivel_acesso', None) == 'admin'
    )


def _gerar_numero_orcamento():
    """Gera próximo número de orçamento no formato ORC-YYYY-NNNN"""
    ano_atual = datetime.now().year
    prefixo = f"ORC-{ano_atual}-"
    
    ultimo_orcamento = (
        Orcamento.query
        .filter(Orcamento.numero.like(f"{prefixo}%"))
        .order_by(desc(Orcamento.numero))
        .first()
    )
    
    if ultimo_orcamento:
        try:
            ultimo_num = int(ultimo_orcamento.numero.split('-')[-1])
            proximo_num = ultimo_num + 1
        except (ValueError, IndexError):
            proximo_num = 1
    else:
        proximo_num = 1
    
    return f"{prefixo}{proximo_num:04d}"


@orcamentos_bp.route('/orcamentos')
def index():
    """Lista todos os orçamentos com filtros"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Você não tem permissão para acessar orçamentos.', 'danger')
        return redirect(url_for('index'))
    
    # Filtros
    status_filtro = request.args.get('status', '')
    busca = request.args.get('busca', '')
    cliente_id = request.args.get('cliente_id', type=int)
    
    query = Orcamento.query.options(
        selectinload(Orcamento.cliente),
        selectinload(Orcamento.criado_por)
    )
    
    if status_filtro:
        query = query.filter(Orcamento.status == status_filtro)
    
    if busca:
        query = query.filter(
            or_(
                Orcamento.numero.ilike(f'%{busca}%'),
                Orcamento.cliente_nome.ilike(f'%{busca}%')
            )
        )
    
    if cliente_id:
        query = query.filter(Orcamento.cliente_id == cliente_id)
    
    orcamentos = query.order_by(desc(Orcamento.criado_em)).all()
    
    # Buscar clientes para filtro
    clientes = Cliente.query.order_by(Cliente.nome).all()
    
    return render_template(
        'orcamentos/index.html',
        orcamentos=orcamentos,
        clientes=clientes,
        pode_ver_valores=pode_ver_valores,
        status_filtro=status_filtro,
        busca=busca,
        cliente_id=cliente_id
    )


@orcamentos_bp.route('/orcamentos/novo', methods=['GET', 'POST'])
def novo():
    """Cria novo orçamento"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Você não tem permissão para criar orçamentos.', 'danger')
        return redirect(url_for('orcamentos.index'))
    
    if request.method == 'POST':
        usuario_id = session.get('usuario_id')
        
        # Criar orçamento
        orcamento = Orcamento(
            numero=_gerar_numero_orcamento(),
            status='rascunho',
            criado_por_id=usuario_id,
            validade_dias=30
        )
        
        # Cliente - pode ser cadastrado ou apenas nome
        cliente_id = request.form.get('cliente_id')
        cliente_nome = request.form.get('cliente_nome', '').strip()
        
        if cliente_id:
            # Cliente cadastrado selecionado
            orcamento.cliente_id = int(cliente_id)
        else:
            # Apenas nome do cliente
            orcamento.cliente_nome = cliente_nome
        
        # Dados do orçamento
        orcamento.validade_dias = int(request.form.get('validade_dias', 30))
        orcamento.condicoes_pagamento = request.form.get('condicoes_pagamento', '').strip()
        orcamento.prazo_entrega = request.form.get('prazo_entrega', '').strip()
        orcamento.observacoes = request.form.get('observacoes', '').strip()
        
        # Atualizar data de validade
        orcamento.atualizar_data_validade()
        
        db.session.add(orcamento)
        db.session.commit()
        
        flash(f'Orçamento {orcamento.numero} criado com sucesso!', 'success')
        return redirect(url_for('orcamentos.editar', orcamento_id=orcamento.id))
    
    # GET
    clientes = Cliente.query.order_by(Cliente.nome).all()
    
    # Buscar itens disponíveis para o modal
    itens_disponiveis = Item.query.options(
        selectinload(Item.estoque_pecas),
        selectinload(Item.classe)
    ).order_by(Item.codigo_acb).all()
    
    return render_template(
        'orcamentos/form.html',
        orcamento=None,
        clientes=clientes,
        itens_disponiveis=itens_disponiveis,
        pode_ver_valores=pode_ver_valores
    )


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/editar', methods=['GET', 'POST'])
def editar(orcamento_id):
    """Edita orçamento existente"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Você não tem permissão para editar orçamentos.', 'danger')
        return redirect(url_for('orcamentos.index'))
    
    orcamento = Orcamento.query.options(
        selectinload(Orcamento.itens).selectinload(OrcamentoItem.item).selectinload(Item.estoque_pecas),
        selectinload(Orcamento.cliente)
    ).get_or_404(orcamento_id)
    
    if request.method == 'POST':
        if orcamento.status in ['aprovado', 'convertido']:
            flash('Não é possível editar orçamento aprovado ou convertido.', 'warning')
            return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))
        
        # Atualizar cliente
        cliente_id = request.form.get('cliente_id')
        cliente_nome = request.form.get('cliente_nome', '').strip()
        
        if cliente_id:
            # Cliente cadastrado selecionado
            orcamento.cliente_id = int(cliente_id)
        else:
            # Apenas nome do cliente
            orcamento.cliente_id = None
            orcamento.cliente_nome = cliente_nome
        
        # Atualizar dados
        orcamento.validade_dias = int(request.form.get('validade_dias', 30))
        orcamento.condicoes_pagamento = request.form.get('condicoes_pagamento', '').strip()
        orcamento.prazo_entrega = request.form.get('prazo_entrega', '').strip()
        orcamento.observacoes = request.form.get('observacoes', '').strip()
        
        # Atualizar data de validade
        orcamento.atualizar_data_validade()
        
        db.session.commit()
        flash('Orçamento atualizado com sucesso!', 'success')
        return redirect(url_for('orcamentos.editar', orcamento_id=orcamento_id))
    
    # GET - Atualizar informações de estoque dos itens
    for item in orcamento.itens:
        item.atualizar_estoque()
    
    # Buscar itens disponíveis para adicionar
    itens_disponiveis = Item.query.options(
        selectinload(Item.estoque_pecas),
        selectinload(Item.classe)
    ).order_by(Item.codigo_acb).all()
    
    clientes = Cliente.query.order_by(Cliente.nome).all()
    
    return render_template(
        'orcamentos/form.html',
        orcamento=orcamento,
        itens_disponiveis=itens_disponiveis,
        clientes=clientes,
        pode_ver_valores=pode_ver_valores
    )


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>')
def visualizar(orcamento_id):
    """Visualiza orçamento (modo impressão)"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Você não tem permissão para visualizar orçamentos.', 'danger')
        return redirect(url_for('orcamentos.index'))
    
    orcamento = Orcamento.query.options(
        selectinload(Orcamento.itens).selectinload(OrcamentoItem.item),
        selectinload(Orcamento.cliente),
        selectinload(Orcamento.criado_por),
        selectinload(Orcamento.aprovado_por)
    ).get_or_404(orcamento_id)
    
    pode_aprovar = _usuario_pode_aprovar()

    pedidos_enviados = _orcamento_ja_enviado_para_pedidos(orcamento)
    
    return render_template(
        'orcamentos/visualizar.html',
        orcamento=orcamento,
        pode_ver_valores=pode_ver_valores,
        pode_aprovar=pode_aprovar,
        pedidos_enviados=pedidos_enviados
    )


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/enviar-para-pedidos', methods=['POST'])
def enviar_para_pedidos(orcamento_id):
    """Gera pedidos a partir do orçamento aprovado (sob demanda)."""
    pode_ver_valores = _usuario_pode_ver_valores()
    if not pode_ver_valores:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('orcamentos.index'))

    orcamento = Orcamento.query.options(
        selectinload(Orcamento.itens)
    ).get_or_404(orcamento_id)

    if orcamento.status != 'aprovado':
        flash('Somente orçamentos aprovados podem ser enviados para Pedidos.', 'warning')
        return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))

    ok, msg, numero_interno = _gerar_pedidos_do_orcamento(orcamento)
    if not ok:
        flash(f'Orçamento aprovado, mas não foi possível enviar para Pedidos: {msg}', 'warning')
        return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))

    db.session.commit()
    if numero_interno:
        flash(f'Enviado para Pedidos: {numero_interno}. {msg}', 'success')
    else:
        flash(f'Enviado para Pedidos. {msg}', 'success')
    return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/adicionar-item', methods=['POST'])
def adicionar_item(orcamento_id):
    """Adiciona item ao orçamento"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        return jsonify({'success': False, 'message': 'Sem permissão'}), 403
    
    orcamento = Orcamento.query.get_or_404(orcamento_id)
    
    if orcamento.status in ['aprovado', 'convertido']:
        return jsonify({'success': False, 'message': 'Orçamento não pode ser editado'}), 400
    
    item_id = request.form.get('item_id', type=int)
    quantidade_raw = (request.form.get('quantidade') or '1').strip()
    valor_unitario_raw = (request.form.get('valor_unitario') or '').strip()
    desconto_percentual_raw = (request.form.get('desconto_percentual') or '0').strip()
    observacao = request.form.get('observacao', '').strip()

    def _to_decimal(raw, default='0'):
        raw = (raw if raw is not None else default)
        raw = str(raw).strip().replace(',', '.')
        if raw == '':
            raw = default
        return Decimal(raw)

    try:
        quantidade = _to_decimal(quantidade_raw, default='1')
        valor_unitario = _to_decimal(valor_unitario_raw, default='0')
        desconto_percentual = _to_decimal(desconto_percentual_raw, default='0')
    except (InvalidOperation, ValueError):
        return jsonify({'success': False, 'message': 'Valores inválidos'}), 400
    
    if not item_id or not valor_unitario:
        return jsonify({'success': False, 'message': 'Item e valor são obrigatórios'}), 400
    
    item = Item.query.get(item_id)
    if not item:
        return jsonify({'success': False, 'message': 'Item não encontrado'}), 404
    
    # Verificar se item já existe no orçamento
    item_existente = OrcamentoItem.query.filter_by(
        orcamento_id=orcamento_id,
        item_id=item_id
    ).first()
    
    if item_existente:
        return jsonify({'success': False, 'message': 'Item já adicionado ao orçamento'}), 400
    
    # Próxima ordem
    max_ordem = db.session.query(db.func.max(OrcamentoItem.ordem)).filter_by(orcamento_id=orcamento_id).scalar() or 0
    
    # Criar item
    orcamento_item = OrcamentoItem(
        orcamento_id=orcamento_id,
        item_id=item_id,
        quantidade=quantidade,
        valor_unitario=valor_unitario,
        desconto_percentual=desconto_percentual,
        observacao=observacao,
        ordem=max_ordem + 1
    )
    
    # Calcular valor total
    orcamento_item.calcular_valor_total()
    orcamento_item.atualizar_estoque()
    
    db.session.add(orcamento_item)
    
    # Recalcular totais do orçamento
    orcamento.calcular_totais()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Item adicionado com sucesso'})


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/remover-item/<int:item_id>', methods=['POST'])
def remover_item(orcamento_id, item_id):
    """Remove item do orçamento"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        return jsonify({'success': False, 'message': 'Sem permissão'}), 403
    
    orcamento = Orcamento.query.get_or_404(orcamento_id)
    
    if orcamento.status in ['aprovado', 'convertido']:
        return jsonify({'success': False, 'message': 'Orçamento não pode ser editado'}), 400
    
    item = OrcamentoItem.query.filter_by(id=item_id, orcamento_id=orcamento_id).first()
    
    if not item:
        return jsonify({'success': False, 'message': 'Item não encontrado'}), 404
    
    db.session.delete(item)
    
    # Recalcular totais
    orcamento.calcular_totais()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Item removido com sucesso'})


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/atualizar-item/<int:item_id>', methods=['POST'])
def atualizar_item(orcamento_id, item_id):
    """Atualiza quantidade, valor ou desconto de um item (AJAX)"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        return jsonify({'success': False, 'message': 'Sem permissão'}), 403
    
    orcamento = Orcamento.query.get_or_404(orcamento_id)
    
    if orcamento.status in ['aprovado', 'convertido']:
        return jsonify({'success': False, 'message': 'Orçamento não pode ser editado'}), 400
    
    item = OrcamentoItem.query.filter_by(id=item_id, orcamento_id=orcamento_id).first()
    
    if not item:
        return jsonify({'success': False, 'message': 'Item não encontrado'}), 404

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

    def _to_decimal(value):
        if value is None:
            raise InvalidOperation('valor vazio')
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value).replace(',', '.'))

    # Atualizar campos (usar Decimal para manter consistência com models Numeric)
    try:
        if 'quantidade' in payload:
            item.quantidade = _to_decimal(payload.get('quantidade'))

        if 'valor_unitario' in payload:
            item.valor_unitario = _to_decimal(payload.get('valor_unitario'))

        if 'desconto_percentual' in payload:
            desconto = _to_decimal(payload.get('desconto_percentual'))
            # Normalizar desconto para faixa 0..100
            if desconto < 0:
                desconto = Decimal('0')
            if desconto > 100:
                desconto = Decimal('100')
            item.desconto_percentual = desconto
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Valor inválido'}), 400
    
    # Recalcular valor total do item
    item.calcular_valor_total()
    
    # Recalcular totais do orçamento
    orcamento.calcular_totais()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'valor_total_item': float(item.valor_total),
        'total_orcamento': float(orcamento.total_final)
    })


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/atualizar-valor-item/<int:item_id>', methods=['POST'])
def atualizar_valor_cadastro_item(orcamento_id, item_id):
    """Atualiza o valor cadastrado do item com o valor do orçamento (apenas admin master)"""
    pode_aprovar = _usuario_pode_aprovar()
    
    if not pode_aprovar:
        return jsonify({'success': False, 'message': 'Apenas administrador pode atualizar valores cadastrados'}), 403
    
    orcamento_item = OrcamentoItem.query.filter_by(id=item_id, orcamento_id=orcamento_id).first()
    
    if not orcamento_item:
        return jsonify({'success': False, 'message': 'Item não encontrado'}), 404
    
    item = orcamento_item.item
    valor_anterior = item.valor_item
    item.valor_item = orcamento_item.valor_unitario
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Valor atualizado de R$ {valor_anterior:.2f} para R$ {item.valor_item:.2f}',
        'valor_anterior': float(valor_anterior or 0),
        'valor_novo': float(item.valor_item)
    })


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/mudar-status', methods=['POST'])
def mudar_status(orcamento_id):
    """Muda status do orçamento"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('orcamentos.index'))
    
    orcamento = Orcamento.query.get_or_404(orcamento_id)
    novo_status = request.form.get('status')
    
    # Validar status
    if novo_status not in ['rascunho', 'enviado', 'aprovado', 'rejeitado', 'cancelado']:
        flash('Status inválido.', 'danger')
        return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))
    
    # Aprovar requer permissão especial
    if novo_status == 'aprovado' and not _usuario_pode_aprovar():
        flash('Apenas administrador pode aprovar orçamentos.', 'danger')
        return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))
    
    orcamento.status = novo_status
    
    if novo_status == 'aprovado':
        orcamento.aprovado_em = datetime.now()
        orcamento.aprovado_por_id = session.get('usuario_id')
    
    db.session.commit()
    
    flash(f'Orçamento {novo_status}.', 'success')
    return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/duplicar', methods=['POST'])
def duplicar(orcamento_id):
    """Duplica orçamento"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('orcamentos.index'))
    
    orcamento_original = Orcamento.query.options(
        selectinload(Orcamento.itens)
    ).get_or_404(orcamento_id)
    
    # Criar novo orçamento
    novo_orcamento = Orcamento(
        numero=_gerar_numero_orcamento(),
        cliente_id=orcamento_original.cliente_id,
        cliente_nome=orcamento_original.cliente_nome,
        cliente_email=orcamento_original.cliente_email,
        cliente_telefone=orcamento_original.cliente_telefone,
        cliente_cnpj_cpf=orcamento_original.cliente_cnpj_cpf,
        cliente_endereco=orcamento_original.cliente_endereco,
        status='rascunho',
        validade_dias=orcamento_original.validade_dias,
        observacoes=orcamento_original.observacoes,
        condicoes_pagamento=orcamento_original.condicoes_pagamento,
        prazo_entrega=orcamento_original.prazo_entrega,
        criado_por_id=session.get('usuario_id')
    )
    
    novo_orcamento.atualizar_data_validade()
    db.session.add(novo_orcamento)
    db.session.flush()
    
    # Copiar itens
    for item_original in orcamento_original.itens:
        novo_item = OrcamentoItem(
            orcamento_id=novo_orcamento.id,
            item_id=item_original.item_id,
            descricao_customizada=item_original.descricao_customizada,
            quantidade=item_original.quantidade,
            valor_unitario=item_original.valor_unitario,
            desconto_percentual=item_original.desconto_percentual,
            observacao=item_original.observacao,
            ordem=item_original.ordem
        )
        novo_item.calcular_valor_total()
        db.session.add(novo_item)
    
    # Calcular totais
    novo_orcamento.calcular_totais()
    
    db.session.commit()
    
    flash(f'Orçamento duplicado: {novo_orcamento.numero}', 'success')
    return redirect(url_for('orcamentos.editar', orcamento_id=novo_orcamento.id))


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/gerar-lista-retirada', methods=['POST'])
def gerar_lista_retirada(orcamento_id):
    """Gera lista de retirada a partir do orçamento aprovado"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('orcamentos.index'))
    
    orcamento = Orcamento.query.options(
        selectinload(Orcamento.itens).selectinload(OrcamentoItem.item).selectinload(Item.estoque_pecas)
    ).get_or_404(orcamento_id)
    
    if orcamento.status != 'aprovado':
        flash('Apenas orçamentos aprovados podem gerar lista de retirada.', 'warning')
        return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))
    
    if orcamento.status == 'convertido':
        flash('Este orçamento já foi convertido em lista de retirada.', 'warning')
        return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))
    
    # Gerar número da lista
    from routes.lista_retirada import _gerar_numero_lista
    
    # Criar lista de retirada
    lista = ListaRetirada(
        numero=_gerar_numero_lista(),
        status='rascunho',
        referencia=f'Orçamento {orcamento.numero}',
        responsavel=orcamento.nome_cliente_display,
        observacao=f'Gerado automaticamente do orçamento {orcamento.numero}',
        criado_por_id=session.get('usuario_id')
    )
    
    db.session.add(lista)
    db.session.flush()
    
    # Adicionar itens à lista
    ordem = 0
    for orc_item in orcamento.itens:
        # Buscar estoque do item
        estoque_item = EstoquePecas.query.filter_by(item_id=orc_item.item_id).filter(
            EstoquePecas.quantidade > 0
        ).first()
        
        if estoque_item:
            ordem += 1
            lista_item = ListaRetiradaItem(
                lista_id=lista.id,
                estoque_id=estoque_item.id,
                quantidade=int(orc_item.quantidade),
                observacao=f'Item do orçamento {orcamento.numero}',
                ordem=ordem
            )
            db.session.add(lista_item)
    
    # Marcar orçamento como convertido
    orcamento.status = 'convertido'
    
    db.session.commit()
    
    flash(f'Lista de retirada {lista.numero} criada com sucesso!', 'success')
    return redirect(url_for('lista_retirada.visualizar', lista_id=lista.id))


@orcamentos_bp.route('/orcamentos/<int:orcamento_id>/excluir', methods=['POST'])
def excluir(orcamento_id):
    """Exclui orçamento"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    if not pode_ver_valores:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('orcamentos.index'))
    
    orcamento = Orcamento.query.get_or_404(orcamento_id)
    
    if orcamento.status in ['aprovado', 'convertido']:
        flash('Não é possível excluir orçamento aprovado ou convertido.', 'warning')
        return redirect(url_for('orcamentos.visualizar', orcamento_id=orcamento_id))
    
    numero = orcamento.numero
    db.session.delete(orcamento)
    db.session.commit()
    
    flash(f'Orçamento {numero} excluído com sucesso.', 'success')
    return redirect(url_for('orcamentos.index'))
