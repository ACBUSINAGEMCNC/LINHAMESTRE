# Script para adicionar a coluna posicao à tabela item usando sqlite3 diretamente
import sqlite3
import os

def add_posicao_column():
    # Caminho para o arquivo do banco de dados SQLite
    db_path = 'database.db'
    
    if not os.path.exists(db_path):
        print(f"Erro: Banco de dados não encontrado em {db_path}")
        return
    
    try:
        # Conectar ao banco de dados
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(item)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'posicao' not in column_names:
            # Adicionar a coluna posicao
            cursor.execute("ALTER TABLE item ADD COLUMN posicao INTEGER DEFAULT 0")
            conn.commit()
            print("Coluna 'posicao' adicionada com sucesso à tabela 'item'.")
        else:
            print("A coluna 'posicao' já existe na tabela 'item'.")
            
    except Exception as e:
        print(f"Erro ao modificar o banco de dados: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_posicao_column()
