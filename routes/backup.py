from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from models import db, Backup, Usuario
from routes.auth import login_required, permissao_requerida
from datetime import datetime
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
    with tempfile.TemporaryDirectory() as tmpdir:
        # Banco
        tmp_db = os.path.join(tmpdir, os.path.basename(db_path))
        shutil.copy2(db_path, tmp_db)
        # Uploads
        if os.path.exists(UPLOADS_DIR):
            shutil.copytree(UPLOADS_DIR, os.path.join(tmpdir, 'uploads'))
                # Compacta
        with zipfile.ZipFile(arquivo_destino, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    abs_path = os.path.join(root, f)
                    rel_path = os.path.relpath(abs_path, tmpdir)
                    zipf.write(abs_path, rel_path)


def _criar_backup_supabase_alternativo(arquivo_destino: str, conn_info: dict):
    """Backup alternativo para Supabase usando SQL queries diretas."""
    try:
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
                                        values.append(f"'{value.replace(chr(39), chr(39)+chr(39))}'")
                                    else:
                                        values.append(str(value))
                                f.write(f"INSERT INTO {table} VALUES ({', '.join(values)});\n")
                        f.write("\n")

            # Uploads
            if os.path.exists(UPLOADS_DIR):
                shutil.copytree(UPLOADS_DIR, os.path.join(tmpdir, 'uploads'))

            # README explicativo
            readme_file = os.path.join(tmpdir, 'README.md')
            with open(readme_file, 'w', encoding='utf-8') as f:
                f.write("# Backup Supabase\n\n")
                f.write("Este backup foi criado usando queries SQL diretas ao invés de pg_dump.\n")
                f.write("Para restaurar, execute o arquivo backup_supabase.sql no seu banco PostgreSQL.\n\n")
                f.write(f"Data do backup: {datetime.now()}\n")

            # Compactar
            with zipfile.ZipFile(arquivo_destino, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(tmpdir):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel_path = os.path.relpath(abs_path, tmpdir)
                        zipf.write(abs_path, rel_path)

    except Exception as e:
        raise Exception(f"Erro no backup alternativo Supabase: {str(e)}")


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

            # Uploads
            if os.path.exists(UPLOADS_DIR):
                shutil.copytree(UPLOADS_DIR, os.path.join(tmpdir, 'uploads'))

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

        sql_file = os.path.join(tmpdir, 'backup.sql')

        if not os.path.exists(sql_file):
            raise Exception("Arquivo de backup PostgreSQL não encontrado no ZIP")

        # Comando pg_restore
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
                raise Exception(f"pg_restore falhou: {result.stderr}")

            # Restaura uploads se existirem
            extracted_uploads = os.path.join(tmpdir, 'uploads')
            if os.path.exists(extracted_uploads):
                if os.path.exists(UPLOADS_DIR):
                    shutil.rmtree(UPLOADS_DIR)
                shutil.copytree(extracted_uploads, UPLOADS_DIR)

        except subprocess.TimeoutExpired:
            raise Exception("Timeout ao restaurar backup do PostgreSQL")
        except FileNotFoundError:
            raise Exception("pg_restore não encontrado. Certifique-se que PostgreSQL está instalado.")


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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
try:
    os.makedirs(BACKUP_DIR, exist_ok=True)
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

    # Gerar nome do arquivo de backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_arquivo = f"backup_{timestamp}.zip"
    caminho_arquivo = os.path.join(BACKUP_DIR, nome_arquivo)

    try:
        # Detectar tipo de banco de dados
        db_type = _detect_database_type()

        if db_type == 'postgresql':
            # Backup PostgreSQL
            conn_info = _get_db_connection_info()
            _criar_backup_postgresql(caminho_arquivo, conn_info)
        elif db_type == 'sqlite':
            # Backup SQLite (método original)
            db_path = db.engine.url.database
            if not db_path.startswith('/'):
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
            _criar_backup_sqlite(caminho_arquivo, db_path)
        else:
            raise Exception(f"Tipo de banco de dados não suportado: {db_type}")

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

        flash(f'Backup criado com sucesso! Tipo de banco: {db_type.upper()}', 'success')
    except Exception as e:
        flash(f'Erro ao criar backup: {str(e)}', 'danger')

    return redirect(url_for('backup.listar_backups'))

@backup.route('/backups/restaurar/<int:backup_id>', methods=['POST'])
@login_required
@permissao_requerida('admin')
def restaurar_backup(backup_id):
    """Rota para restaurar o banco de dados a partir de um backup"""
    backup_obj = Backup.query.get_or_404(backup_id)
    caminho_backup = os.path.join(BACKUP_DIR, backup_obj.nome_arquivo)
    
    if not os.path.exists(caminho_backup):
        flash('Arquivo de backup não encontrado!', 'danger')
        return redirect(url_for('backup.listar_backups'))
    
    # Obter caminho do banco de dados atual
    db_uri = db.engine.url.database
    if db_uri.startswith('/'):
        db_path = db_uri
    else:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_uri)
    
    try:
        # Criar backup temporário antes da restauração
        temp_backup = f"{db_path}.temp"
        shutil.copy2(db_path, temp_backup)
        
        # Fechar todas as conexões com o banco de dados
        db.session.close()
        db.engine.dispose()
        
        if caminho_backup.endswith('.zip'):
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
        else:
            # backup antigo apenas do banco
            shutil.copy2(caminho_backup, db_path)
        
        flash('Backup restaurado com sucesso! Por favor, reinicie a aplicação.', 'success')
    except Exception as e:
        # Tentar restaurar o backup temporário em caso de falha
        if os.path.exists(temp_backup):
            try:
                shutil.copy2(temp_backup, db_path)
            except:
                pass
        
        flash(f'Erro ao restaurar backup: {str(e)}', 'danger')
    finally:
        # Remover backup temporário
        if os.path.exists(temp_backup):
            os.remove(temp_backup)
    
    return redirect(url_for('backup.listar_backups'))

@backup.route('/backups/download/<int:backup_id>')
@login_required
@permissao_requerida('admin')
def download_backup(backup_id):
    """Rota para baixar um arquivo de backup"""
    backup_obj = Backup.query.get_or_404(backup_id)
    caminho_backup = os.path.join(BACKUP_DIR, backup_obj.nome_arquivo)
    
    if not os.path.exists(caminho_backup):
        flash('Arquivo de backup não encontrado!', 'danger')
        return redirect(url_for('backup.listar_backups'))
    
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
