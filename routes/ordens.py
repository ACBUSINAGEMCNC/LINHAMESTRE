from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from models import db, OrdemServico, Pedido, PedidoOrdemServico, Item
from utils import validate_form_data, generate_next_code
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import re

ordens = Blueprint('ordens', __name__)


def _extrair_codigo_composto_de_pedido_auto(pedido):
    if not pedido or not pedido.descricao:
        return None
    m = re.search(r'item composto\s+([A-Za-z0-9\-_.]+)', pedido.descricao)
    if not m:
        return None
    return m.group(1).strip()


def _recriar_pedidos_virtuais_os_componente(os_componente, pedidos_originais, item_composto, componente_rel):
    # Remover associações/pedidos virtuais antigos desta OS
    assocs = list(os_componente.pedidos)
    for pedido_os in assocs:
        pedido = pedido_os.pedido
        if not pedido:
            continue
        if pedido.numero_pedido and pedido.numero_pedido.startswith('AUTO-') and pedido.descricao and pedido.descricao.startswith('Componente gerado automaticamente'):
            db.session.delete(pedido_os)
            db.session.delete(pedido)

    # Recriar pedidos virtuais por pedido original
    for pedido_original in pedidos_originais:
        quantidade_virtual = (componente_rel.quantidade or 0) * (pedido_original.quantidade or 0)
        if quantidade_virtual <= 0:
            continue

        pedido_virtual = Pedido(
            cliente_id=pedido_original.cliente_id,
            unidade_entrega_id=pedido_original.unidade_entrega_id,
            item_id=componente_rel.item_componente_id,
            nome_item=f"{componente_rel.item_componente.nome} (Componente de {item_composto.nome})",
            descricao=f"Componente gerado automaticamente do item composto {item_composto.codigo_acb}",
            quantidade=quantidade_virtual,
            data_entrada=datetime.now().date(),
            numero_pedido=f"AUTO-{os_componente.numero}-{pedido_original.id}",
            previsao_entrega=pedido_original.previsao_entrega,
            numero_oc=os_componente.numero
        )
        db.session.add(pedido_virtual)
        db.session.flush()

        assoc = PedidoOrdemServico(
            pedido_id=pedido_virtual.id,
            ordem_servico_id=os_componente.id
        )
        db.session.add(assoc)


def _reconciliar_os_componente_por_composto(ordem_servico):
    """Reconcilia uma OS de componente antiga: recria pedidos AUTO por cliente/pedido original."""
    # Encontrar um pedido AUTO dentro desta OS e extrair o código do composto
    pedidos_os = [po.pedido for po in ordem_servico.pedidos if po.pedido]
    pedido_auto = next((p for p in pedidos_os if p.numero_pedido and p.numero_pedido.startswith('AUTO-') and p.descricao), None)
    codigo_composto = _extrair_codigo_composto_de_pedido_auto(pedido_auto)
    if not codigo_composto:
        return False, 'Não foi possível identificar o item composto a partir da OS.'

    item_composto = Item.query.filter_by(codigo_acb=codigo_composto).first()
    if not item_composto or not item_composto.eh_composto:
        return False, f"Item composto não encontrado: {codigo_composto}"

    # Identificar qual item (componente) esta OS está produzindo
    item_ids_os = list({p.item_id for p in pedidos_os if p.item_id})
    if len(item_ids_os) != 1:
        return False, 'A OS não possui um único item de componente para reconciliar.'
    item_componente_id = item_ids_os[0]

    componente_rel = None
    for rel in item_composto.componentes:
        if rel.item_componente_id == item_componente_id:
            componente_rel = rel
            break
    if not componente_rel:
        return False, 'Este item não foi encontrado como componente do composto informado.'

    # Determinar o grupo de pedidos originais do composto
    # Buscar o grupo mais recente de pedidos não-AUTO do composto que tenha múltiplos clientes
    todos_pedidos = (
        Pedido.query
        .filter(Pedido.item_id == item_composto.id)
        .filter(Pedido.numero_pedido.isnot(None))
        .filter(~Pedido.numero_pedido.like('AUTO-%'))
        .order_by(Pedido.id.desc())
        .all()
    )
    
    if not todos_pedidos:
        return False, 'Nenhum pedido original encontrado para o item composto.'
    
    # Agrupar por numero_oc e pegar o grupo mais recente com mais de 1 pedido
    grupos_oc = {}
    for p in todos_pedidos:
        oc = p.numero_oc or 'SEM_OC'
        if oc not in grupos_oc:
            grupos_oc[oc] = []
        grupos_oc[oc].append(p)
    
    pedidos_originais = []
    for oc in sorted(grupos_oc.keys(), reverse=True):
        grupo = grupos_oc[oc]
        if len(grupo) > 1:
            pedidos_originais = grupo
            break
    
    # Fallback: se não houver grupo com múltiplos pedidos, usar o último pedido individualmente
    if not pedidos_originais:
        pedido_ref = todos_pedidos[0]
        if pedido_ref.numero_oc:
            pedidos_originais = [p for p in todos_pedidos if p.numero_oc == pedido_ref.numero_oc]
        else:
            pedidos_originais = [pedido_ref]
    
    if not pedidos_originais:
        return False, 'Não foi possível montar o grupo de pedidos originais para o composto.'

    _recriar_pedidos_virtuais_os_componente(ordem_servico, pedidos_originais, item_composto, componente_rel)
    return True, f"Pedidos virtuais atualizados ({len(pedidos_originais)} pedido(s) do composto)."


