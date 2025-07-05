"""
Script de migração para adicionar a coluna material_comprado à tabela pedido
"""

from flask import Flask
from models import db
import os
import sqlite3

def run_migration():
    """Executa a migração para adicionar a coluna material_comprado à tabela pedido"""
    # Verificar se o arquivo do banco de dados existe
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'acb_usinagem.db')
    
    # Se o banco de dados não existir, criar um banco de dados vazio
    if not os.path.exists(db_path):
        print(f"Criando banco de dados em: {db_path}")
        conn = sqlite3.connect(db_path)
        conn.close()
        
        # Criar uma aplicação Flask temporária para inicializar o banco de dados
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
            print("Banco de dados inicializado com sucesso")
    
    # Adicionar a coluna material_comprado
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se a tabela pedido existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pedido'")
        if cursor.fetchone() is None:
            print("A tabela 'pedido' não existe no banco de dados")
            conn.close()
            return
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(pedido)")
        colunas = cursor.fetchall()
        colunas_nomes = [coluna[1] for coluna in colunas]
        
        if 'material_comprado' not in colunas_nomes:
            # Adicionar a coluna material_comprado
            cursor.execute('ALTER TABLE pedido ADD COLUMN material_comprado BOOLEAN DEFAULT 0')
            conn.commit()
            print("Coluna 'material_comprado' adicionada com sucesso à tabela 'pedido'")
        else:
            print("A coluna 'material_comprado' já existe na tabela 'pedido'")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Erro ao executar a migração: {e}")

if __name__ == '__main__':
    run_migration()
