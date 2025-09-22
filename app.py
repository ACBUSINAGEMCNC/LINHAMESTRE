import os
import sys
import datetime
import subprocess
import sqlite3
import logging
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do banco de dados
basedir = os.path.abspath(os.path.dirname(__file__))
# Diretório gravável em ambientes serverless (Vercel). Somente /tmp é permitido.
WRITABLE_DIR = '/tmp' if os.getenv('VERCEL') else basedir

# Logger do módulo
logger = logging.getLogger(__name__)

def verificar_inicializar_banco():
    """Verifica se o banco de dados existe e o inicializa se necessário."""
    database_url = os.getenv('DATABASE_URL', '')
    
    # Se for PostgreSQL (Supabase), usar script de migração rápido
    if database_url.startswith('postgresql://'):
        logger.info("Usando PostgreSQL (Supabase) - verificando tabelas de apontamento...")
        try:
            # Usar script rápido com timeout
            result = subprocess.run(
                [sys.executable, 'migrate_apontamento_supabase_fast.py'], 
                timeout=15,  # Timeout de 15 segundos
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Tabelas PostgreSQL verificadas/criadas com sucesso.")
            else:
                logger.warning(f"Script de migração retornou código {result.returncode}")
                if result.stderr:
                    logger.warning(f"Stderr: {result.stderr[:200]}")
                    
        except subprocess.TimeoutExpired:
            logger.warning("Timeout na migração PostgreSQL - continuando sem migração")
                
        except subprocess.CalledProcessError as e:
            logger.warning(f"Migração retornou código {e.returncode}, mas pode estar OK")
        except Exception as e:
            logger.warning(f"Erro na migração PostgreSQL: {str(e)[:100]} - continuando")
            
        # Executar migrações adicionais para PostgreSQL
        try:
            from migrations.add_categoria_trabalho import migrate_postgres
            if migrate_postgres():
                logger.info("Coluna categoria_trabalho verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna categoria_trabalho.")
        except Exception as col_err:
            logger.warning(f"Erro ao migrar coluna categoria_trabalho: {str(col_err)}")
            
        # Executar migração para adicionar colunas imagem e data_cadastro
        try:
            from migrations.add_columns_maquina import migrate_postgres as migrate_colunas_postgres
            if migrate_colunas_postgres():
                logger.info("Colunas imagem e data_cadastro verificadas/adicionadas com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar colunas imagem e data_cadastro.")
        except Exception as cols_err:
            logger.warning(f"Erro ao migrar colunas imagem e data_cadastro: {str(cols_err)}")
            
        return
    
    # Para SQLite, verificar se arquivo existe
    logger.info("Usando SQLite local...")
    db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(db_dir, 'database.db')
    
    if not os.path.exists(db_path):
        logger.info(f"Banco de dados SQLite não encontrado em {db_path}. Inicializando...")
        subprocess.run([sys.executable, 'init_db_local.py'], check=True)
        logger.info("Banco de dados SQLite inicializado com sucesso.")
    else:
        logger.info(f"Banco de dados SQLite verificado: {db_path}")
        
        # Verificar se tabelas de apontamento existem
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Verificar se tabela apontamento_producao existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apontamento_producao';")
            if not cursor.fetchone():
                logger.info("Tabelas de apontamento não encontradas. Executando migração...")
                subprocess.run([sys.executable, 'migrate_apontamento.py'], check=True)
                logger.info("Migração de apontamento concluída.")
            
            # Verificar se tabela maquina tem a coluna categoria_trabalho
            try:
                cursor.execute("PRAGMA table_info(maquina)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'categoria_trabalho' not in columns:
                    logger.info("Coluna categoria_trabalho não encontrada na tabela maquina. Executando migração...")
                    from migrations.add_categoria_trabalho import migrate_sqlite
                    if migrate_sqlite():
                        logger.info("Coluna categoria_trabalho adicionada com sucesso à tabela maquina.")
                    else:
                        logger.warning("Falha ao adicionar coluna categoria_trabalho à tabela maquina.")
                        
                # Verificar se tabela maquina tem as colunas imagem e data_cadastro
                if 'imagem' not in columns or 'data_cadastro' not in columns:
                    logger.info("Colunas imagem ou data_cadastro não encontradas na tabela maquina. Executando migração...")
                    from migrations.add_columns_maquina import migrate_sqlite
                    if migrate_sqlite():
                        logger.info("Colunas imagem e data_cadastro adicionadas com sucesso à tabela maquina.")
                    else:
                        logger.warning("Falha ao adicionar colunas imagem e data_cadastro à tabela maquina.")
            except Exception as col_err:
                logger.warning(f"Erro ao verificar/adicionar colunas na tabela maquina: {str(col_err)}")
                
            conn.close()
            
        except Exception as e:
            logger.exception("Erro ao verificar tabelas")
            # Se houver erro, tentar migração
            try:
                subprocess.run([sys.executable, 'migrate_apontamento.py'], check=True)
                logger.info("Migração de apontamento concluída.")
            except Exception as migrate_error:
                logger.exception("Erro na migração")

def create_app():
    # Definir diretório de banco gravável para init_db.py
    os.environ['DB_DIR'] = WRITABLE_DIR
    # Verificar e inicializar o banco de dados antes de criar a aplicação (a menos que pulado)
    skip_db_checks = os.getenv('SKIP_DB_CHECKS', '').strip().lower() in ('1', 'true', 'yes')
    if not skip_db_checks:
        verificar_inicializar_banco()
    else:
        logger.info("SKIP_DB_CHECKS habilitado: pulando verificar_inicializar_banco()")
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'acbusinagem2023')
    # Configurar DATABASE_URL: PostgreSQL (produção) ou SQLite (desenvolvimento/temporário)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        # Usar SQLite local como fallback
        db_path = os.path.join(WRITABLE_DIR, 'database.db')
        database_url = f'sqlite:///{db_path}'
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.logger.info("Usando banco: %s", 'PostgreSQL (Supabase)' if database_url.startswith('postgresql://') else 'SQLite')
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
        except (PermissionError, OSError):
            pass  # Ignorar erros de permissão ou sistema de arquivos somente leitura
    try:
        os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)
    except (PermissionError, OSError):
        pass  # Ignorar erros de permissão ou sistema de arquivos somente leitura
    
    # Inicializar SQLAlchemy
    from models import db
    db.init_app(app)
    
    if not skip_db_checks:
        with app.app_context():
            db.create_all()
            db_type = 'PostgreSQL (Supabase)' if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql://') else 'SQLite'
            app.logger.info("Tabelas %s criadas/verificadas com sucesso.", db_type)
            
            # Garantir que o usuário admin existe (especialmente importante no Vercel)
            from models import Usuario
            from werkzeug.security import generate_password_hash
            
            admin_user = Usuario.query.filter_by(email='admin@acbusinagem.com.br').first()
            if not admin_user:
                admin_user = Usuario(
                    nome='Administrador',
                    email='admin@acbusinagem.com.br',
                    senha_hash=generate_password_hash('admin123'),
                    nivel_acesso='admin',
                    acesso_pedidos=True,
                    acesso_kanban=True,
                    acesso_estoque=True,
                    acesso_cadastros=True,
                    pode_finalizar_os=True
                )
                db.session.add(admin_user)
                db.session.commit()
                app.logger.info("Usuário admin criado no banco %s.", db_type)
            else:
                app.logger.info("Usuário admin já existe no banco %s.", db_type)
    else:
        app.logger.info("SKIP_DB_CHECKS habilitado: pulando db.create_all() e seed do usuário admin")
    
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
    from routes.apontamento import apontamento_bp
    from routes.maquinas import maquinas
    from routes.castanhas import castanhas
    from routes.gabaritos_centro import gabaritos_centro
    from routes.gabaritos_rosca import gabaritos_rosca
    from routes.novas_folhas_processo import novas_folhas_processo
    
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
    app.register_blueprint(apontamento_bp, url_prefix='/apontamento')
    app.register_blueprint(maquinas)
    app.register_blueprint(castanhas)
    app.register_blueprint(gabaritos_centro)
    app.register_blueprint(gabaritos_rosca)
    app.register_blueprint(novas_folhas_processo)
    
    # Rota para redirecionar URLs Supabase
    @app.route('/uploads/supabase:/<path:file_path>')
    def supabase_redirect(file_path):
        import os
        from urllib.parse import quote
        from flask import current_app as _current_app
        
        # Construir URL pública direta sem usar get_file_url para evitar loop
        bucket_env = os.environ.get('SUPABASE_BUCKET', 'uploads')
        supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        
        # Log da tentativa de redirecionamento
        _current_app.logger.info("Tentativa de redirecionamento Supabase para: %s", file_path)
        _current_app.logger.debug("SUPABASE_URL configurado: %s", 'Sim' if supabase_url else 'Não')
        _current_app.logger.debug("SUPABASE_BUCKET: %s", bucket_env)
        
        if supabase_url:
            # Remover qualquer '/' inicial para evitar '//'
            path_clean = file_path.lstrip('/')
            
            # Detectar se o caminho já inclui o bucket como primeiro segmento.
            # Mantém compatibilidade com caminhos antigos: 'imagens/arquivo.jpg'
            # e novos: '<bucket>/imagens/arquivo.jpg'
            KNOWN_FOLDERS = {'imagens', 'desenhos', 'instrucoes', 'cnc_files', 'maquinas', 'castanhas', 'gabaritos', 'folhas_processo'}
            parts = path_clean.split('/', 1)
            if len(parts) > 1 and parts[0] not in KNOWN_FOLDERS:
                bucket = parts[0]
                rel_path = parts[1]
            else:
                bucket = bucket_env
                rel_path = path_clean

            # Não codificar as barras do caminho
            rel_encoded = quote(rel_path, safe='/')
            public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{rel_encoded}"
            _current_app.logger.info("Redirecionando para URL Supabase: %s", public_url)
            return redirect(public_url, code=302)
        else:
            # Log do erro de configuração
            _current_app.logger.error("SUPABASE_URL não configurado! Não é possível redirecionar para: %s", file_path)
            _current_app.logger.error("Configure a variável de ambiente SUPABASE_URL para usar o Supabase Storage")
            
            # Em vez de retornar 404, tentar servir arquivo local como fallback
            _current_app.logger.info("Tentando fallback para arquivo local...")
            
            # Extrair apenas o nome do arquivo e pasta
            path_clean = file_path.lstrip('/')
            parts = path_clean.split('/', 1)
            
            if len(parts) >= 2:
                folder = parts[0]  # ex: 'imagens'
                filename = parts[1]  # ex: 'df879b3c_POLIA_TENSORA.jpg'
                
                # Tentar servir arquivo local
                if folder == 'imagens':
                    local_path = os.path.join(_current_app.config['UPLOAD_FOLDER_IMAGENS'], filename)
                elif folder == 'desenhos':
                    local_path = os.path.join(_current_app.config['UPLOAD_FOLDER_DESENHOS'], filename)
                elif folder == 'instrucoes':
                    local_path = os.path.join(_current_app.config['UPLOAD_FOLDER_INSTRUCOES'], filename)
                else:
                    local_path = None
                
                if local_path and os.path.exists(local_path):
                    _current_app.logger.info("Arquivo local encontrado, servindo: %s", local_path)
                    return send_file(local_path)
                else:
                    _current_app.logger.warning("Arquivo local não encontrado: %s", local_path if local_path else 'caminho inválido')
            
            from flask import abort
            _current_app.logger.error("Retornando 404 para: %s", file_path)
            abort(404)
    
    app.register_blueprint(folhas_processo)
    
    # Adicionar contexto global para templates
    @app.context_processor
    def inject_user():
        from utils import get_file_url
        user_data = {
            'usuario_nome': session.get('usuario_nome', 'Visitante'),
            'usuario_nivel': session.get('usuario_nivel', None),
            'acesso_pedidos': session.get('acesso_pedidos', False),
            'acesso_kanban': session.get('acesso_kanban', False),
            'acesso_estoque': session.get('acesso_estoque', False),
            'acesso_cadastros': session.get('acesso_cadastros', False),
            'pode_finalizar_os': session.get('pode_finalizar_os', False),
            'acesso_finalizar_os': session.get('pode_finalizar_os', False),
            'get_file_url': get_file_url  # Adicionar função para templates
        }
        return user_data
    
    # Adicionar função now() para os templates
    @app.context_processor
    def utility_processor():
        def now():
            return datetime.datetime.now()
        return dict(now=now)
    
    # Adicionar filtros customizados
    @app.template_filter('nl2br')
    def nl2br_filter(s):
        """Converte quebras de linha em tags <br>"""
        if s is None:
            return ''
        from markupsafe import Markup, escape
        # Escapar HTML primeiro, depois converter quebras de linha
        escaped = escape(str(s))
        return Markup(str(escaped).replace('\n', '<br>\n'))
    
    @app.template_filter('safe')
    def safe_filter(s):
        """Marca string como segura para HTML"""
        if s is None:
            return ''
        from markupsafe import Markup
        return Markup(str(s))
    
    # Adicionar manipuladores de erro
    @app.errorhandler(404)
    def pagina_nao_encontrada(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def erro_servidor(e):
        return render_template('500.html'), 500
    
    return app
