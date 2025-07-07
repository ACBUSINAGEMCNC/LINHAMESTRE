import os
import sys
import datetime
import sqlite3
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Configuração do banco de dados
basedir = os.path.abspath(os.path.dirname(__file__))
# Diretório gravável em ambientes serverless (Vercel). Somente /tmp é permitido.
WRITABLE_DIR = '/tmp' if os.getenv('VERCEL') else basedir

def verificar_inicializar_banco():
    """Verifica se o banco de dados existe e contém todas as tabelas necessárias.
    Se não existir ou faltar alguma tabela, executa o script de inicialização."""
    # Se DATABASE_URL estiver definido e for SQLite, extrair caminho do arquivo;
    # caso contrário, usar diretório adequado
    db_uri_env = os.getenv('DATABASE_URL')
    if db_uri_env and db_uri_env.startswith('sqlite:///'):
        db_path = db_uri_env.replace('sqlite:///','').split('?')[0]
    else:
        db_path = os.path.join(WRITABLE_DIR, 'database.db')
    
    # Verificar se o banco de dados existe
    if not os.path.exists(db_path):
        print("Banco de dados não encontrado. Inicializando...")
        exec(open(os.path.join(basedir, 'init_db.py')).read())
        return
    
    # Verificar se todas as tabelas necessárias existem
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas_existentes = [tabela[0] for tabela in cursor.fetchall()]
        
        tabelas_necessarias = [
            'cliente', 'unidade_entrega', 'material', 'trabalho', 'item', 
            'pedido', 'ordem_servico', 'pedido_ordem_servico', 'pedido_material',
            'estoque', 'estoque_pecas', 'movimentacao_estoque', 
            'movimentacao_estoque_pecas', 'usuario', 'item_trabalho', 'item_material',
            'item_pedido_material', 'registro_mensal', 'backup'
        ]
        
        tabelas_faltantes = [tabela for tabela in tabelas_necessarias if tabela not in tabelas_existentes]
        
        # Verificar se as colunas necessárias existem nas tabelas
        colunas_faltantes = False
        if 'item' in tabelas_existentes:
            cursor.execute("PRAGMA table_info(item)")
            colunas_item = [coluna[1] for coluna in cursor.fetchall()]
            if 'codigo_acb' not in colunas_item:
                colunas_faltantes = True
                print("Coluna 'codigo_acb' faltando na tabela 'item'")
        
        if 'usuario' in tabelas_existentes:
            cursor.execute("PRAGMA table_info(usuario)")
            colunas_usuario = [coluna[1] for coluna in cursor.fetchall()]
            if 'senha_hash' not in colunas_usuario:
                colunas_faltantes = True
                print("Coluna 'senha_hash' faltando na tabela 'usuario'")
        
        if tabelas_faltantes or colunas_faltantes:
            print(f"Tabelas faltantes no banco de dados: {tabelas_faltantes}")
            if colunas_faltantes:
                print("Colunas necessárias faltando em tabelas existentes")
            print("Reinicializando o banco de dados...")
            conn.close()
            # Fazer backup do banco atual antes de recriar
            if os.path.exists(db_path):
                backup_path = f"{db_path}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                os.rename(db_path, backup_path)
                print(f"Backup do banco de dados criado em: {backup_path}")
            
            # Executar script de inicialização
            exec(open(os.path.join(basedir, 'init_db.py')).read())
        else:
            print("Banco de dados verificado: todas as tabelas necessárias estão presentes.")
            conn.close()
    except Exception as e:
        print(f"Erro ao verificar o banco de dados: {e}")
        print("Reinicializando o banco de dados...")
        # Executar script de inicialização
        exec(open(os.path.join(basedir, 'init_db.py')).read())

def create_app():
    # Definir diretório de banco gravável para init_db.py
    os.environ['DB_DIR'] = WRITABLE_DIR
    # Verificar e inicializar o banco de dados antes de criar a aplicação
    verificar_inicializar_banco()
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'acbusinagem2023'
    # Utilizar DATABASE_URL do ambiente se existir, senão SQLite local (ou /tmp em serverless)
    default_sqlite_path = os.path.join(WRITABLE_DIR, 'database.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f'sqlite:///{default_sqlite_path}')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER_DESENHOS'] = os.path.join(basedir, 'uploads/desenhos')
    app.config['UPLOAD_FOLDER_INSTRUCOES'] = os.path.join(basedir, 'uploads/instrucoes')
    app.config['UPLOAD_FOLDER_IMAGENS'] = os.path.join(basedir, 'uploads/imagens')
    app.config['BACKUP_FOLDER'] = os.path.join(basedir, 'backups')
    
    # Garantir que as pastas de upload existam
    # Tentar criar pastas de upload se possível; ignorar em ambiente somente leitura
    for path in [
        app.config['UPLOAD_FOLDER_DESENHOS'],
        app.config['UPLOAD_FOLDER_INSTRUCOES'],
        app.config['UPLOAD_FOLDER_IMAGENS']
    ]:
        try:
            os.makedirs(path, exist_ok=True)
        except PermissionError:
            pass
    os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)
    
    # Inicializar SQLAlchemy
    from models import db
    db.init_app(app)
    
    # Criar todas as tabelas se não existirem
    with app.app_context():
        try:
            db.create_all()
            print("Tabelas SQLAlchemy criadas/verificadas com sucesso.")
        except Exception as e:
            print(f"Erro ao criar tabelas SQLAlchemy: {e}")
    
    # Registrar blueprints
    from routes.clientes import clientes
    from routes.materiais import materiais
    from routes.trabalhos import trabalhos
    from routes.itens import itens
    from routes.pedidos import pedidos
    from routes.ordens import ordens
    from routes.pedidos_material import pedidos_material
    from routes.estoque import estoque
    from routes.kanban import kanban
    from routes.arquivos import arquivos
    from routes.estoque_pecas import estoque_pecas
    from routes.auth import auth
    from routes.backup import backup
    from routes.main import main
    from routes.folhas_processo import folhas_processo
    
    app.register_blueprint(clientes)
    app.register_blueprint(materiais)
    app.register_blueprint(trabalhos)
    app.register_blueprint(itens)
    app.register_blueprint(pedidos)
    app.register_blueprint(ordens)
    app.register_blueprint(pedidos_material)
    app.register_blueprint(estoque)
    app.register_blueprint(kanban)
    app.register_blueprint(arquivos)
    app.register_blueprint(estoque_pecas)
    app.register_blueprint(auth)
    app.register_blueprint(backup)
    app.register_blueprint(main)
    app.register_blueprint(folhas_processo)
    
    # Adicionar contexto global para templates
    @app.context_processor
    def inject_user():
        user_data = {
            'usuario_nome': session.get('usuario_nome', 'Visitante'),
            'usuario_nivel': session.get('usuario_nivel', None),
            'acesso_pedidos': session.get('acesso_pedidos', False),
            'acesso_kanban': session.get('acesso_kanban', False),
            'acesso_estoque': session.get('acesso_estoque', False),
            'acesso_cadastros': session.get('acesso_cadastros', False),
            'pode_finalizar_os': session.get('pode_finalizar_os', False),
        'acesso_finalizar_os': session.get('pode_finalizar_os', False)
        }
        return user_data
    
    # Adicionar função now() para os templates
    @app.context_processor
    def utility_processor():
        def now():
            return datetime.datetime.now()
        return dict(now=now)
    
    # Adicionar manipuladores de erro
    @app.errorhandler(404)
    def pagina_nao_encontrada(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def erro_servidor(e):
        return render_template('500.html'), 500
    
    return app
