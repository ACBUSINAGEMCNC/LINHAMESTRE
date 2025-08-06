from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
import os
from werkzeug.utils import secure_filename
from flask import current_app

arquivos = Blueprint('arquivos', __name__)

@arquivos.route('/uploads/imagens/<filename>')
def uploaded_imagem(filename):
    """Rota para acessar imagens enviadas"""
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER_IMAGENS'], filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    else:
        flash(f'Arquivo de imagem não encontrado: {filename}', 'danger')
        return render_template('error.html', message=f'Arquivo de imagem {filename} não encontrado'), 404

@arquivos.route('/uploads/desenhos/<filename>')
def uploaded_desenho(filename):
    """Rota para acessar desenhos enviados"""
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER_DESENHOS'], filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    else:
        flash(f'Arquivo de desenho não encontrado: {filename}', 'danger')
        return render_template('error.html', message=f'Arquivo de desenho {filename} não encontrado'), 404

@arquivos.route('/uploads/instrucoes/<filename>')
def uploaded_instrucao(filename):
    """Rota para acessar instruções enviadas"""
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER_INSTRUCOES'], filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    else:
        flash(f'Arquivo de instrução não encontrado: {filename}', 'danger')
        return render_template('error.html', message=f'Arquivo de instrução {filename} não encontrado'), 404
