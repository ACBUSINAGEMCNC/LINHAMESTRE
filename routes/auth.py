from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario
from functools import wraps

auth = Blueprint('auth', __name__)

# Decorator para verificar se o usuário está logado
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Decorator para verificar permissões específicas
def permissao_requerida(permissao):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'usuario_id' not in session:
                flash('Por favor, faça login para acessar esta página', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            usuario = Usuario.query.get(session['usuario_id'])
            if not usuario:
                flash('Usuário não encontrado', 'danger')
                return redirect(url_for('auth.login'))
            
            if usuario.nivel_acesso == 'admin':
                return f(*args, **kwargs)
            
            if permissao == 'kanban' and not usuario.acesso_kanban:
                flash('Você não tem permissão para acessar esta página', 'danger')
                return redirect(url_for('main.index'))
            
            if permissao == 'estoque' and not usuario.acesso_estoque:
                flash('Você não tem permissão para acessar esta página', 'danger')
                return redirect(url_for('main.index'))
            
            if permissao == 'pedidos' and not usuario.acesso_pedidos:
                flash('Você não tem permissão para acessar esta página', 'danger')
                return redirect(url_for('main.index'))
            
            if permissao == 'cadastros' and not usuario.acesso_cadastros:
                flash('Você não tem permissão para acessar esta página', 'danger')
                return redirect(url_for('main.index'))
            
            if permissao == 'finalizar_os' and not usuario.pode_finalizar_os:
                flash('Você não tem permissão para finalizar ordens de serviço', 'danger')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if not usuario or not check_password_hash(usuario.senha_hash, senha):
            flash('Email ou senha incorretos. Por favor, tente novamente.', 'danger')
            return render_template('auth/login.html')
        
        # Registrar login bem-sucedido
        from datetime import datetime
        usuario.ultimo_acesso = datetime.utcnow()
        db.session.commit()
        
        # Armazenar informações do usuário na sessão
        session['usuario_id'] = usuario.id
        session['usuario_nome'] = usuario.nome
        session['usuario_nivel'] = usuario.nivel_acesso
        session['acesso_kanban'] = usuario.acesso_kanban
        session['acesso_estoque'] = usuario.acesso_estoque
        session['acesso_pedidos'] = usuario.acesso_pedidos
        session['acesso_cadastros'] = usuario.acesso_cadastros
        session['pode_finalizar_os'] = usuario.pode_finalizar_os
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('main.index'))
    
    return render_template('auth/login.html')

@auth.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema com sucesso.', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/usuarios')
@login_required
@permissao_requerida('admin')
def listar_usuarios():
    usuarios = Usuario.query.all()
    return render_template('auth/usuarios.html', usuarios=usuarios)

@auth.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
@permissao_requerida('admin')
def novo_usuario():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        nivel_acesso = request.form.get('nivel_acesso')
        
        # Verificar se o email já está em uso
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash('Este email já está em uso. Por favor, escolha outro.', 'danger')
            return render_template('auth/novo_usuario.html')
        
        # Definir permissões com base no nível de acesso
        acesso_kanban = False
        acesso_estoque = False
        acesso_pedidos = False
        acesso_cadastros = False
        pode_finalizar_os = False
        
        if nivel_acesso == 'admin':
            acesso_kanban = True
            acesso_estoque = True
            acesso_pedidos = True
            acesso_cadastros = True
            pode_finalizar_os = True
        else:
            acesso_kanban = 'acesso_kanban' in request.form
            acesso_estoque = 'acesso_estoque' in request.form
            acesso_pedidos = 'acesso_pedidos' in request.form
            acesso_cadastros = 'acesso_cadastros' in request.form
            pode_finalizar_os = 'pode_finalizar_os' in request.form
        
        # Criar novo usuário
        novo_usuario = Usuario(
            nome=nome,
            email=email,
            senha_hash=generate_password_hash(senha),
            nivel_acesso=nivel_acesso,
            acesso_kanban=acesso_kanban,
            acesso_estoque=acesso_estoque,
            acesso_pedidos=acesso_pedidos,
            acesso_cadastros=acesso_cadastros,
            pode_finalizar_os=pode_finalizar_os
        )
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        flash('Usuário criado com sucesso!', 'success')
        return redirect(url_for('auth.listar_usuarios'))
    
    return render_template('auth/novo_usuario.html')

@auth.route('/usuarios/editar/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
@permissao_requerida('admin')
def editar_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        nivel_acesso = request.form.get('nivel_acesso')
        
        # Verificar se o email já está em uso por outro usuário
        usuario_existente = Usuario.query.filter(Usuario.email == email, Usuario.id != usuario_id).first()
        if usuario_existente:
            flash('Este email já está em uso. Por favor, escolha outro.', 'danger')
            return render_template('auth/editar_usuario.html', usuario=usuario)
        
        # Atualizar senha se fornecida
        senha = request.form.get('senha')
        if senha and senha.strip():
            usuario.senha_hash = generate_password_hash(senha)
        
        # Atualizar dados básicos
        usuario.nome = nome
        usuario.email = email
        usuario.nivel_acesso = nivel_acesso
        
        # Definir permissões com base no nível de acesso
        if nivel_acesso == 'admin':
            usuario.acesso_kanban = True
            usuario.acesso_estoque = True
            usuario.acesso_pedidos = True
            usuario.acesso_cadastros = True
            usuario.pode_finalizar_os = True
        else:
            usuario.acesso_kanban = 'acesso_kanban' in request.form
            usuario.acesso_estoque = 'acesso_estoque' in request.form
            usuario.acesso_pedidos = 'acesso_pedidos' in request.form
            usuario.acesso_cadastros = 'acesso_cadastros' in request.form
            usuario.pode_finalizar_os = 'pode_finalizar_os' in request.form
        
        db.session.commit()
        
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('auth.listar_usuarios'))
    
    return render_template('auth/editar_usuario.html', usuario=usuario)

@auth.route('/usuarios/excluir/<int:usuario_id>', methods=['POST'])
@login_required
@permissao_requerida('admin')
def excluir_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # Não permitir excluir o próprio usuário
    if usuario_id == session.get('usuario_id'):
        flash('Você não pode excluir seu próprio usuário!', 'danger')
        return redirect(url_for('auth.listar_usuarios'))
    
    db.session.delete(usuario)
    db.session.commit()
    
    flash('Usuário excluído com sucesso!', 'success')
    return redirect(url_for('auth.listar_usuarios'))

@auth.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    usuario = Usuario.query.get_or_404(session['usuario_id'])
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        
        # Verificar se o email já está em uso por outro usuário
        usuario_existente = Usuario.query.filter(Usuario.email == email, Usuario.id != usuario.id).first()
        if usuario_existente:
            flash('Este email já está em uso. Por favor, escolha outro.', 'danger')
            return render_template('auth/perfil.html', usuario=usuario)
        
        # Atualizar senha se fornecida
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        
        if senha_atual and nova_senha:
            if not check_password_hash(usuario.senha_hash, senha_atual):
                flash('Senha atual incorreta!', 'danger')
                return render_template('auth/perfil.html', usuario=usuario)
            
            usuario.senha_hash = generate_password_hash(nova_senha)
        
        # Atualizar dados básicos
        usuario.nome = nome
        usuario.email = email
        
        db.session.commit()
        
        # Atualizar informações da sessão
        session['usuario_nome'] = usuario.nome
        
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('auth.perfil'))
    
    return render_template('auth/perfil.html', usuario=usuario)