def _precisa_reconciliar_os_componente_por_composto(ordem_servico):
    pedidos_os = [po.pedido for po in ordem_servico.pedidos if po.pedido]
    pedidos_auto = [
        p for p in pedidos_os
        if p.numero_pedido
        and p.numero_pedido.startswith('AUTO-')
        and p.descricao
        and p.descricao.startswith('Componente gerado automaticamente')
    ]
    if not pedidos_auto:
        return False

    codigo_composto = _extrair_codigo_composto_de_pedido_auto(pedidos_auto[0])
    if not codigo_composto:
        return False

    item_composto = Item.query.filter_by(codigo_acb=codigo_composto).first()
    if not item_composto or not item_composto.eh_composto:
        return False

    # Buscar o grupo mais recente de pedidos originais com múltiplos clientes
    todos_pedidos = (
        Pedido.query
        .filter(Pedido.item_id == item_composto.id)
        .filter(Pedido.numero_pedido.isnot(None))
        .filter(~Pedido.numero_pedido.like('AUTO-%'))
        .order_by(Pedido.id.desc())
        .all()
    )
    
    if not todos_pedidos:
        return False
    
    # Agrupar por numero_oc e pegar o grupo mais recente com mais de 1 pedido
    grupos_oc = {}
    for p in todos_pedidos:
        oc = p.numero_oc or 'SEM_OC'
        if oc not in grupos_oc:
            grupos_oc[oc] = []
        grupos_oc[oc].append(p)
    
    total_originais = 0
    for oc in sorted(grupos_oc.keys(), reverse=True):
        grupo = grupos_oc[oc]
        if len(grupo) > 1:
            total_originais = len(grupo)
            break
    
    if total_originais <= 1:
        return False

    # Se ainda não existem AUTO suficientes para separar por cliente/unidade, reconciliar.
    return len(pedidos_auto) < total_originais

@ordens.route('/ordens-servico')
def listar_ordens_servico():
    """Rota para listar todas as ordens de serviço"""
    ordens = OrdemServico.query.all()
    return render_template('ordens/listar.html', ordens=ordens)

@ordens.route('/ordens-servico/nova', methods=['GET', 'POST'])
def nova_ordem_servico():
    """Rota para criar uma nova ordem de serviço"""
    if request.method == 'POST':
        # Validação de dados
        pedidos_ids = request.form.getlist('pedidos')
        if not pedidos_ids:
            flash('Selecione pelo menos um pedido para gerar a ordem de serviço', 'danger')
            pedidos = Pedido.query.filter(Pedido.numero_oc == None).all()
            return render_template('ordens/nova.html', pedidos=pedidos)
        
        # Gerar número da OS automaticamente com tentativas para garantir unicidade
        max_tentativas = 5
        for tentativa in range(max_tentativas):
            try:
                novo_numero = generate_next_code(OrdemServico, "OS", "numero")
                
                # Verificar explicitamente se o número já existe
                if OrdemServico.query.filter_by(numero=novo_numero).first():
                    continue  # Se já existe, tenta novamente
                
                ordem = OrdemServico(numero=novo_numero)
                db.session.add(ordem)
                db.session.flush()  # Flush para obter o ID sem commit
                
                # Adicionar pedidos à OS
                for pedido_id in pedidos_ids:
                    pedido_os = PedidoOrdemServico(
                        pedido_id=pedido_id,
                        ordem_servico_id=ordem.id
                    )
                    db.session.add(pedido_os)
                    
                    # Atualizar número da OC no pedido
                    pedido = Pedido.query.get(pedido_id)
                    pedido.numero_oc = novo_numero
                
                db.session.commit()
                flash('Ordem de Serviço criada com sucesso!', 'success')
                return redirect(url_for('ordens.listar_ordens_servico'))
                
            except IntegrityError as e:
                db.session.rollback()
                if tentativa == max_tentativas - 1:
                    flash(f'Erro ao gerar ordem de serviço: {str(e)}', 'danger')
                    pedidos = Pedido.query.filter(Pedido.numero_oc == None).all()
                    return render_template('ordens/nova.html', pedidos=pedidos)
    
    pedidos = Pedido.query.filter(Pedido.numero_oc == None).all()
    return render_template('ordens/nova.html', pedidos=pedidos)

@ordens.route('/ordens-servico/imprimir/<int:ordem_id>')
def imprimir_ordem_servico(ordem_id):
    """Rota para imprimir uma ordem de serviço"""
    ordem = OrdemServico.query.get_or_404(ordem_id)
    deve_reconciliar = request.args.get('reconciliar') == '1'
    if not deve_reconciliar:
        try:
            deve_reconciliar = _precisa_reconciliar_os_componente_por_composto(ordem)
        except Exception:
            deve_reconciliar = False

    if deve_reconciliar:
        try:
            ok, msg = _reconciliar_os_componente_por_composto(ordem)
            if ok:
                db.session.commit()
                if request.args.get('reconciliar') == '1':
                    flash(msg, 'success')
            else:
                db.session.rollback()
                if request.args.get('reconciliar') == '1':
                    flash(msg, 'warning')
        except Exception as e:
            db.session.rollback()
            if request.args.get('reconciliar') == '1':
                flash(f'Falha ao reconciliar OS: {str(e)}', 'danger')
    # Modo bonito preserva o layout de tela e cores na impressão
    modo_bonito = request.args.get('bonito') == '1' or request.args.get('modo') == 'bonito'
    return render_template('ordens/imprimir.html', ordem=ordem, Item=Item, Pedido=Pedido, modo_bonito=modo_bonito)

@ordens.route('/ordens-servico/imprimir-desenho/<int:ordem_id>')
def imprimir_desenho(ordem_id):
    """Rota para imprimir desenhos técnicos de uma ordem de serviço"""
    ordem = OrdemServico.query.get_or_404(ordem_id)
    return render_template('ordens/imprimir_desenho.html', ordem=ordem)
