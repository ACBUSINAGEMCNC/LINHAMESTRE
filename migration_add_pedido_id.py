from sqlalchemy import create_engine, Column, Integer, ForeignKey
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import sqlite3
import os

# Caminho do banco de dados
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')

# Conectar ao banco de dados SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Tentar adicionar a coluna pedido_id
    cursor.execute('ALTER TABLE item_pedido_material ADD COLUMN pedido_id INTEGER')
    print("Coluna pedido_id adicionada com sucesso!")
    conn.commit()
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Coluna pedido_id já existe.")
    else:
        print(f"Erro ao adicionar coluna: {e}")

conn.close()
