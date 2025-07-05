from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from models import db, Backup, Usuario
from routes.auth import login_required, permissao_requerida
from datetime import datetime
import os
import subprocess
import shutil
import tempfile
import glob

backup = Blueprint('backup', __name__)

# Diretório para armazenar os backups
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

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
    nome_arquivo = f"backup_{timestamp}.sqlite"
    caminho_arquivo = os.path.join(BACKUP_DIR, nome_arquivo)
    
    # Obter caminho do banco de dados atual
    db_uri = db.engine.url.database
    if db_uri.startswith('/'):
        db_path = db_uri
    else:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_uri)
    
    try:
        # Criar cópia do banco de dados
        shutil.copy2(db_path, caminho_arquivo)
        
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
        
        flash('Backup criado com sucesso!', 'success')
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
        
        # Restaurar o backup
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
        nome_arquivo = f"backup_auto_{timestamp}.sqlite"
        caminho_arquivo = os.path.join(BACKUP_DIR, nome_arquivo)
        
        # Obter caminho do banco de dados atual
        db_uri = db.engine.url.database
        if db_uri.startswith('/'):
            db_path = db_uri
        else:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_uri)
        
        # Criar cópia do banco de dados
        shutil.copy2(db_path, caminho_arquivo)
        
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
        print(f"Erro ao criar backup automático: {str(e)}")
        return False
