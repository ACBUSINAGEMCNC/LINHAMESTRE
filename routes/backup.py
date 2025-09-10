from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from models import db, Backup, Usuario
from routes.auth import login_required, permissao_requerida
from datetime import datetime, date, time
import os
import subprocess
import shutil
import tempfile
import zipfile
import glob
import logging
from sqlalchemy import create_engine, text
import psycopg2
from urllib.parse import urlparse

backup = Blueprint('backup', __name__)
logger = logging.getLogger(__name__)

# Configurar logging mais detalhado para o módulo de backup
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def _detect_database_type():
    """Detecta o tipo de banco de dados sendo usado."""
    db_url = str(db.engine.url)
    if db_url.startswith('sqlite'):
        return 'sqlite'
    elif db_url.startswith('postgresql'):
        return 'postgresql'
    else:
        return 'unknown'


def _get_db_connection_info():
    """Retorna informações de conexão do banco de dados."""
    # Usar DATABASE_URL diretamente do ambiente se disponível
    import os
    env_database_url = os.getenv('DATABASE_URL')
    
    if env_database_url:
        # Usar URL do ambiente (.env) que sabemos que funciona
        db_url = env_database_url
    else:
        # Fallback para URL do SQLAlchemy
        db_url = str(db.engine.url)
    
    if db_url.startswith('sqlite'):
        return {'type': 'sqlite', 'path': db.engine.url.database}
    elif db_url.startswith('postgresql'):
        parsed = urlparse(db_url)
        return {
            'type': 'postgresql',
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'username': parsed.username,
            'password': parsed.password
        }
    else:
        raise ValueError(f"Tipo de banco não suportado: {db_url}")


