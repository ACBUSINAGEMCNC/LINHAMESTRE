from sqlalchemy import create_engine, Column, Integer, ForeignKey, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError
from models import db  # Importar o db do models
import os

# Caminho do banco de dados
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')

# Criar engine
engine = create_engine(f'sqlite:///{db_path}')

def add_column_if_not_exists(table_name, column_name, column_type):
    try:
        # Tentar adicionar a coluna
        with engine.connect() as connection:
            connection.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}')
        print(f"Coluna {column_name} adicionada à tabela {table_name}")
    except OperationalError as e:
        # Se a coluna já existir, a exceção será capturada
        if "duplicate column name" in str(e) or "duplicate column" in str(e):
            print(f"Coluna {column_name} já existe na tabela {table_name}")
        else:
            print(f"Erro ao adicionar coluna {column_name}: {e}")

def migrate_database():
    # Adicionar colunas que podem estar faltando
    add_column_if_not_exists('item_pedido_material', 'pedido_id', 'INTEGER')

    print("Migração concluída.")

if __name__ == '__main__':
    migrate_database()
