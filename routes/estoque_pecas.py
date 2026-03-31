import json

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from sqlalchemy import or_
from sqlalchemy.exc import ProgrammingError
from models import db, EstoquePecas, Item, MovimentacaoEstoquePecas, EstoquePecasSlotTemp
from utils import validate_form_data
from datetime import datetime

estoque_pecas = Blueprint('estoque_pecas', __name__)


def _normalize_slots(slots, estante_padrao=None):
    out = []
    seen = set()
    for s in slots or []:
        try:
            est = int(s.get('estante') if isinstance(s, dict) else s[0])
            sec = int(s.get('secao') if isinstance(s, dict) else s[1])
            lin = int(s.get('linha') if isinstance(s, dict) else s[2])
            col = int(s.get('coluna') if isinstance(s, dict) else s[3])
        except Exception:
            continue
        if estante_padrao is not None:
            est = int(estante_padrao)
        if est < 1 or est > 8 or sec < 1 or sec > 4 or lin < 1 or lin > 2 or col < 1 or col > 6:
            continue
        key = (est, sec, lin, col)
        if key in seen:
            continue
        seen.add(key)
        out.append({'estante': est, 'secao': sec, 'linha': lin, 'coluna': col})
    out.sort(key=lambda x: (x['estante'], x['secao'], x['linha'], x['coluna']))
    return out


def _load_slots_json(raw, estante_padrao=None):
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    return _normalize_slots(data, estante_padrao=estante_padrao)


def _dump_slots_json(slots):
    return json.dumps(_normalize_slots(slots), ensure_ascii=False)


def _slots_from_entity(entity):
    slots = _load_slots_json(getattr(entity, 'slots_json', None))
    if slots:
        return slots
    if getattr(entity, 'estante', None) and getattr(entity, 'secao', None) and getattr(entity, 'linha', None) and getattr(entity, 'coluna', None):
        return _normalize_slots([{
            'estante': int(entity.estante),
            'secao': int(entity.secao),
            'linha': int(entity.linha),
            'coluna': int(entity.coluna),
        }])
    return []

@estoque_pecas.route('/estoque-pecas')
def index():
    """Rota para a página principal do estoque de peças"""
    # Organizar estoque por prateleira
    show_zero = (request.args.get('show_zero') or '').strip().lower() in ('1', 'true', 'yes', 'sim')
    q = EstoquePecas.query
    if not show_zero:
        q = q.filter(EstoquePecas.quantidade > 0)
    estoque = q.order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna).all()
    return render_template('estoque_pecas/index.html', estoque=estoque, show_zero=show_zero)

