# Script para adicionar colunas de cancelamento à tabela Pedido
# Execute este script no mesmo diretório que o seu arquivo app.py e database.db

import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "instance", "database.db")

# Verificar se o diretório instance existe, senão usar o diretório atual
if not os.path.exists(os.path.dirname(DATABASE_PATH)):
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "database.db")

print(f"Tentando conectar ao banco de dados em: {DATABASE_PATH}")

if not os.path.exists(DATABASE_PATH):
    print(f"Erro: Arquivo do banco de dados não encontrado em {DATABASE_PATH}. Certifique-se de que o caminho está correto e o arquivo existe.")
else:
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        print("Conectado ao banco de dados com sucesso.")

        # Verificar quais colunas já existem
        cursor.execute("PRAGMA table_info(pedido)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        print(f"Colunas existentes na tabela pedido: {existing_columns}")

        columns_to_add = {
            "cancelado": "BOOLEAN DEFAULT 0",
            "motivo_cancelamento": "TEXT",
            "cancelado_por": "VARCHAR(100)",
            "data_cancelamento": "DATETIME"
        }

        added_count = 0
        skipped_count = 0

        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE pedido ADD COLUMN {col_name} {col_type}"
                    print(f"Executando: {sql}")
                    cursor.execute(sql)
                    print(f"Coluna ", {col_name}, " adicionada com sucesso.")
                    added_count += 1
                except sqlite3.OperationalError as e:
                    print(f"Erro ao adicionar coluna ", {col_name}, ": {e}")
            else:
                print(f"Coluna ", {col_name}, " já existe. Pulando.")
                skipped_count += 1

        conn.commit()
        print(f"\nMigração concluída. {added_count} coluna(s) adicionada(s), {skipped_count} coluna(s) já existia(m).")

    except sqlite3.Error as e:
        print(f"Erro ao conectar ou modificar o banco de dados: {e}")
    finally:
        if conn:
            conn.close()
            print("Conexão com o banco de dados fechada.")

