import os
import sys
import datetime
import subprocess
import sqlite3
import logging
import json
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file, g, has_request_context
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect
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
    force_sqlite = os.getenv('FORCE_SQLITE', '').strip().lower() in ('1', 'true', 'yes')
    database_url = '' if force_sqlite else os.getenv('DATABASE_URL', '')
    
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
            
            from migrations.add_quantidade_snapshot import migrate_postgres as migrate_snapshot_pg
            if migrate_snapshot_pg():
                logger.info("Coluna quantidade_snapshot verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna quantidade_snapshot.")

            from migrations.enable_rls_public_tables import migrate_postgres as migrate_rls_public
            if migrate_rls_public():
                logger.info("RLS verificado/habilitado nas tabelas public (Supabase).")
            else:
                logger.warning("Falha ao verificar/habilitar RLS nas tabelas public.")

            from migrations.add_indexes_and_pk_postgres import migrate_postgres as migrate_indexes_pk
            if migrate_indexes_pk():
                logger.info("Índices de FKs e PKs de tabelas backup verificados/criados (Supabase).")
            else:
                logger.warning("Falha ao verificar/criar índices de FKs e PKs de tabelas backup (Supabase).")
        except Exception as col_err:
            logger.warning(f"Erro ao migrar coluna categoria_trabalho: {str(col_err)}")
            
        # Executar migração para adicionar coluna tipo_bruto em Item
        try:
            from migrations.add_tipo_bruto_item import migrate_postgres as migrate_tipo_bruto_postgres
            if migrate_tipo_bruto_postgres():
                logger.info("Coluna tipo_bruto verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna tipo_bruto.")
        except Exception as col_err:
            logger.warning(f"Erro ao migrar coluna tipo_bruto: {str(col_err)}")
            
        # Executar migração para adicionar coluna tamanho_peca em Item
        try:
            from migrations.add_tamanho_peca_item import migrate_postgres as migrate_tamanho_peca_postgres
            if migrate_tamanho_peca_postgres():
                logger.info("Coluna tamanho_peca verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna tamanho_peca.")
        except Exception as col_err:
            logger.warning(f"Erro ao migrar coluna tamanho_peca: {str(col_err)}")
            
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
                
                # Verificar se tabela pedido_ordem_servico tem a coluna quantidade_snapshot
                cursor.execute("PRAGMA table_info(pedido_ordem_servico)")
                pos_columns = [column[1] for column in cursor.fetchall()]
                if 'quantidade_snapshot' not in pos_columns:
                    logger.info("Coluna quantidade_snapshot não encontrada na tabela pedido_ordem_servico. Executando migração...")
                    from migrations.add_quantidade_snapshot import migrate_sqlite as migrate_snapshot_sqlite
                    if migrate_snapshot_sqlite():
                        logger.info("Coluna quantidade_snapshot adicionada com sucesso à tabela pedido_ordem_servico.")
                    else:
                        logger.warning("Falha ao adicionar coluna quantidade_snapshot à tabela pedido_ordem_servico.")
                        
                # Verificar se tabela item tem a coluna tipo_bruto
                try:
                    cursor.execute("PRAGMA table_info(item)")
                    item_columns = [column[1] for column in cursor.fetchall()]
                    if 'tipo_bruto' not in item_columns:
                        logger.info("Coluna tipo_bruto não encontrada na tabela item. Executando migração...")
                        from migrations.add_tipo_bruto_item import migrate_sqlite as migrate_tipo_bruto_sqlite
                        if migrate_tipo_bruto_sqlite():
                            logger.info("Coluna tipo_bruto adicionada com sucesso à tabela item.")
                        else:
                            logger.warning("Falha ao adicionar coluna tipo_bruto à tabela item.")
                    if 'tamanho_peca' not in item_columns:
                        logger.info("Coluna tamanho_peca não encontrada na tabela item. Executando migração...")
                        from migrations.add_tamanho_peca_item import migrate_sqlite as migrate_tamanho_peca_sqlite
                        if migrate_tamanho_peca_sqlite():
                            logger.info("Coluna tamanho_peca adicionada com sucesso à tabela item.")
                        else:
                            logger.warning("Falha ao adicionar coluna tamanho_peca à tabela item.")
                except Exception as col_err:
                    logger.warning(f"Erro ao verificar/adicionar coluna tipo_bruto na tabela item: {str(col_err)}")
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
    # FORCE_SQLITE: força SQLite mesmo que DATABASE_URL esteja configurada (útil para testes locais)
    force_sqlite = os.getenv('FORCE_SQLITE', '').strip().lower() in ('1', 'true', 'yes')
    database_url = None if force_sqlite else os.getenv('DATABASE_URL')
    if not database_url:
        # Usar SQLite local como fallback ou quando FORCE_SQLITE está ativo
        db_path = os.path.join(WRITABLE_DIR, 'database.db')
        database_url = f'sqlite:///{db_path}'

    # Preferir psycopg3 (psycopg) no Python 3.13+ quando URL for PostgreSQL genérica
    # Isso evita dependência de psycopg2 que pode não ter wheel no Windows/Py3.13
    if database_url:
        db_url_lower = database_url.lower()
        if db_url_lower.startswith('postgres://'):
            database_url = 'postgresql://' + database_url[len('postgres://'):]
            db_url_lower = database_url.lower()
        if db_url_lower.startswith('postgresql://') and '+psycopg' not in db_url_lower and '+psycopg2' not in db_url_lower:
            try:
                import psycopg  # noqa: F401
                database_url = 'postgresql+psycopg://' + database_url[len('postgresql://'):]
            except Exception:
                pass
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.logger.info("Usando banco: %s", 'PostgreSQL (Supabase)' if database_url.startswith('postgresql://') else 'SQLite')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if database_url and database_url.lower().startswith('postgresql'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 180,
        }
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

    def _register_audit_logging(_app):
        if _app.extensions.get('audit_log_registered'):
            return

        from models import AuditLog

        def _get_actor():
            usuario = getattr(g, 'usuario', None)
            if usuario is not None:
                return usuario.id, getattr(usuario, 'nome', None)
            if 'usuario_id' in session:
                return session.get('usuario_id'), session.get('usuario_nome')
            return None, None

        def _get_request_meta():
            if not has_request_context():
                return None, None, None, None
            try:
                endpoint = request.endpoint
            except Exception:
                endpoint = None
            try:
                metodo = request.method
            except Exception:
                metodo = None
            try:
                ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            except Exception:
                ip = None
            try:
                ua = request.headers.get('User-Agent')
            except Exception:
                ua = None
            return endpoint, metodo, ip, ua

        def _row_identity(obj):
            try:
                mapper = inspect(obj).mapper
                pks = [col.key for col in mapper.primary_key]
                if not pks:
                    return None
                if len(pks) == 1:
                    return str(getattr(obj, pks[0], None))
                return json.dumps({k: getattr(obj, k, None) for k in pks}, ensure_ascii=False, default=str)
            except Exception:
                return None

        def _collect_changes(obj, action):
            try:
                state = inspect(obj)
                mapper = state.mapper
                changes = {}

                for attr in mapper.column_attrs:
                    key = attr.key
                    if key == 'id':
                        continue
                    hist = state.attrs[key].history

                    if action == 'create':
                        val = getattr(obj, key, None)
                        if val is not None:
                            changes[key] = {'old': None, 'new': val}
                        continue

                    if action == 'delete':
                        val = getattr(obj, key, None)
                        if val is not None:
                            changes[key] = {'old': val, 'new': None}
                        continue

                    if action == 'update':
                        if not hist.has_changes():
                            continue
                        old = hist.deleted[0] if hist.deleted else None
                        new = hist.added[0] if hist.added else getattr(obj, key, None)
                        changes[key] = {'old': old, 'new': new}

                if not changes:
                    return None
                return changes
            except Exception:
                return None

        @event.listens_for(db.session.__class__, 'before_flush')
        def _audit_before_flush(session_, flush_context, instances):
            if session_.info.get('_audit_logging_disabled'):
                return

            usuario_id, usuario_nome = _get_actor()
            endpoint, metodo, ip, ua = _get_request_meta()

            def _add_log(acao, obj, changes):
                if isinstance(obj, AuditLog):
                    return

                entidade_tipo = obj.__class__.__name__
                entidade_id = _row_identity(obj)
                mudancas_json = None
                if changes is not None:
                    try:
                        mudancas_json = json.dumps(changes, ensure_ascii=False, default=str)
                    except Exception:
                        mudancas_json = None

                session_.add(
                    AuditLog(
                        usuario_id=usuario_id,
                        usuario_nome=usuario_nome,
                        acao=acao,
                        entidade_tipo=entidade_tipo,
                        entidade_id=entidade_id,
                        mudancas_json=mudancas_json,
                        endpoint=endpoint,
                        metodo=metodo,
                        ip=ip,
                        user_agent=ua,
                    )
                )

            for obj in list(session_.new):
                if isinstance(obj, AuditLog):
                    continue
                changes = _collect_changes(obj, 'create')
                _add_log('create', obj, changes)

            for obj in list(session_.dirty):
                if isinstance(obj, AuditLog):
                    continue
                if not session_.is_modified(obj, include_collections=False):
                    continue
                changes = _collect_changes(obj, 'update')
                if changes:
                    _add_log('update', obj, changes)

            for obj in list(session_.deleted):
                if isinstance(obj, AuditLog):
                    continue
                changes = _collect_changes(obj, 'delete')
                _add_log('delete', obj, changes)

        _app.extensions['audit_log_registered'] = True

    _register_audit_logging(app)
    
    if not skip_db_checks:
        with app.app_context():
            db.create_all()
            db_type = 'PostgreSQL (Supabase)' if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql://') else 'SQLite'
            app.logger.info("Tabelas %s criadas/verificadas com sucesso.", db_type)
            
            # Executar migração para adicionar numero_pedido_cliente
            try:
                from migrations.add_numero_pedido_cliente import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração numero_pedido_cliente: {str(e)}")

            # Executar migração para adicionar categoria_trabalho em gabarito_centro_usinagem
            try:
                from migrations.add_categoria_trabalho_gabarito_centro import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração categoria_trabalho (gabarito_centro_usinagem): {str(e)}")

            # Executar migração para adicionar bt/ar em folha_processo_torno_cnc
            try:
                from migrations.add_bt_ar_folha_torno_cnc import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração bt/ar (folha_processo_torno_cnc): {str(e)}")

            # Executar migração para adicionar campos suporte_bt/comprimento_fora em ferramentas
            try:
                from migrations.add_campos_ferramenta_suporte_comprimento import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração suporte_bt/comprimento_fora (ferramentas): {str(e)}")
            
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
    from routes.auditoria import auditoria
    
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
    app.register_blueprint(auditoria)

    # Guard global de autenticação/autorização
    @app.before_request
    def _global_auth_guard():
        # Permitir preflight CORS/OPTIONS sem login
        if request.method == 'OPTIONS':
            return

        endpoint = request.endpoint or ''
        blueprint = request.blueprint

        # Endpoints públicos
        if endpoint.startswith('static'):
            return
        if endpoint in ('auth.login', 'auth.logout'):
            return
        if endpoint.startswith('arquivos.uploaded_'):
            return
        if endpoint == 'supabase_redirect':
            return

        # Qualquer outra rota exige usuário logado
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        # Carregar usuário e validar sessão
        from models import Usuario
        usuario = Usuario.query.get(session.get('usuario_id'))
        if not usuario:
            session.clear()
            flash('Sessão inválida. Faça login novamente.', 'warning')
            return redirect(url_for('auth.login'))

        g.usuario = usuario

        # Admin possui acesso total
        if usuario.nivel_acesso == 'admin':
            return

        # Blueprints que já têm verificação interna (evitar duplicar regras finas)
        if blueprint in ('kanban', 'estoque', 'folhas_processo', 'backup', 'auth'):
            return

        # Permissões por módulo
        if blueprint in ('pedidos', 'ordens', 'pedidos_material', 'clientes'):
            if not usuario.acesso_pedidos:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

        if blueprint in ('apontamento',):
            if not usuario.acesso_kanban:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

        if blueprint in (
            'itens',
            'materiais',
            'trabalhos',
            'maquinas',
            'castanhas',
            'gabaritos_centro',
            'gabaritos_rosca',
            'novas_folhas_processo',
        ):
            if not usuario.acesso_cadastros:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

        if blueprint in ('estoque_pecas',):
            if not usuario.acesso_estoque:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

    @app.context_processor
    def _inject_audit_footer():
        try:
            usuario = getattr(g, 'usuario', None)
            if not usuario or getattr(usuario, 'nivel_acesso', None) != 'admin':
                return {}

            if not has_request_context():
                return {}

            from models import AuditLog

            blueprint = request.blueprint
            view_args = request.view_args or {}

            blueprint_to_entity = {
                'itens': 'Item',
                'pedidos': 'Pedido',
                'ordens': 'OrdemServico',
                'novas_folhas_processo': 'NovaFolhaProcesso',
                'clientes': 'Cliente',
                'materiais': 'Material',
                'trabalhos': 'Trabalho',
                'pedidos_material': 'PedidoMaterial',
                'estoque': 'Estoque',
                'estoque_pecas': 'EstoquePeca',
                'kanban': 'OrdemServico',
                'apontamento': 'OrdemServico',
            }

            entity_type = blueprint_to_entity.get(blueprint)
            entity_id = None

            viewarg_to_entity = {
                'item_id': 'Item',
                'pedido_id': 'Pedido',
                'ordem_id': 'OrdemServico',
                'ordem_servico_id': 'OrdemServico',
                'os_id': 'OrdemServico',
                'folha_id': 'NovaFolhaProcesso',
                'cliente_id': 'Cliente',
                'material_id': 'Material',
                'trabalho_id': 'Trabalho',
                'pedido_material_id': 'PedidoMaterial',
                'id': None,
            }

            for arg_name, et in viewarg_to_entity.items():
                if arg_name in view_args and view_args.get(arg_name) is not None:
                    val = view_args.get(arg_name)
                    if et:
                        entity_type = et
                    entity_id = str(val)
                    break

            q = AuditLog.query
            if entity_type and entity_id:
                q = q.filter(AuditLog.entidade_tipo == entity_type, AuditLog.entidade_id == entity_id)
                titulo = f"Últimas mudanças: {entity_type} #{entity_id}"
            elif entity_type:
                q = q.filter(AuditLog.entidade_tipo == entity_type)
                titulo = f"Últimas mudanças: {entity_type}"
            else:
                titulo = "Últimas mudanças (Sistema)"

            logs = q.order_by(AuditLog.data_criacao.desc()).limit(8).all()
            return {
                'audit_footer_logs': logs,
                'audit_footer_title': titulo,
            }
        except Exception:
            return {}
    
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