@estoque_pecas.route('/estoque-pecas/entrada', methods=['GET', 'POST'])
def entrada():
    """Rota para registrar entrada de peças no estoque"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['item_id', 'quantidade'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            itens = Item.query.all()
            return render_template('estoque_pecas/entrada.html', itens=itens)
        
        item_id = request.form['item_id']
        
        # Validar quantidade
        try:
            quantidade = int(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                itens = Item.query.all()
                return render_template('estoque_pecas/entrada.html', itens=itens)
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            itens = Item.query.all()
            return render_template('estoque_pecas/entrada.html', itens=itens)
        
        referencia = request.form.get('referencia', '')
        observacao = request.form.get('observacao', '')
        estante = request.form.get('estante')
        secao = request.form.get('secao')
        linha = request.form.get('linha')
        coluna = request.form.get('coluna')

        def _to_int(v):
            try:
                if v is None or str(v).strip() == '':
                    return None
                return int(v)
            except Exception:
                return None

        estante_i = _to_int(estante)
        secao_i = _to_int(secao)
        linha_i = _to_int(linha)
        coluna_i = _to_int(coluna)

        if estante_i and secao_i and linha_i and coluna_i:
            if coluna_i < 1 or coluna_i > 6:
                flash('Coluna inválida para o mapa (use 1 a 6).', 'warning')
                itens = Item.query.all()
                return render_template('estoque_pecas/entrada.html', itens=itens)
            ocupado = (
                EstoquePecas.query
                .filter(
                    EstoquePecas.estante == estante_i,
                    EstoquePecas.secao == secao_i,
                    EstoquePecas.linha == linha_i,
                    EstoquePecas.coluna == coluna_i,
                )
                .first()
            )
            if ocupado and str(ocupado.item_id) != str(item_id):
                flash('Este endereço já está ocupado por outro item. Escolha outra posição.', 'warning')
                itens = Item.query.all()
                return render_template('estoque_pecas/entrada.html', itens=itens)
        
        # Verificar se já existe um registro para este item
        estoque_existente = EstoquePecas.query.filter_by(item_id=item_id).first()
        
        if estoque_existente:
            # Atualizar estoque existente
            estoque_existente.quantidade += quantidade

            if estante_i:
                estoque_existente.estante = estante_i
            if secao_i:
                estoque_existente.secao = secao_i
            if linha_i:
                estoque_existente.linha = linha_i
            if coluna_i:
                estoque_existente.coluna = coluna_i
            
            # Registrar movimentação
            movimentacao = MovimentacaoEstoquePecas(
                estoque_pecas_id=estoque_existente.id,
                tipo='entrada',
                quantidade=quantidade,
                data=datetime.now().date(),
                referencia=referencia,
                observacao=observacao
            )
            
            db.session.add(movimentacao)
        else:
            # Criar novo registro de estoque
            novo_estoque = EstoquePecas(
                item_id=item_id,
                quantidade=quantidade,
                data_entrada=datetime.now().date(),
                estante=estante_i,
                secao=secao_i,
                linha=linha_i,
                coluna=coluna_i,
                observacao=observacao
            )
            
            db.session.add(novo_estoque)
            db.session.flush()  # Para obter o ID do novo registro
            
            # Registrar movimentação
            movimentacao = MovimentacaoEstoquePecas(
                estoque_pecas_id=novo_estoque.id,
                tipo='entrada',
                quantidade=quantidade,
                data=datetime.now().date(),
                referencia=referencia,
                observacao=observacao
            )
            
            db.session.add(movimentacao)
        
        db.session.commit()
        flash('Entrada de peças registrada com sucesso!', 'success')
        return redirect(url_for('estoque_pecas.index'))
    
    itens = Item.query.all()
    return render_template('estoque_pecas/entrada.html', itens=itens)

@estoque_pecas.route('/estoque-pecas/saida', methods=['GET', 'POST'])
def saida():
    """Rota para registrar saída de peças do estoque"""
    if request.method == 'POST':
        # Validação de dados
        errors = validate_form_data(request.form, ['estoque_id', 'quantidade'])
        if errors:
            for error in errors:
                flash(error, 'danger')
            estoque = EstoquePecas.query.order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna).all()
            return render_template('estoque_pecas/saida.html', estoque=estoque)
        
        estoque_id = request.form['estoque_id']
        
        # Validar quantidade
        try:
            quantidade = int(request.form['quantidade'])
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                estoque = EstoquePecas.query.order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna).all()
                return render_template('estoque_pecas/saida.html', estoque=estoque)
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            estoque = EstoquePecas.query.order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna).all()
            return render_template('estoque_pecas/saida.html', estoque=estoque)
        
        referencia = request.form.get('referencia', '')
        observacao = request.form.get('observacao', '')
        
        # Buscar registro de estoque
        estoque_item = EstoquePecas.query.get_or_404(estoque_id)
        
        # Verificar se há quantidade suficiente
        if estoque_item.quantidade < quantidade:
            flash('Quantidade insuficiente em estoque!', 'danger')
            estoque = EstoquePecas.query.order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna).all()
            return render_template('estoque_pecas/saida.html', estoque=estoque)
        
        # Atualizar estoque
        estoque_item.quantidade -= quantidade
        
        # Registrar movimentação
        movimentacao = MovimentacaoEstoquePecas(
            estoque_pecas_id=estoque_item.id,
            tipo='saida',
            quantidade=quantidade,
            data=datetime.now().date(),
            referencia=referencia,
            observacao=observacao
        )
        
        db.session.add(movimentacao)
        db.session.commit()
        
        flash('Saída de peças registrada com sucesso!', 'success')
        return redirect(url_for('estoque_pecas.index'))
    
    estoque = EstoquePecas.query.order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna).all()
    return render_template('estoque_pecas/saida.html', estoque=estoque)

@estoque_pecas.route('/estoque-pecas/historico/<int:estoque_id>')
def historico(estoque_id):
    """Rota para visualizar o histórico de movimentações de um item do estoque"""
    estoque_item = EstoquePecas.query.get_or_404(estoque_id)
    movimentacoes = MovimentacaoEstoquePecas.query.filter_by(estoque_pecas_id=estoque_id).order_by(MovimentacaoEstoquePecas.data.desc()).all()
    
    return render_template('estoque_pecas/historico.html', estoque=estoque_item, movimentacoes=movimentacoes)


@estoque_pecas.route('/estoque-pecas/mapa')
def mapa():
    estante = request.args.get('estante', '1')
    try:
        estante_i = int(estante) if estante is not None and str(estante).strip() != '' else 1
    except Exception:
        estante_i = 1
    if estante_i < 1 or estante_i > 8:
        estante_i = 1

    def _fetch_mapa_data():
        itens = EstoquePecas.query.order_by(EstoquePecas.id.desc()).all()
        ocup = (
            EstoquePecas.query
            .filter(EstoquePecas.estante == estante_i)
            .all()
        )
        temps = (
            EstoquePecasSlotTemp.query
            .filter(EstoquePecasSlotTemp.estante == estante_i)
            .all()
        )
        return itens, ocup, temps

    try:
        itens_estoque, ocupados, slots_temp = _fetch_mapa_data()
    except ProgrammingError as e:
        msg = str(e or '')
        if 'linha_fim' not in msg:
            raise
        try:
            from migrations.add_estoque_pecas_linha_fim import migrate_postgres, migrate_sqlite
            db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
            if str(db_url).lower().startswith('postgresql'):
                migrate_postgres()
            else:
                migrate_sqlite()
            db.session.remove()
            itens_estoque, ocupados, slots_temp = _fetch_mapa_data()
        except Exception:
            raise

    # Slots temporários da estante
    slots_temp = (
        EstoquePecasSlotTemp.query
        .filter(EstoquePecasSlotTemp.estante == estante_i)
        .order_by(EstoquePecasSlotTemp.id.desc())
        .all()
    )
    ocupados = (
        EstoquePecas.query
        .filter(EstoquePecas.estante == estante_i)
        .filter(EstoquePecas.slot_temp_id.is_(None))
        .all()
    )

    # Itens que estão em slots temporários desta estante
    slot_ids = [s.id for s in slots_temp]
    itens_em_temp = []
    if slot_ids:
        itens_em_temp = (
            EstoquePecas.query
            .filter(EstoquePecas.slot_temp_id.in_(slot_ids))
            .all()
        )

    def _slot_index(linha_v: int, coluna_v: int) -> int:
        return ((int(linha_v) - 1) * 6) + int(coluna_v)

    def _index_to_cell(idx: int):
        idx_i = int(idx)
        lin = 1 if idx_i <= 6 else 2
        col = idx_i if idx_i <= 6 else (idx_i - 6)
        return lin, col

    ocupados_map = {}
    for e in ocupados:
        for s in _slots_from_entity(e):
            if int(s['estante']) != estante_i:
                continue
            k = (int(s['secao']), int(s['linha']), int(s['coluna']))
            if k not in ocupados_map:
                ocupados_map[k] = []
            ocupados_map[k].append(e)

    # Mapa de slots temporários por célula (para renderização)
    temp_map = {}
    for s in slots_temp:
        for slot in _slots_from_entity(s):
            if int(slot['estante']) != estante_i:
                continue
            temp_map[(int(slot['secao']), int(slot['linha']), int(slot['coluna']))] = s

    # Itens dentro de temporário aparecem como ocupados no endereço do temporário
    slot_by_id = {s.id: s for s in slots_temp}
    for e in itens_em_temp:
        s = slot_by_id.get(e.slot_temp_id)
        if not s:
            continue
        for slot in _slots_from_entity(s):
            if int(slot['estante']) != estante_i:
                continue
            k = (int(slot['secao']), int(slot['linha']), int(slot['coluna']))
            if k not in ocupados_map:
                ocupados_map[k] = []
            ocupados_map[k].append(e)

    return render_template(
        'estoque_pecas/mapa.html',
        estante=estante_i,
        ocupados_map=ocupados_map,
        temp_map=temp_map,
        itens_estoque=itens_estoque,
    )


@estoque_pecas.route('/estoque-pecas/mapa/search')
def mapa_search():
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'results': []})

    like = f"%{q}%"
    rows = (
        EstoquePecas.query
        .join(Item, EstoquePecas.item_id == Item.id)
        .filter(
            or_(
                Item.codigo_acb.ilike(like),
                Item.nome.ilike(like),
            )
        )
        .filter(EstoquePecas.estante.isnot(None))
        .filter(EstoquePecas.secao.isnot(None))
        .filter(EstoquePecas.linha.isnot(None))
        .filter(EstoquePecas.coluna.isnot(None))
        .order_by(EstoquePecas.estante, EstoquePecas.secao, EstoquePecas.linha, EstoquePecas.coluna)
        .limit(40)
        .all()
    )

    results = []
    for e in rows:
        results.append({
            'estoque_id': e.id,
            'item_id': e.item.id if e.item else None,
            'codigo': (e.item.codigo_acb if e.item else '') or '',
            'nome': (e.item.nome if e.item else '') or '',
            'imagem': (e.item.imagem_path if e.item and e.item.imagem_path else '') or '',
            'pdf': url_for('itens.desenho_pdf_item', item_id=e.item.id) if e.item and e.item.desenho_tecnico else '',
            'estante': e.estante,
            'secao': e.secao,
            'linha': e.linha,
            'coluna': e.coluna,
        })

    return jsonify({'results': results})


@estoque_pecas.route('/estoque-pecas/mapa/definir', methods=['POST'])
def definir_localizacao_mapa():
    estoque_id = request.form.get('estoque_id')
    estante = request.form.get('estante')
    secao = request.form.get('secao')
    linha = request.form.get('linha')
    coluna = request.form.get('coluna')
    linha_fim = request.form.get('linha_fim')
    coluna_fim = request.form.get('coluna_fim')
    slots_json = request.form.get('slots_json')
    permitir_compartilhado = (request.form.get('permitir_compartilhado') or '').strip().lower() in ('1', 'true', 'yes', 'sim', 'on')
    usar_temporario = (request.form.get('usar_temporario') or '').strip().lower() in ('1', 'true', 'yes', 'sim', 'on')
    temporario_nome = (request.form.get('temporario_nome') or '').strip()

    def _to_int(v):
        try:
            if v is None or str(v).strip() == '':
                return None
            return int(v)
        except Exception:
            return None

    estoque_id_i = _to_int(estoque_id)
    estante_i = _to_int(estante)
    secao_i = _to_int(secao)
    linha_i = _to_int(linha)
    coluna_i = _to_int(coluna)
    linha_fim_i = _to_int(linha_fim)
    coluna_fim_i = _to_int(coluna_fim)
    slots_sel = _normalize_slots(_load_slots_json(slots_json, estante_padrao=estante_i), estante_padrao=estante_i)

    if not estoque_id_i and not usar_temporario:
        flash('Selecione um item do estoque (ou marque Temporário).', 'danger')
        return redirect(url_for('estoque_pecas.mapa', estante=estante_i or 1))

    if not (estante_i and secao_i and linha_i and coluna_i):
        flash('Informe Estante, Seção, Linha e Coluna.', 'danger')
        return redirect(url_for('estoque_pecas.mapa', estante=estante_i or 1))

    if estante_i < 1 or estante_i > 8 or secao_i < 1 or secao_i > 4 or linha_i < 1 or linha_i > 2 or coluna_i < 1 or coluna_i > 6:
        flash('Endereço inválido.', 'danger')
        return redirect(url_for('estoque_pecas.mapa', estante=estante_i or 1))

    if not slots_sel:
        slots_sel = _normalize_slots([{'estante': estante_i, 'secao': secao_i, 'linha': linha_i, 'coluna': coluna_i}], estante_padrao=estante_i)

    if linha_fim_i is not None:
        if linha_fim_i < linha_i:
            linha_fim_i = linha_i
        if linha_fim_i < 1 or linha_fim_i > 2:
            flash('Linha final inválida.', 'danger')
            return redirect(url_for('estoque_pecas.mapa', estante=estante_i or 1))

    if coluna_fim_i is not None:
        if coluna_fim_i < coluna_i:
            coluna_fim_i = coluna_i
        if coluna_fim_i < 1 or coluna_fim_i > 6:
            flash('Coluna final inválida.', 'danger')
            return redirect(url_for('estoque_pecas.mapa', estante=estante_i or 1))

    estoque_item = EstoquePecas.query.get(estoque_id_i) if estoque_id_i else None

    ocupacoes = (
        EstoquePecas.query
        .filter(EstoquePecas.estante == estante_i)
        .all()
    )

    slots_sel_set = {(int(s['estante']), int(s['secao']), int(s['linha']), int(s['coluna'])) for s in slots_sel}

    conflita = []
    for o in ocupacoes:
        if estoque_item and o.id == estoque_item.id:
            continue
        o_slots_set = {(int(s['estante']), int(s['secao']), int(s['linha']), int(s['coluna'])) for s in _slots_from_entity(o)}
        if slots_sel_set & o_slots_set:
            conflita.append(o)

    if conflita:
        if not permitir_compartilhado:
            flash('Esta posição já está ocupada por outro item. Marque "Permitir compartilhado" para permitir mais de um item no mesmo slot.', 'warning')
            return redirect(url_for('estoque_pecas.mapa', estante=estante_i))
        # Só permite compartilhar se todas as ocupações já estiverem marcadas como compartilháveis
        if any(not getattr(o, 'permitir_compartilhado', False) for o in conflita):
            flash('Esta posição já tem item(s) que não permitem compartilhamento. Ajuste o(s) item(ns) existente(s) para permitir compartilhamento antes.', 'warning')
            return redirect(url_for('estoque_pecas.mapa', estante=estante_i))

    # Se for temporário, criamos (ou atualizamos) o slot temporário neste endereço.
    slot_temp = None
    if usar_temporario:
        # Só pode haver 1 temporário por célula de início
        slot_temp = (
            EstoquePecasSlotTemp.query
            .filter_by(estante=estante_i, secao=secao_i, linha=linha_i, coluna=coluna_i)
            .first()
        )
        if not slot_temp:
            slot_temp = EstoquePecasSlotTemp(
                estante=estante_i,
                secao=secao_i,
                linha=linha_i,
                coluna=coluna_i,
            )
            db.session.add(slot_temp)
            db.session.flush()

        slot_temp.nome = temporario_nome or slot_temp.nome
        slot_temp.linha_fim = linha_fim_i
        slot_temp.coluna_fim = coluna_fim_i
        slot_temp.estante = int(slots_sel[0]['estante'])
        slot_temp.secao = int(slots_sel[0]['secao'])
        slot_temp.linha = int(slots_sel[0]['linha'])
        slot_temp.coluna = int(slots_sel[0]['coluna'])
        slot_temp.slots_json = _dump_slots_json(slots_sel)
        slot_temp.permitir_compartilhado = True if permitir_compartilhado else False

    # Se selecionou item, atualiza local.
    if estoque_item:
        if slot_temp:
            # Endereço passa a ser regido pelo temporário
            estoque_item.slot_temp_id = slot_temp.id
            estoque_item.estante = None
            estoque_item.secao = None
            estoque_item.linha = None
            estoque_item.coluna = None
            estoque_item.linha_fim = None
            estoque_item.coluna_fim = None
            estoque_item.slots_json = None
            estoque_item.permitir_compartilhado = permitir_compartilhado
        else:
            estoque_item.slot_temp_id = None
            estoque_item.estante = int(slots_sel[0]['estante'])
            estoque_item.secao = int(slots_sel[0]['secao'])
            estoque_item.linha = int(slots_sel[0]['linha'])
            estoque_item.coluna = int(slots_sel[0]['coluna'])
            estoque_item.linha_fim = linha_fim_i
            estoque_item.coluna_fim = coluna_fim_i
            estoque_item.slots_json = _dump_slots_json(slots_sel)
            estoque_item.permitir_compartilhado = permitir_compartilhado

    db.session.commit()
    flash('Localização atualizada com sucesso!', 'success')
    return redirect(url_for('estoque_pecas.mapa', estante=estante_i))


@estoque_pecas.route('/estoque-pecas/mapa/remover', methods=['POST'])
def remover_localizacao_mapa():
    estoque_id = request.form.get('estoque_id')
    estante = request.form.get('estante')

    def _to_int(v):
        try:
            if v is None or str(v).strip() == '':
                return None
            return int(v)
        except Exception:
            return None

    estoque_id_i = _to_int(estoque_id)
    estante_i = _to_int(estante) or 1
    if not estoque_id_i:
        flash('Selecione um item do estoque.', 'danger')
        return redirect(url_for('estoque_pecas.mapa', estante=estante_i))

    estoque_item = EstoquePecas.query.get_or_404(estoque_id_i)
    slot_temp_id = getattr(estoque_item, 'slot_temp_id', None)

    estoque_item.slot_temp_id = None
    estoque_item.estante = None
    estoque_item.secao = None
    estoque_item.linha = None
    estoque_item.coluna = None
    estoque_item.linha_fim = None
    estoque_item.coluna_fim = None
    estoque_item.slots_json = None
    db.session.commit()

    # Se estava em temporário, remover o temporário quando ficar vazio
    if slot_temp_id:
        rest = EstoquePecas.query.filter_by(slot_temp_id=slot_temp_id).first()
        if not rest:
            slot = EstoquePecasSlotTemp.query.get(slot_temp_id)
            if slot:
                db.session.delete(slot)
                db.session.commit()

    flash('Localização removida com sucesso!', 'success')
    return redirect(url_for('estoque_pecas.mapa', estante=estante_i))


@estoque_pecas.route('/estoque-pecas/mapa/temp/remover', methods=['POST'])
def remover_slot_temporario_mapa():
    estante = request.form.get('estante')
    secao = request.form.get('secao')
    linha = request.form.get('linha')
    coluna = request.form.get('coluna')

    def _to_int(v):
        try:
            if v is None or str(v).strip() == '':
                return None
            return int(v)
        except Exception:
            return None

    estante_i = _to_int(estante) or 1
    secao_i = _to_int(secao)
    linha_i = _to_int(linha)
    coluna_i = _to_int(coluna)

    if not (secao_i and linha_i and coluna_i):
        flash('Endereço inválido para remover temporário.', 'danger')
        return redirect(url_for('estoque_pecas.mapa', estante=estante_i))

    slot = (
        EstoquePecasSlotTemp.query
        .filter_by(estante=estante_i, secao=secao_i, linha=linha_i, coluna=coluna_i)
        .first()
    )
    if not slot:
        flash('Slot temporário não encontrado.', 'warning')
        return redirect(url_for('estoque_pecas.mapa', estante=estante_i))

    # Só remove se estiver vazio
    existe = EstoquePecas.query.filter_by(slot_temp_id=slot.id).first()
    if existe:
        flash('Este temporário ainda possui itens. Remova os itens primeiro.', 'warning')
        return redirect(url_for('estoque_pecas.mapa', estante=estante_i))

    db.session.delete(slot)
    db.session.commit()
    flash('Slot temporário removido.', 'success')
    return redirect(url_for('estoque_pecas.mapa', estante=estante_i))

@estoque_pecas.route('/estoque-pecas/atualizar-localizacao/<int:estoque_id>', methods=['POST'])
def atualizar_localizacao(estoque_id):
    """Rota para atualizar a localização (prateleira e posição) de um item no estoque"""
    estoque_item = EstoquePecas.query.get_or_404(estoque_id)
    
    if request.method == 'POST':
        estante = request.form.get('estante')
        secao = request.form.get('secao')
        linha = request.form.get('linha')
        coluna = request.form.get('coluna')
        coluna_fim = request.form.get('coluna_fim')
        permitir_compartilhado = (request.form.get('permitir_compartilhado') or '').strip().lower() in ('1', 'true', 'yes', 'sim', 'on')

        def _to_int(v):
            try:
                if v is None or str(v).strip() == '':
                    return None
                return int(v)
            except Exception:
                return None
        
        estoque_item.prateleira = None
        estoque_item.posicao = None

        estante_i = _to_int(estante)
        secao_i = _to_int(secao)
        linha_i = _to_int(linha)
        coluna_i = _to_int(coluna)
        coluna_fim_i = _to_int(coluna_fim)

        if estante_i and secao_i and linha_i and coluna_i:
            if coluna_i < 1 or coluna_i > 6:
                flash('Coluna inválida para o mapa (use 1 a 6).', 'warning')
                return redirect(url_for('estoque_pecas.index'))

            if coluna_fim_i is not None:
                if coluna_fim_i < coluna_i:
                    coluna_fim_i = coluna_i
                if coluna_fim_i < 1 or coluna_fim_i > 6:
                    flash('Coluna final inválida para o mapa (use 1 a 6).', 'warning')
                    return redirect(url_for('estoque_pecas.index'))

            col_fim_check = coluna_fim_i if coluna_fim_i is not None else coluna_i
            col_ini_check = coluna_i
            ocupacoes = (
                EstoquePecas.query
                .filter(
                    EstoquePecas.estante == estante_i,
                    EstoquePecas.secao == secao_i,
                    EstoquePecas.linha == linha_i,
                    EstoquePecas.id != estoque_item.id,
                )
                .all()
            )

            def _ranges_overlap(a1, a2, b1, b2):
                return max(a1, b1) <= min(a2, b2)

            conflita = []
            for o in ocupacoes:
                o_ini = int(o.coluna) if o.coluna else None
                if not o_ini:
                    continue
                o_fim = int(o.coluna_fim) if getattr(o, 'coluna_fim', None) else o_ini
                o_fim = max(o_ini, min(o_fim, 6))
                if _ranges_overlap(col_ini_check, col_fim_check, o_ini, o_fim):
                    conflita.append(o)

            if conflita:
                if not permitir_compartilhado:
                    flash('Esta posição já está ocupada por outro item. Marque "Permitir compartilhado" para permitir mais de um item no mesmo slot.', 'warning')
                    return redirect(url_for('estoque_pecas.index'))
                if any(not getattr(o, 'permitir_compartilhado', False) for o in conflita):
                    flash('Esta posição já tem item(s) que não permitem compartilhamento. Ajuste o(s) item(ns) existente(s) para permitir compartilhamento antes.', 'warning')
                    return redirect(url_for('estoque_pecas.index'))

        estoque_item.estante = estante_i
        estoque_item.secao = secao_i
        estoque_item.linha = linha_i
        estoque_item.coluna = coluna_i
        estoque_item.coluna_fim = coluna_fim_i
        estoque_item.permitir_compartilhado = permitir_compartilhado
        
        db.session.commit()
        flash('Localização atualizada com sucesso!', 'success')
    
    return redirect(url_for('estoque_pecas.index'))

@estoque_pecas.route('/estoque-pecas/movimentacao-rapida/<int:estoque_id>/<string:tipo>', methods=['POST'])
def movimentacao_rapida(estoque_id, tipo):
    """Rota para movimentação rápida (entrada ou saída) de itens no estoque"""
    estoque_item = EstoquePecas.query.get_or_404(estoque_id)
    
    if request.method == 'POST':
        try:
            quantidade = int(request.form.get('quantidade', 1))
            if quantidade <= 0:
                flash('A quantidade deve ser maior que zero', 'danger')
                return redirect(url_for('estoque_pecas.index'))
        except ValueError:
            flash('A quantidade deve ser um número inteiro', 'danger')
            return redirect(url_for('estoque_pecas.index'))
        
        referencia = request.form.get('referencia', '')
        observacao = request.form.get('observacao', 'Movimentação rápida')
        
        if tipo == 'entrada':
            estoque_item.quantidade += quantidade
        elif tipo == 'saida':
            if estoque_item.quantidade < quantidade:
                flash('Quantidade insuficiente em estoque!', 'danger')
                return redirect(url_for('estoque_pecas.index'))
            estoque_item.quantidade -= quantidade
        else:
            flash('Tipo de movimentação inválido!', 'danger')
            return redirect(url_for('estoque_pecas.index'))
        
        # Registrar movimentação
        movimentacao = MovimentacaoEstoquePecas(
            estoque_pecas_id=estoque_item.id,
            tipo=tipo,
            quantidade=quantidade,
            data=datetime.now().date(),
            referencia=referencia,
            observacao=observacao
        )
        
        db.session.add(movimentacao)
        db.session.commit()
        
        flash(f'Movimentação de {quantidade} item(ns) registrada com sucesso!', 'success')
    
    return redirect(url_for('estoque_pecas.index'))
