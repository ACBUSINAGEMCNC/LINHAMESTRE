from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from sqlalchemy import or_
from models import AuditLog


auditoria = Blueprint('auditoria', __name__)


def _require_admin():
    usuario = getattr(g, 'usuario', None)
    if not usuario or getattr(usuario, 'nivel_acesso', None) != 'admin':
        flash('Você não tem permissão para acessar esta página', 'danger')
        return False
    return True


@auditoria.route('/auditoria')
def listar_auditoria():
    if not _require_admin():
        return redirect(url_for('main.index'))

    q = (request.args.get('q') or '').strip()
    usuario = (request.args.get('usuario') or '').strip()
    entidade_tipo = (request.args.get('entidade_tipo') or '').strip()
    entidade_id = (request.args.get('entidade_id') or '').strip()
    acao = (request.args.get('acao') or '').strip()
    data_de = (request.args.get('data_de') or '').strip()
    data_ate = (request.args.get('data_ate') or '').strip()

    try:
        page = int(request.args.get('page', 1))
    except Exception:
        page = 1
    if page < 1:
        page = 1

    try:
        per_page = int(request.args.get('per_page', 50))
    except Exception:
        per_page = 50
    per_page = max(10, min(200, per_page))

    query = AuditLog.query

    if acao:
        query = query.filter(AuditLog.acao == acao)

    if entidade_tipo:
        query = query.filter(AuditLog.entidade_tipo == entidade_tipo)

    if entidade_id:
        query = query.filter(AuditLog.entidade_id == entidade_id)

    if usuario:
        if usuario.isdigit():
            query = query.filter(or_(AuditLog.usuario_nome.ilike(f'%{usuario}%'), AuditLog.usuario_id == int(usuario)))
        else:
            query = query.filter(AuditLog.usuario_nome.ilike(f'%{usuario}%'))

    if q:
        query = query.filter(
            or_(
                AuditLog.usuario_nome.ilike(f'%{q}%'),
                AuditLog.acao.ilike(f'%{q}%'),
                AuditLog.entidade_tipo.ilike(f'%{q}%'),
                AuditLog.entidade_id.ilike(f'%{q}%'),
                AuditLog.endpoint.ilike(f'%{q}%'),
                AuditLog.ip.ilike(f'%{q}%'),
                AuditLog.mudancas_json.ilike(f'%{q}%'),
            )
        )

    # Datas (mantém simples: compara strings YYYY-MM-DD via conversão no banco quando suportado)
    # Para compatibilidade SQLite/Postgres sem dependências extras, vamos filtrar em Python se necessário no template.
    # Aqui tentamos filtrar via cast textual no formato ISO.
    if data_de:
        query = query.filter(AuditLog.data_criacao >= f'{data_de} 00:00:00')
    if data_ate:
        query = query.filter(AuditLog.data_criacao <= f'{data_ate} 23:59:59')

    total = query.count()
    logs = (
        query.order_by(AuditLog.data_criacao.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    total_pages = (total + per_page - 1) // per_page if total else 1

    return render_template(
        'auditoria/listar.html',
        logs=logs,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        filtros={
            'q': q,
            'usuario': usuario,
            'entidade_tipo': entidade_tipo,
            'entidade_id': entidade_id,
            'acao': acao,
            'data_de': data_de,
            'data_ate': data_ate,
        },
    )


@auditoria.route('/auditoria/<entidade_tipo>/<entidade_id>')
def auditoria_entidade(entidade_tipo, entidade_id):
    if not _require_admin():
        return redirect(url_for('main.index'))

    logs = (
        AuditLog.query.filter(
            AuditLog.entidade_tipo == entidade_tipo,
            AuditLog.entidade_id == str(entidade_id),
        )
        .order_by(AuditLog.data_criacao.desc())
        .limit(500)
        .all()
    )

    return render_template(
        'auditoria/entidade.html',
        logs=logs,
        entidade_tipo=entidade_tipo,
        entidade_id=str(entidade_id),
    )
