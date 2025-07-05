import sqlite3
import os
import sys

# Caminho do banco de dados
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')
print(f"Atualizando banco de dados em: {db_path}")
sys.stdout.flush()

def add_columns():
    """Adiciona as colunas relacionadas ao cancelamento na tabela pedido"""
    try:
        # Conectar ao banco de dados
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se as colunas já existem
        cursor.execute("PRAGMA table_info(pedido)")
        colunas = [coluna[1] for coluna in cursor.fetchall()]
        
        # Adicionar colunas se elas não existirem
        if 'cancelado' not in colunas:
            cursor.execute("ALTER TABLE pedido ADD COLUMN cancelado BOOLEAN DEFAULT 0")
            print("Coluna 'cancelado' adicionada com sucesso.")
        else:
            print("Coluna 'cancelado' já existe.")
            
        if 'motivo_cancelamento' not in colunas:
            cursor.execute("ALTER TABLE pedido ADD COLUMN motivo_cancelamento TEXT")
            print("Coluna 'motivo_cancelamento' adicionada com sucesso.")
        else:
            print("Coluna 'motivo_cancelamento' já existe.")
            
        if 'cancelado_por' not in colunas:
            cursor.execute("ALTER TABLE pedido ADD COLUMN cancelado_por TEXT")
            print("Coluna 'cancelado_por' adicionada com sucesso.")
        else:
            print("Coluna 'cancelado_por' já existe.")
            
        if 'data_cancelamento' not in colunas:
            cursor.execute("ALTER TABLE pedido ADD COLUMN data_cancelamento TIMESTAMP")
            print("Coluna 'data_cancelamento' adicionada com sucesso.")
        else:
            print("Coluna 'data_cancelamento' já existe.")
        
        # Salvar alterações e fechar conexão
        conn.commit()
        conn.close()
        print("Atualização do banco de dados concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro ao atualizar o banco de dados: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    print("Iniciando atualização do banco de dados...")
    sys.stdout.flush()
    add_columns()
    print("Processo concluído!")
    sys.stdout.flush()