def _criar_zip(arquivo_destino: str, db_path: str):
    """Gera um ZIP contendo o banco de dados e a pasta uploads."""
    try:
        # Verificar se o diretório de backup existe
        backup_dir = os.path.dirname(arquivo_destino)
        if not os.path.exists(backup_dir):
            logger.info(f"Criando diretório de backup: {backup_dir}")
            os.makedirs(backup_dir, exist_ok=True)
            
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"Diretório temporário criado: {tmpdir}")
            
            # Banco
            tmp_db = os.path.join(tmpdir, os.path.basename(db_path))
            logger.info(f"Copiando banco de dados: {db_path} -> {tmp_db}")
            shutil.copy2(db_path, tmp_db)
            
            # Uploads
            if os.path.exists(UPLOADS_DIR):
                uploads_tmp = os.path.join(tmpdir, 'uploads')
                logger.info(f"Copiando uploads: {UPLOADS_DIR} -> {uploads_tmp}")
                shutil.copytree(UPLOADS_DIR, uploads_tmp)
            else:
                logger.warning(f"Diretório de uploads não encontrado: {UPLOADS_DIR}")
                # Criar diretório vazio para uploads para manter a estrutura
                os.makedirs(os.path.join(tmpdir, 'uploads'), exist_ok=True)
                
            # Compacta
            logger.info(f"Criando arquivo ZIP: {arquivo_destino}")
            with zipfile.ZipFile(arquivo_destino, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(tmpdir):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel_path = os.path.relpath(abs_path, tmpdir)
                        zipf.write(abs_path, rel_path)
                        logger.debug(f"Adicionado ao ZIP: {rel_path}")
    except Exception as e:
        logger.error(f"Erro ao criar ZIP: {str(e)}")
        # Em ambiente serverless, tentar usar o diretório /tmp diretamente
        if not os.access(os.path.dirname(arquivo_destino), os.W_OK):
            logger.info("Tentando usar /tmp diretamente para o backup")
            novo_destino = os.path.join('/tmp', os.path.basename(arquivo_destino))
            logger.info(f"Novo destino: {novo_destino}")
            return _criar_zip(novo_destino, db_path)
        raise


def _criar_backup_sqlite(caminho_arquivo, db_path):
    """Cria um backup do banco de dados SQLite e da pasta uploads."""
    logger.info(f"Criando backup SQLite: {db_path} -> {caminho_arquivo}")
    logger.info(f"UPLOADS_DIR para backup: {UPLOADS_DIR}, existe: {os.path.exists(UPLOADS_DIR)}")
    _criar_zip(caminho_arquivo, db_path)


def _criar_backup_supabase_alternativo(arquivo_destino: str, conn_info: dict):
    """Backup alternativo para Supabase usando SQL queries diretas."""
    try:
        # Verificar se as credenciais estão disponíveis
        if not all([conn_info.get('username'), conn_info.get('password'), conn_info.get('host')]):
            raise Exception("Credenciais do Supabase não configuradas. Configure DATABASE_URL no arquivo .env com as credenciais corretas.")
        
        # Conectar ao banco Supabase
        connection_string = f"postgresql://{conn_info['username']}:{conn_info['password']}@{conn_info['host']}:{conn_info['port']}/{conn_info['database']}"
        engine = create_engine(connection_string)

        with tempfile.TemporaryDirectory() as tmpdir:
            sql_file = os.path.join(tmpdir, 'backup_supabase.sql')

            with engine.connect() as conn:
                # Obter lista de tabelas
                result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
                tables = [row[0] for row in result.fetchall()]

                with open(sql_file, 'w', encoding='utf-8') as f:
                    f.write("-- Backup Supabase - Gerado automaticamente\n")
                    f.write(f"-- Data: {datetime.now()}\n\n")

                    for table in tables:
                        # Dump da estrutura da tabela
                        result = conn.execute(text(f"SELECT * FROM {table} LIMIT 0"))
                        columns = result.keys()

                        f.write(f"-- Tabela: {table}\n")
                        f.write(f"CREATE TABLE IF NOT EXISTS {table} (\n")
                        f.write(",\n".join([f"  {col} TEXT" for col in columns]))
                        f.write("\n);\n\n")

                        # Dump dos dados
                        result = conn.execute(text(f"SELECT * FROM {table}"))
                        rows = result.fetchall()

                        if rows:
                            for row in rows:
                                values = []
                                for value in row:
                                    if value is None:
                                        values.append('NULL')
                                    elif isinstance(value, str):
                                        # Escapar aspas simples
                                        values.append(f"'{value.replace("'", "''")}'")
                                    elif isinstance(value, (datetime, date, time)):
                                        # Normalizar datas/horas para string e citar
                                        if isinstance(value, datetime):
                                            formatted = value.strftime('%Y-%m-%d %H:%M:%S.%f')
                                        else:
                                            formatted = value.isoformat()
                                        values.append(f"'{formatted}'")
                                    elif isinstance(value, bool):
                                        values.append('TRUE' if value else 'FALSE')
                                    else:
                                        # Números e outros tipos
                                        values.append(str(value))
                                f.write(f"INSERT INTO {table} VALUES ({', '.join(values)});\n")
                        f.write("\n")

            # Backup dos arquivos do Supabase Storage
            try:
                _backup_supabase_storage(tmpdir)
            except Exception as storage_error:
                # Se falhar o backup do storage, continuar com o backup do banco
                logger.warning(f"Falha no backup do Supabase Storage: {storage_error}")
                with open(os.path.join(tmpdir, 'storage_error.txt'), 'w') as f:
                    f.write(f"Erro no backup do Supabase Storage: {storage_error}\n")
                    f.write("Apenas dados do banco foram salvos.\n")

            # Uploads locais (fallback)
            if os.path.exists(UPLOADS_DIR):
                shutil.copytree(UPLOADS_DIR, os.path.join(tmpdir, 'uploads_local'))

            # README explicativo
            readme_file = os.path.join(tmpdir, 'README.md')
            with open(readme_file, 'w', encoding='utf-8') as f:
                f.write("# Backup Supabase\n\n")
                f.write("Este backup foi criado usando queries SQL diretas ao invés de pg_dump.\n")
                f.write("Para restaurar, execute o arquivo backup_supabase.sql no seu banco PostgreSQL.\n\n")
                f.write("## Conteúdo do Backup:\n")
                f.write("- backup_supabase.sql: Dados das tabelas\n")
                f.write("- supabase_storage/: Arquivos do Supabase Storage\n")
                f.write("- uploads_local/: Arquivos locais (se existirem)\n\n")
                f.write(f"Data do backup: {datetime.now()}\n")

            # Compactar
            with zipfile.ZipFile(arquivo_destino, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(tmpdir):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel_path = os.path.relpath(abs_path, tmpdir)
                        zipf.write(abs_path, rel_path)

    except Exception as e:
        error_msg = str(e)
        if "Wrong password" in error_msg or "authentication failed" in error_msg:
            raise Exception(f"Erro de autenticação Supabase: Verifique se a senha no DATABASE_URL está correta. Detalhes: {error_msg}")
        elif "connection" in error_msg.lower():
            raise Exception(f"Erro de conexão Supabase: Verifique se o DATABASE_URL está correto e se o servidor está acessível. Detalhes: {error_msg}")
        else:
            raise Exception(f"Erro no backup alternativo Supabase: {error_msg}")


def _backup_supabase_storage(tmpdir: str):
    """Faz backup dos arquivos do Supabase Storage."""
    import requests
    import os
    from models import db
    from sqlalchemy import text
    
    # Obter configurações do Supabase
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
    
    if not all([supabase_url, supabase_key]):
        raise Exception("Configuração do Supabase Storage não encontrada")
    
    # Remover barra final da URL
    if supabase_url.endswith('/'):
        supabase_url = supabase_url[:-1]
    
    # Criar diretório para arquivos do storage
    storage_dir = os.path.join(tmpdir, 'supabase_storage')
    os.makedirs(storage_dir, exist_ok=True)
    
    # Headers para autenticação
    headers = {
        'Authorization': f'Bearer {supabase_key}',
        'apikey': supabase_key
    }
    
    try:
        # Listar todos os arquivos no bucket
        list_url = f"{supabase_url}/storage/v1/object/list/{bucket}"
        response = requests.post(list_url, headers=headers, json={})
        
        if response.status_code != 200:
            raise Exception(f"Erro ao listar arquivos: {response.status_code} - {response.text}")
        
        files = response.json()
        downloaded_count = 0
        
        for file_info in files:
            if file_info.get('name'):
                file_path = file_info['name']
                
                # URL para download do arquivo
                download_url = f"{supabase_url}/storage/v1/object/{bucket}/{file_path}"
                
                try:
                    # Fazer download do arquivo
                    file_response = requests.get(download_url, headers=headers)
                    
                    if file_response.status_code == 200:
                        # Criar estrutura de diretórios se necessário
                        local_file_path = os.path.join(storage_dir, file_path)
                        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                        
                        # Salvar arquivo
                        with open(local_file_path, 'wb') as f:
                            f.write(file_response.content)
                        
                        downloaded_count += 1
                        logger.debug(f"Arquivo baixado: {file_path}")
                    else:
                        logger.warning(f"Erro ao baixar {file_path}: {file_response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"Erro ao processar arquivo {file_path}: {e}")
        
        # Criar arquivo de log do backup
        with open(os.path.join(storage_dir, 'backup_info.txt'), 'w') as f:
            f.write(f"Backup do Supabase Storage\n")
            f.write(f"Data: {datetime.now()}\n")
            f.write(f"Bucket: {bucket}\n")
            f.write(f"Arquivos baixados: {downloaded_count}\n")
            f.write(f"Total de arquivos listados: {len(files)}\n")
        
        logger.info(f"Backup do Supabase Storage concluído: {downloaded_count} arquivos")
        
    except Exception as e:
        raise Exception(f"Erro no backup do Supabase Storage: {str(e)}")


def _restaurar_supabase_storage(tmpdir: str):
    """Restaura arquivos do Supabase Storage a partir do backup."""
    import requests
    import os
    
    storage_dir = os.path.join(tmpdir, 'supabase_storage')
    
    if not os.path.exists(storage_dir):
        logger.info("Nenhum backup do Supabase Storage encontrado")
        return
    
    # Obter configurações do Supabase
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
    
    if not all([supabase_url, supabase_key]):
        logger.warning("Configuração do Supabase Storage não encontrada para restauração")
        return
    
    # Remover barra final da URL
    if supabase_url.endswith('/'):
        supabase_url = supabase_url[:-1]
    
    # Headers para autenticação
    headers = {
        'Authorization': f'Bearer {supabase_key}',
        'apikey': supabase_key
    }
    
    uploaded_count = 0
    
    # Percorrer todos os arquivos do backup
    for root, dirs, files in os.walk(storage_dir):
        for file_name in files:
            if file_name == 'backup_info.txt':
                continue
                
            local_file_path = os.path.join(root, file_name)
            # Calcular caminho relativo no storage
            rel_path = os.path.relpath(local_file_path, storage_dir)
            storage_path = rel_path.replace('\\', '/')  # Normalizar para URL
            
            try:
                # URL de upload
                upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{storage_path}"
                
                # Ler arquivo
                with open(local_file_path, 'rb') as f:
                    file_content = f.read()
                
                # Fazer upload
                files_data = {
                    'file': (file_name, file_content, 'application/octet-stream')
                }
                
                response = requests.post(upload_url, headers=headers, files=files_data)
                
                if response.status_code in [200, 201]:
                    uploaded_count += 1
                    logger.debug(f"Arquivo restaurado: {storage_path}")
                else:
                    logger.warning(f"Erro ao restaurar {storage_path}: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.warning(f"Erro ao processar arquivo {storage_path}: {e}")
    
    logger.info(f"Restauração do Supabase Storage concluída: {uploaded_count} arquivos")


def _criar_backup_postgresql(arquivo_destino: str, conn_info: dict):
    """Cria backup do PostgreSQL usando pg_dump ou método alternativo."""
    try:
        # Primeiro tentar pg_dump
        _criar_backup_postgresql_pg_dump(arquivo_destino, conn_info)
    except Exception as e:
        if "pg_dump" in str(e) and ("not found" in str(e) or "não encontrado" in str(e)):
            # Fallback para método alternativo
            print("pg_dump não encontrado, usando método alternativo...")
            _criar_backup_supabase_alternativo(arquivo_destino, conn_info)
        else:
            raise


def _criar_backup_postgresql_pg_dump(arquivo_destino: str, conn_info: dict):
    """Cria backup do PostgreSQL usando pg_dump."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Arquivo SQL do backup
        sql_file = os.path.join(tmpdir, 'backup.sql')

        # Comando pg_dump
        cmd = [
            'pg_dump',
            f"--host={conn_info['host']}",
            f"--port={conn_info['port']}",
            f"--username={conn_info['username']}",
            f"--dbname={conn_info['database']}",
            f"--file={sql_file}",
            "--format=custom",
            "--compress=9",
            "--no-owner",
            "--no-privileges"
        ]

        # Configurar senha via variável de ambiente
        env = os.environ.copy()
        env['PGPASSWORD'] = conn_info['password']

        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                # Se pg_dump não estiver disponível, tentar abordagem alternativa
                if "pg_dump" in result.stderr and ("not found" in result.stderr or "não encontrado" in result.stderr):
                    raise Exception("pg_dump não encontrado. Para Supabase, considere usar o painel de administração do Supabase para backups, ou instalar PostgreSQL client tools.")
                raise Exception(f"pg_dump falhou: {result.stderr}")

            # Uploads locais (usar uploads_local para casar com a restauração)
            if os.path.exists(UPLOADS_DIR):
                shutil.copytree(UPLOADS_DIR, os.path.join(tmpdir, 'uploads_local'))

            # Incluir arquivos do Supabase Storage no pacote de backup (best effort)
            try:
                _backup_supabase_storage(tmpdir)
            except Exception as storage_error:
                logger.warning(f"Falha no backup do Supabase Storage (pg_dump path): {storage_error}")
                # Registrar aviso no pacote
                with open(os.path.join(tmpdir, 'storage_error.txt'), 'w', encoding='utf-8') as f:
                    f.write(f"Erro no backup do Supabase Storage: {storage_error}\n")
                    f.write("Apenas dados do banco foram salvos para o storage.\n")

            # Adicionar README com instruções
            readme_file = os.path.join(tmpdir, 'README.md')
            try:
                with open(readme_file, 'w', encoding='utf-8') as f:
                    f.write("# Backup PostgreSQL (pg_dump)\n\n")
                    f.write("Este backup foi criado com pg_dump.\n\n")
                    f.write("## Conteúdo:\n")
                    f.write("- backup.sql: Dump do banco via pg_dump (formato custom em arquivo)\n")
                    f.write("- supabase_storage/: Arquivos do Supabase Storage (se configurado)\n")
                    f.write("- uploads_local/: Uploads locais (se existirem)\n")
            except Exception:
                pass

            # Compacta tudo em ZIP
            with zipfile.ZipFile(arquivo_destino, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(tmpdir):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel_path = os.path.relpath(abs_path, tmpdir)
                        zipf.write(abs_path, rel_path)

        except subprocess.TimeoutExpired:
            raise Exception("Timeout ao criar backup do PostgreSQL")
        except FileNotFoundError:
            raise Exception("pg_dump não encontrado. Para Supabase, considere usar o painel de administração do Supabase para backups, ou instalar PostgreSQL client tools.")
        except Exception as e:
            # Para Supabase, sugerir alternativa
            if "pg_dump" in str(e):
                raise Exception("Para backups Supabase, use o painel de administração do Supabase. Backups locais requerem instalação do PostgreSQL client tools.")
            raise


def _restaurar_backup_postgresql(caminho_backup: str, conn_info: dict):
    """Restaura backup do PostgreSQL usando pg_restore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extrai o backup
        with zipfile.ZipFile(caminho_backup, 'r') as zipf:
            zipf.extractall(tmpdir)

        # Procurar por diferentes tipos de arquivo SQL
        sql_file = None
        possible_files = ['backup.sql', 'backup_supabase.sql']
        
        for filename in possible_files:
            test_path = os.path.join(tmpdir, filename)
            if os.path.exists(test_path):
                sql_file = test_path
                break
        
        if not sql_file:
            # Listar arquivos disponíveis para debug
            available_files = []
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    available_files.append(os.path.relpath(os.path.join(root, file), tmpdir))
            
            raise Exception(f"Arquivo de backup PostgreSQL não encontrado no ZIP. Arquivos disponíveis: {', '.join(available_files)}")

        # Verificar se é arquivo SQL do Supabase (texto) ou backup binário do pg_dump
        if sql_file.endswith('backup_supabase.sql'):
            # Para backups SQL do Supabase, usar psql ao invés de pg_restore
            cmd = [
                'psql',
                f"--host={conn_info['host']}",
                f"--port={conn_info['port']}",
                f"--username={conn_info['username']}",
                f"--dbname={conn_info['database']}",
                f"--file={sql_file}"
            ]
        else:
            # Para backups binários do pg_dump, usar pg_restore
            cmd = [
                'pg_restore',
                f"--host={conn_info['host']}",
                f"--port={conn_info['port']}",
                f"--username={conn_info['username']}",
                f"--dbname={conn_info['database']}",
                sql_file,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges"
            ]

        # Configurar senha via variável de ambiente
        env = os.environ.copy()
        env['PGPASSWORD'] = conn_info['password']

        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise Exception(f"Comando falhou: {result.stderr}")

            # Restaurar arquivos do Supabase Storage
            try:
                _restaurar_supabase_storage(tmpdir)
            except Exception as storage_error:
                logger.warning(f"Erro ao restaurar Supabase Storage: {storage_error}")

            # Restaurar uploads locais se existirem
            uploads_local_dir = os.path.join(tmpdir, 'uploads_local')
            if os.path.exists(uploads_local_dir):
                if os.path.exists(UPLOADS_DIR):
                    shutil.rmtree(UPLOADS_DIR)
                shutil.copytree(uploads_local_dir, UPLOADS_DIR)
                print(f"Uploads locais restaurados para {UPLOADS_DIR}")

            return "Backup PostgreSQL restaurado com sucesso!"
        except subprocess.TimeoutExpired:
            raise Exception("Timeout ao restaurar backup do PostgreSQL")
        except FileNotFoundError:
            # Fallback: restauração manual usando SQLAlchemy
            return _restaurar_backup_supabase_manual(sql_file, conn_info)


def _restaurar_backup_supabase_manual(sql_file: str, conn_info: dict):
    """Restaura backup do Supabase usando SQLAlchemy (sem dependência de ferramentas PostgreSQL)."""
    try:
        from sqlalchemy import create_engine, text
        
        # Criar conexão usando SQLAlchemy
        connection_string = f"postgresql://{conn_info['username']}:{conn_info['password']}@{conn_info['host']}:{conn_info['port']}/{conn_info['database']}"
        engine = create_engine(connection_string)
        
        # Ler e executar o arquivo SQL
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Dividir em comandos individuais e executar
        with engine.connect() as conn:
            # Executar em transação
            trans = conn.begin()
            try:
                # Dividir por linhas e filtrar comandos válidos
                commands = []
                current_command = ""
                
                for line in sql_content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('--'):
                        current_command += line + " "
                        if line.endswith(';'):
                            commands.append(current_command.strip())
                            current_command = ""
                
                # Executar comandos
                for command in commands:
                    if command and not command.startswith('--'):
                        try:
                            conn.execute(text(command))
                        except Exception as cmd_error:
                            # Ignorar erros de comandos específicos (ex: CREATE TABLE IF NOT EXISTS)
                            if "already exists" not in str(cmd_error).lower():
                                print(f"Aviso ao executar comando: {cmd_error}")
                
                trans.commit()
                
            except Exception as e:
                trans.rollback()
                raise Exception(f"Erro na restauração manual: {str(e)}")
                
    except Exception as e:
        raise Exception(f"Erro na restauração manual do Supabase: {str(e)}")


def _restaurar_backup_sqlite(caminho_backup: str, db_path: str):
    """Restaura backup do SQLite (método original)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extrai zip
        with zipfile.ZipFile(caminho_backup, 'r') as zipf:
            zipf.extractall(tmpdir)
        # Restaura DB
        extracted_db = os.path.join(tmpdir, os.path.basename(db_path))
        shutil.copy2(extracted_db, db_path)
        # Restaura uploads
        extracted_uploads = os.path.join(tmpdir, 'uploads')
        if os.path.exists(extracted_uploads):
            # Copiar conteúdo, preservando estrutura
            if os.path.exists(UPLOADS_DIR):
                shutil.rmtree(UPLOADS_DIR)
            shutil.copytree(extracted_uploads, UPLOADS_DIR)


# Configurações de diretórios
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Verificar se podemos escrever no BASE_DIR, senão usar /tmp (para serverless como Vercel)
if os.access(BASE_DIR, os.W_OK):
    BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
    UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
else:
    # Ambiente serverless, usar /tmp
    BACKUP_DIR = '/tmp/backups'
    UPLOADS_DIR = '/tmp/uploads'  # Também usar /tmp para uploads em ambiente serverless

try:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
except (PermissionError, OSError):
    pass  # Ignorar erros de permissão ou sistema de arquivos somente leitura

@backup.route('/backups')
@login_required
@permissao_requerida('admin')
def listar_backups():
    """Rota para listar todos os backups disponíveis"""
    backups = Backup.query.order_by(Backup.data_criacao.desc()).all()
    return render_template('backup/listar.html', backups=backups)

@backup.route('/backups/criar', methods=['POST'])
@login_required
@permissao_requerida('admin')
def criar_backup():
    """Rota para criar um novo backup do banco de dados"""
    descricao = request.form.get('descricao', '')
    
    # Log do ambiente
    logger.info(f"Iniciando backup. BASE_DIR: {BASE_DIR}")
    logger.info(f"BACKUP_DIR: {BACKUP_DIR}, existe: {os.path.exists(BACKUP_DIR)}, permissão escrita: {os.access(BACKUP_DIR, os.W_OK) if os.path.exists(BACKUP_DIR) else 'N/A'}")
    logger.info(f"UPLOADS_DIR: {UPLOADS_DIR}, existe: {os.path.exists(UPLOADS_DIR)}")
    logger.info(f"Ambiente: {'Serverless' if not os.access(BASE_DIR, os.W_OK) else 'Local'}")

    # Gerar nome do arquivo de backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_arquivo = f"backup_{timestamp}.zip"
    caminho_arquivo = os.path.join(BACKUP_DIR, nome_arquivo)
    logger.info(f"Caminho do arquivo de backup: {caminho_arquivo}")

    try:
        # Detectar tipo de banco de dados
        db_type = _detect_database_type()
        logger.info(f"Tipo de banco de dados detectado: {db_type}")

        if db_type == 'postgresql':
            # Backup PostgreSQL
            conn_info = _get_db_connection_info()
            
            # Verificar se estamos usando Supabase
            if 'supabase.com' in conn_info.get('host', ''):
                # Para Supabase, adicionar informações de configuração
                database_url = os.getenv('DATABASE_URL', '')
                if not database_url or 'postgresql://' not in database_url:
                    raise Exception("DATABASE_URL não configurado. Para usar Supabase, configure DATABASE_URL no arquivo .env com: postgresql://postgres.[SEU-PROJETO]:[SUA-SENHA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres")
            
            _criar_backup_postgresql(caminho_arquivo, conn_info)
        elif db_type == 'sqlite':
            # Backup SQLite (método original)
            db_path = db.engine.url.database
            if not db_path.startswith('/'):
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
            _criar_backup_sqlite(caminho_arquivo, db_path)
        else:
            raise Exception(f"Tipo de banco de dados não suportado: {db_type}")

        # Verificar se o arquivo foi criado
        if not os.path.exists(caminho_arquivo):
            raise Exception(f"Arquivo de backup não foi criado em {caminho_arquivo}")
            
        # Listar conteúdo do arquivo ZIP para debug
        logger.info(f"Verificando conteúdo do arquivo ZIP {caminho_arquivo}")
        try:
            with zipfile.ZipFile(caminho_arquivo, 'r') as zipf:
                file_list = zipf.namelist()
                logger.info(f"Arquivos no ZIP: {', '.join(file_list)}")
                # Verificar se uploads estão incluídos
                uploads_included = any(name.startswith('uploads/') for name in file_list)
                logger.info(f"Uploads incluídos no backup: {uploads_included}")
        except Exception as zip_error:
            logger.error(f"Erro ao verificar conteúdo do ZIP: {zip_error}")
            
        # Registrar backup no banco de dados
        tamanho = os.path.getsize(caminho_arquivo)
        logger.info(f"Tamanho do arquivo de backup: {tamanho} bytes")
        novo_backup = Backup(
            nome_arquivo=nome_arquivo,
            data_criacao=datetime.now(),
            tamanho=tamanho,
            usuario_id=session.get('usuario_id'),
            descricao=descricao,
            automatico=False
        )

        db.session.add(novo_backup)
        db.session.commit()
        logger.info(f"Backup registrado no banco de dados com ID {novo_backup.id}")

        flash(f'Backup criado com sucesso! Tipo de banco: {db_type.upper()}', 'success')
    except Exception as e:
        error_msg = str(e)
        if "Wrong password" in error_msg or "authentication failed" in error_msg:
            flash(f'Erro de autenticação: Verifique as credenciais do Supabase no arquivo .env. {error_msg}', 'danger')
        elif "DATABASE_URL não configurado" in error_msg:
            flash(f'Configuração necessária: {error_msg}', 'warning')
        else:
            flash(f'Erro ao criar backup: {error_msg}', 'danger')

    return redirect(url_for('backup.listar_backups'))

@backup.route('/backups/restaurar/<int:backup_id>', methods=['POST'])
@login_required
@permissao_requerida('admin')
def restaurar_backup(backup_id):
    """Rota para restaurar o banco de dados a partir de um backup"""
    backup_obj = Backup.query.get_or_404(backup_id)
    caminho_backup = os.path.join(BACKUP_DIR, backup_obj.nome_arquivo)
    
    # Verificar se o arquivo existe no caminho padrão
    if not os.path.exists(caminho_backup):
        logger.warning(f"Arquivo de backup não encontrado no caminho padrão: {caminho_backup}")
        
        # Tentar encontrar em /tmp para ambientes serverless
        caminho_tmp = os.path.join('/tmp', backup_obj.nome_arquivo)
        if os.path.exists(caminho_tmp):
            logger.info(f"Arquivo de backup encontrado em caminho alternativo: {caminho_tmp}")
            caminho_backup = caminho_tmp
        else:
            # Verificar se existe em algum lugar no diretório /tmp
            try:
                encontrado = False
                for root, _, files in os.walk('/tmp'):
                    for file in files:
                        if file == backup_obj.nome_arquivo:
                            caminho_backup = os.path.join(root, file)
                            logger.info(f"Arquivo de backup encontrado em: {caminho_backup}")
                            encontrado = True
                            break
                    if encontrado:
                        break
                        
                if not encontrado:
                    flash('Arquivo de backup não encontrado!', 'danger')
                    return redirect(url_for('backup.listar_backups'))
            except Exception as e:
                logger.error(f"Erro ao procurar backup em /tmp: {str(e)}")
                flash('Arquivo de backup não encontrado!', 'danger')
                return redirect(url_for('backup.listar_backups'))
    
    try:
        # Detectar tipo de banco de dados
        db_type = _detect_database_type()
        
        if db_type == 'postgresql':
            # Restauração PostgreSQL
            conn_info = _get_db_connection_info()
            _restaurar_backup_postgresql(caminho_backup, conn_info)
        elif db_type == 'sqlite':
            # Restauração SQLite (método original)
            db_uri = db.engine.url.database
            if db_uri.startswith('/'):
                db_path = db_uri
            else:
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_uri)
            
            _restaurar_backup_sqlite(caminho_backup, db_path)
        else:
            raise Exception(f"Tipo de banco de dados não suportado para restauração: {db_type}")
        
        flash('Backup restaurado com sucesso! Por favor, reinicie a aplicação.', 'success')
    except Exception as e:
        error_msg = str(e)
        if "pg_restore" in error_msg and ("not found" in error_msg or "não encontrado" in error_msg):
            flash('Erro: pg_restore não encontrado. Para restaurar backups PostgreSQL, instale PostgreSQL client tools.', 'danger')
        elif "backup_supabase.sql" in error_msg:
            flash('Este backup contém dados SQL do Supabase. Use o painel do Supabase ou execute o arquivo SQL manualmente para restaurar.', 'warning')
        else:
            flash(f'Erro ao restaurar backup: {error_msg}', 'danger')
    
    return redirect(url_for('backup.listar_backups'))

@backup.route('/backups/download/<int:backup_id>')
@login_required
@permissao_requerida('admin')
def download_backup(backup_id):
    """Rota para baixar um arquivo de backup"""
    backup_obj = Backup.query.get_or_404(backup_id)
    caminho_backup = os.path.join(BACKUP_DIR, backup_obj.nome_arquivo)
    
    # Verificar se o arquivo existe no caminho padrão
    if not os.path.exists(caminho_backup):
        logger.warning(f"Arquivo de backup não encontrado no caminho padrão: {caminho_backup}")
        
        # Tentar encontrar em /tmp para ambientes serverless
        caminho_tmp = os.path.join('/tmp', backup_obj.nome_arquivo)
        if os.path.exists(caminho_tmp):
            logger.info(f"Arquivo de backup encontrado em caminho alternativo: {caminho_tmp}")
            return send_file(caminho_tmp, as_attachment=True)
        
        # Verificar se existe em algum lugar no diretório /tmp
        try:
            for root, _, files in os.walk('/tmp'):
                for file in files:
                    if file == backup_obj.nome_arquivo:
                        caminho_encontrado = os.path.join(root, file)
                        logger.info(f"Arquivo de backup encontrado em: {caminho_encontrado}")
                        return send_file(caminho_encontrado, as_attachment=True)
        except Exception as e:
            logger.error(f"Erro ao procurar backup em /tmp: {str(e)}")
        
        flash('Arquivo de backup não encontrado!', 'danger')
        return redirect(url_for('backup.listar_backups'))
    
    logger.info(f"Enviando arquivo de backup: {caminho_backup}")
    return send_file(caminho_backup, as_attachment=True)

@backup.route('/backups/excluir/<int:backup_id>', methods=['POST'])
@login_required
@permissao_requerida('admin')
def excluir_backup(backup_id):
    """Rota para excluir um backup"""
    backup_obj = Backup.query.get_or_404(backup_id)
    caminho_backup = os.path.join(BACKUP_DIR, backup_obj.nome_arquivo)
    
    try:
        # Excluir arquivo físico
        if os.path.exists(caminho_backup):
            os.remove(caminho_backup)
        
        # Excluir registro do banco de dados
        db.session.delete(backup_obj)
        db.session.commit()
        
        flash('Backup excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir backup: {str(e)}', 'danger')
    
    return redirect(url_for('backup.listar_backups'))

@backup.route('/backups/importar', methods=['POST'])
@login_required
@permissao_requerida('admin')
def importar_backup():
    """Rota para importar um arquivo de backup externo"""
    if 'arquivo_backup' not in request.files:
        flash('Nenhum arquivo selecionado!', 'danger')
        return redirect(url_for('backup.listar_backups'))
    
    arquivo = request.files['arquivo_backup']
    descricao = request.form.get('descricao', 'Backup importado')
    
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado!', 'danger')
        return redirect(url_for('backup.listar_backups'))
    
    # Verificar extensão do arquivo
    if not arquivo.filename.endswith('.sqlite'):
        flash('Formato de arquivo inválido! O backup deve ser um arquivo SQLite.', 'danger')
        return redirect(url_for('backup.listar_backups'))
    
    try:
        # Gerar nome do arquivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"backup_importado_{timestamp}.sqlite"
        caminho_arquivo = os.path.join(BACKUP_DIR, nome_arquivo)
        
        # Salvar arquivo
        arquivo.save(caminho_arquivo)
        
        # Registrar backup no banco de dados
        tamanho = os.path.getsize(caminho_arquivo)
        novo_backup = Backup(
            nome_arquivo=nome_arquivo,
            data_criacao=datetime.now(),
            tamanho=tamanho,
            usuario_id=session.get('usuario_id'),
            descricao=descricao,
            automatico=False
        )
        
        db.session.add(novo_backup)
        db.session.commit()
        
        flash('Backup importado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao importar backup: {str(e)}', 'danger')
    
    return redirect(url_for('backup.listar_backups'))

@backup.route('/backups/exportar-drive', methods=['POST'])
@login_required
@permissao_requerida('admin')
def exportar_para_drive():
    """Rota para exportar backup para serviços de nuvem (simulado)"""
    backup_id = request.form.get('backup_id')
    servico = request.form.get('servico', 'drive')
    
    if not backup_id:
        flash('Backup não especificado!', 'danger')
        return redirect(url_for('backup.listar_backups'))
    
    backup_obj = Backup.query.get_or_404(backup_id)
    
    # Simulação de exportação para serviços de nuvem
    flash(f'Backup "{backup_obj.nome_arquivo}" exportado com sucesso para {servico.upper()}!', 'success')
    flash('Nota: Esta é uma simulação. Para implementação real, seria necessário configurar as APIs dos serviços de nuvem.', 'info')
    
    return redirect(url_for('backup.listar_backups'))

def criar_backup_automatico():
    """Função para criar backup automático (chamada por agendador)"""
    try:
        # Gerar nome do arquivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"backup_auto_{timestamp}.zip"
        caminho_arquivo = os.path.join(BACKUP_DIR, nome_arquivo)
        
        # Obter caminho do banco de dados atual
        db_uri = db.engine.url.database
        if db_uri.startswith('/'):
            db_path = db_uri
        else:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_uri)
        
        # Criar arquivo ZIP contendo banco de dados e uploads
        _criar_zip(caminho_arquivo, db_path)
        
        # Registrar backup no banco de dados
        tamanho = os.path.getsize(caminho_arquivo)
        novo_backup = Backup(
            nome_arquivo=nome_arquivo,
            data_criacao=datetime.now(),
            tamanho=tamanho,
            descricao='Backup automático',
            automatico=True
        )
        
        db.session.add(novo_backup)
        db.session.commit()
        
        # Limpar backups automáticos antigos (manter apenas os 5 mais recentes)
        backups_automaticos = Backup.query.filter_by(automatico=True).order_by(Backup.data_criacao.desc()).all()
        if len(backups_automaticos) > 5:
            for backup_antigo in backups_automaticos[5:]:
                caminho_backup = os.path.join(BACKUP_DIR, backup_antigo.nome_arquivo)
                if os.path.exists(caminho_backup):
                    os.remove(caminho_backup)
                db.session.delete(backup_antigo)
            
            db.session.commit()
        
        return True
    except Exception as e:
        logger.exception("Erro ao criar backup automático")
        return False
