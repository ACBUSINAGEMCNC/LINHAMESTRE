"""
Rotas para Lista de Retirada - Sistema melhorado com armazenamento em banco
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import desc
from models import db, ListaRetirada, ListaRetiradaItem, EstoquePecas, MovimentacaoEstoquePecas, Usuario
from utils import get_file_url

lista_retirada_bp = Blueprint('lista_retirada', __name__)

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


def _gerar_numero_lista():
    """Gera próximo número de lista no formato LR-YYYY-NNNN"""
    ano_atual = datetime.now().year
    prefixo = f"LR-{ano_atual}-"
    
    ultima_lista = (
        ListaRetirada.query
        .filter(ListaRetirada.numero.like(f"{prefixo}%"))
        .order_by(desc(ListaRetirada.numero))
        .first()
    )
    
    if ultima_lista:
        try:
            ultimo_num = int(ultima_lista.numero.split('-')[-1])
            proximo_num = ultimo_num + 1
        except (ValueError, IndexError):
            proximo_num = 1
    else:
        proximo_num = 1
    
    return f"{prefixo}{proximo_num:04d}"


def _localizacao_estoque(estoque_item):
    """Formata localização do estoque"""
    if estoque_item.estante and estoque_item.secao and estoque_item.linha and estoque_item.coluna:
        secao_letra = ['A', 'B', 'C', 'D'][estoque_item.secao - 1]
        posicao = (estoque_item.linha - 1) * 12 + estoque_item.coluna
        return f"{estoque_item.estante}-{secao_letra}-{posicao}"
    return '--'


@lista_retirada_bp.route('/estoque-pecas/listas-retirada')
def historico():
    """Lista todas as listas de retirada (histórico)"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    # Filtros
    status_filtro = request.args.get('status', '')
    busca = request.args.get('busca', '')
    
    query = ListaRetirada.query
    
    if status_filtro:
        query = query.filter(ListaRetirada.status == status_filtro)
    
    if busca:
        query = query.filter(
            db.or_(
                ListaRetirada.numero.ilike(f'%{busca}%'),
                ListaRetirada.referencia.ilike(f'%{busca}%'),
                ListaRetirada.responsavel.ilike(f'%{busca}%')
            )
        )
    
    listas = query.order_by(desc(ListaRetirada.criado_em)).all()
    
    # Calcular totais para cada lista
    listas_com_totais = []
    for lista in listas:
        total_itens = len(lista.itens)
        total_quantidade = sum(item.quantidade for item in lista.itens)
        total_valor = 0.0
        
        if pode_ver_valores:
            for item in lista.itens:
                valor_unit = float(getattr(item.estoque.item, 'valor_item', 0) or 0)
                total_valor += valor_unit * item.quantidade
        
        listas_com_totais.append({
            'lista': lista,
            'total_itens': total_itens,
            'total_quantidade': total_quantidade,
            'total_valor': total_valor
        })
    
    return render_template(
        'estoque_pecas/historico_listas.html',
        listas=listas_com_totais,
        pode_ver_valores=pode_ver_valores,
        status_filtro=status_filtro,
        busca=busca
    )


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>')
@lista_retirada_bp.route('/estoque-pecas/lista-retirada')
def visualizar(lista_id=None):
    """Visualiza ou cria nova lista de retirada"""
    pode_ver_valores = _usuario_pode_ver_valores()
    
    # Se não tem ID, pega a última lista em rascunho do usuário ou cria nova
    if not lista_id:
        usuario_id = session.get('usuario_id')
        lista = (
            ListaRetirada.query
            .filter_by(status='rascunho', criado_por_id=usuario_id)
            .order_by(desc(ListaRetirada.criado_em))
            .first()
        )
        
        if not lista:
            # Criar nova lista
            lista = ListaRetirada(
                numero=_gerar_numero_lista(),
                status='rascunho',
                criado_por_id=usuario_id
            )
            db.session.add(lista)
            db.session.commit()
            flash('Nova lista de retirada criada.', 'success')
    else:
        lista = ListaRetirada.query.get_or_404(lista_id)
    
    # Preparar dados dos itens
    itens_formatados = []
    total_quantidade = 0
    total_valor = 0.0
    
    for item in lista.itens:
        estoque = item.estoque
        if not estoque or not estoque.item:
            continue
        
        valor_unit = float(getattr(estoque.item, 'valor_item', 0) or 0)
        valor_total = valor_unit * item.quantidade
        
        itens_formatados.append({
            'id': item.id,
            'estoque_id': estoque.id,
            'codigo_acb': estoque.item.codigo_acb,
            'nome': estoque.item.nome,
            'quantidade_solicitada': item.quantidade,
            'quantidade_disponivel': estoque.quantidade,
            'localizacao': _localizacao_estoque(estoque),
            'imagem_path': get_file_url(estoque.item.imagem_path) if estoque.item.imagem_path else None,
            'valor_unitario': valor_unit,
            'valor_total': valor_total,
            'observacao_item': item.observacao,
            'ordem': item.ordem
        })
        
        total_quantidade += item.quantidade
        total_valor += valor_total
    
    # Ordenar por ordem
    itens_formatados.sort(key=lambda x: x['ordem'])
    
    # Estoque disponível para adicionar
    estoque_lista = (
        EstoquePecas.query
        .filter(EstoquePecas.quantidade > 0)
        .join(EstoquePecas.item)
        .order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna)
        .all()
    )
    
    return render_template(
        'estoque_pecas/lista_retirada_v2.html',
        lista=lista,
        itens_lista=itens_formatados,
        total_itens=len(itens_formatados),
        total_quantidade=total_quantidade,
        total_valor=total_valor,
        estoque_lista=estoque_lista,
        pode_ver_valores=pode_ver_valores,
        gerado_em=lista.criado_em.strftime('%d/%m/%Y %H:%M') if lista.criado_em else '',
        baixado_em=lista.baixado_em.strftime('%d/%m/%Y %H:%M') if lista.baixado_em else ''
    )


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>/nova', methods=['POST'])
@lista_retirada_bp.route('/estoque-pecas/lista-retirada/nova', methods=['POST'])
def nova(lista_id=None):
    """Cria nova lista de retirada"""
    usuario_id = session.get('usuario_id')
    
    lista = ListaRetirada(
        numero=_gerar_numero_lista(),
        status='rascunho',
        criado_por_id=usuario_id
    )
    db.session.add(lista)
    db.session.commit()
    
    flash('Nova lista de retirada criada.', 'success')
    return redirect(url_for('lista_retirada.visualizar', lista_id=lista.id))


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>/atualizar', methods=['POST'])
def atualizar_dados(lista_id):
    """Atualiza dados da lista (referência, responsável, observação)"""
    lista = ListaRetirada.query.get_or_404(lista_id)
    
    if lista.status == 'baixada':
        flash('Não é possível editar lista já baixada.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    lista.referencia = request.form.get('referencia', '').strip()
    lista.responsavel = request.form.get('responsavel', '').strip()
    lista.observacao = request.form.get('observacao', '').strip()
    
    db.session.commit()
    flash('Dados da lista atualizados.', 'success')
    return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>/adicionar', methods=['POST'])
def adicionar_item(lista_id):
    """Adiciona item à lista"""
    lista = ListaRetirada.query.get_or_404(lista_id)
    
    if lista.status == 'baixada':
        flash('Não é possível adicionar itens em lista já baixada.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    estoque_id = request.form.get('estoque_id', '').strip()
    quantidade_raw = request.form.get('quantidade', '').strip()
    observacao_item = request.form.get('observacao_item', '').strip()
    
    if not estoque_id or not quantidade_raw:
        flash('Selecione a peça e informe a quantidade.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    try:
        quantidade = int(quantidade_raw)
    except ValueError:
        flash('Quantidade inválida.', 'danger')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    if quantidade <= 0:
        flash('A quantidade deve ser maior que zero.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    estoque_item = EstoquePecas.query.get(estoque_id)
    if not estoque_item or estoque_item.quantidade <= 0:
        flash('Item não encontrado ou sem saldo disponível.', 'danger')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    # Verificar se já existe na lista
    item_existente = ListaRetiradaItem.query.filter_by(
        lista_id=lista_id,
        estoque_id=estoque_id
    ).first()
    
    if item_existente:
        nova_quantidade = item_existente.quantidade + quantidade
        if nova_quantidade > estoque_item.quantidade:
            flash(f'Quantidade total maior que disponível em estoque ({estoque_item.quantidade}).', 'danger')
            return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
        
        item_existente.quantidade = nova_quantidade
        if observacao_item:
            item_existente.observacao = observacao_item
    else:
        if quantidade > estoque_item.quantidade:
            flash(f'Quantidade maior que disponível em estoque ({estoque_item.quantidade}).', 'danger')
            return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
        
        # Próxima ordem
        max_ordem = db.session.query(db.func.max(ListaRetiradaItem.ordem)).filter_by(lista_id=lista_id).scalar() or 0
        
        novo_item = ListaRetiradaItem(
            lista_id=lista_id,
            estoque_id=estoque_id,
            quantidade=quantidade,
            observacao=observacao_item,
            ordem=max_ordem + 1
        )
        db.session.add(novo_item)
    
    db.session.commit()
    flash(f'Item {estoque_item.item.codigo_acb} adicionado à lista.', 'success')
    return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>/adicionar-multiplos', methods=['POST'])
def adicionar_multiplos(lista_id):
    """Adiciona múltiplos itens de uma vez (importação do estoque)"""
    lista = ListaRetirada.query.get_or_404(lista_id)
    
    if lista.status == 'baixada':
        flash('Não é possível adicionar itens em lista já baixada.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    # Recebe JSON com lista de itens: [{"estoque_id": 1, "quantidade": 5}, ...]
    try:
        itens_json = request.get_json()
        if not itens_json or not isinstance(itens_json, list):
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
        
        adicionados = 0
        max_ordem = db.session.query(db.func.max(ListaRetiradaItem.ordem)).filter_by(lista_id=lista_id).scalar() or 0
        
        for item_data in itens_json:
            estoque_id = item_data.get('estoque_id')
            quantidade = item_data.get('quantidade', 1)
            
            if not estoque_id:
                continue
            
            estoque_item = EstoquePecas.query.get(estoque_id)
            if not estoque_item or estoque_item.quantidade <= 0:
                continue
            
            # Verificar se já existe
            item_existente = ListaRetiradaItem.query.filter_by(
                lista_id=lista_id,
                estoque_id=estoque_id
            ).first()
            
            if item_existente:
                nova_quantidade = item_existente.quantidade + quantidade
                if nova_quantidade <= estoque_item.quantidade:
                    item_existente.quantidade = nova_quantidade
                    adicionados += 1
            else:
                if quantidade <= estoque_item.quantidade:
                    max_ordem += 1
                    novo_item = ListaRetiradaItem(
                        lista_id=lista_id,
                        estoque_id=estoque_id,
                        quantidade=quantidade,
                        ordem=max_ordem
                    )
                    db.session.add(novo_item)
                    adicionados += 1
        
        db.session.commit()
        return jsonify({'success': True, 'adicionados': adicionados})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>/remover/<int:item_id>', methods=['POST'])
def remover_item(lista_id, item_id):
    """Remove item da lista"""
    lista = ListaRetirada.query.get_or_404(lista_id)
    
    if lista.status == 'baixada':
        flash('Não é possível remover itens de lista já baixada.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    item = ListaRetiradaItem.query.filter_by(id=item_id, lista_id=lista_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash('Item removido da lista.', 'success')
    
    return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>/baixar', methods=['POST'])
def baixar(lista_id):
    """Dá baixa em todos os itens da lista no estoque"""
    lista = ListaRetirada.query.get_or_404(lista_id)
    
    if lista.status == 'baixada':
        flash('Esta lista já foi baixada.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    if not lista.itens:
        flash('A lista está vazia.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    try:
        usuario_id = session.get('usuario_id')
        referencia = lista.referencia or lista.numero
        
        for item in lista.itens:
            estoque = item.estoque
            if estoque.quantidade < item.quantidade:
                raise ValueError(f'Quantidade insuficiente para {estoque.item.codigo_acb}')
            
            # Dar baixa no estoque
            estoque.quantidade -= item.quantidade
            
            # Registrar movimentação
            movimentacao = MovimentacaoEstoquePecas(
                estoque_id=estoque.id,
                tipo='saida',
                quantidade=item.quantidade,
                referencia=referencia,
                observacao=f"Lista: {lista.numero} - {item.observacao or ''}".strip(),
                usuario_id=usuario_id
            )
            db.session.add(movimentacao)
        
        # Atualizar status da lista
        lista.status = 'baixada'
        lista.baixado_em = datetime.utcnow()
        lista.baixado_por_id = usuario_id
        
        db.session.commit()
        flash('Lista baixada no estoque com sucesso!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao baixar lista: {str(e)}', 'danger')
    
    return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))


@lista_retirada_bp.route('/estoque-pecas/lista-retirada/<int:lista_id>/cancelar', methods=['POST'])
def cancelar(lista_id):
    """Cancela uma lista de retirada"""
    lista = ListaRetirada.query.get_or_404(lista_id)
    
    if lista.status == 'baixada':
        flash('Não é possível cancelar lista já baixada.', 'warning')
        return redirect(url_for('lista_retirada.visualizar', lista_id=lista_id))
    
    lista.status = 'cancelada'
    db.session.commit()
    
    flash('Lista cancelada.', 'info')
    return redirect(url_for('lista_retirada.historico'))
