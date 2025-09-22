from flask import Blueprint, redirect, url_for, flash, session, request
from models import Usuario

folhas_processo = Blueprint('folhas_processo', __name__)

# Verificação de permissão
@folhas_processo.before_request
def verificar_permissao():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    usuario = Usuario.query.get(session['usuario_id'])
    if not usuario:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('auth.login'))

# ==================== ROTAS DE REDIRECIONAMENTO PARA O NOVO SISTEMA ====================

@folhas_processo.route('/folhas-processo/item/<int:item_id>')
def listar_folhas(item_id):
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.listar_folhas'))

@folhas_processo.route('/folhas-processo/historico/<int:item_id>')
def historico_folhas(item_id):
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.listar_folhas'))

@folhas_processo.route('/folhas-processo/criar/<int:item_id>')
def criar_folha_form(item_id):
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.nova_folha'))

@folhas_processo.route('/folhas-processo/criar', methods=['POST'])
def criar_folha():
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.nova_folha'))

@folhas_processo.route('/folhas-processo/editar/<int:folha_id>')
def editar_folha(folha_id):
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.listar_folhas'))

@folhas_processo.route('/folhas-processo/salvar/<int:folha_id>', methods=['POST'])
def salvar_folha(folha_id):
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.listar_folhas'))

@folhas_processo.route('/folhas-processo/visualizar/<int:folha_id>')
def visualizar_folha(folha_id):
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.listar_folhas'))

@folhas_processo.route('/folhas-processo/<int:folha_id>/criar-nova-versao', methods=['POST'])
def criar_nova_versao(folha_id):
    """Redireciona para o novo sistema de folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.nova_folha'))

# Qualquer outra rota de folhas de processo redireciona para o novo sistema
@folhas_processo.route('/folhas-processo')
@folhas_processo.route('/folhas-processo/')
def redirecionar_geral():
    """Redireciona qualquer acesso geral às folhas de processo"""
    flash('Sistema de folhas de processo atualizado! Use o novo sistema.', 'info')
    return redirect(url_for('novas_folhas_processo.listar_folhas'))
