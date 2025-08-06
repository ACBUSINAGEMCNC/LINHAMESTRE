"""
Script de migração para adicionar colunas data_fim e operador_id à tabela apontamento_producao
"""
import os
import sys
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Adicionar diretório raiz ao path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carregar variáveis de ambiente
load_dotenv()

def conectar_bd():
    """Conecta ao banco de dados PostgreSQL (Supabase)"""
    try:
        # Obter credenciais do ambiente
        db_url = os.getenv('DATABASE_URL')
        
        # Conectar ao banco
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        print("Conectado ao PostgreSQL/Supabase com sucesso!")
        return conn
    except Exception as e:
        print(f"[ERRO] Falha ao conectar ao banco de dados: {e}")
        sys.exit(1)

def adicionar_colunas(conn):
    """Adiciona as colunas data_fim e operador_id à tabela apontamento_producao"""
    try:
        cursor = conn.cursor()
        
        # Verificar se a coluna data_fim já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'apontamento_producao' AND column_name = 'data_fim'
        """)
        if not cursor.fetchone():
            print("Adicionando coluna data_fim à tabela apontamento_producao...")
            cursor.execute("""
                ALTER TABLE apontamento_producao 
                ADD COLUMN data_fim TIMESTAMP
            """)
            print("[OK] Coluna data_fim adicionada com sucesso!")
        else:
            print("[OK] Coluna data_fim já existe na tabela.")
        
        # Verificar se a coluna operador_id já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'apontamento_producao' AND column_name = 'operador_id'
        """)
        if not cursor.fetchone():
            print("Adicionando coluna operador_id à tabela apontamento_producao...")
            cursor.execute("""
                ALTER TABLE apontamento_producao 
                ADD COLUMN operador_id INTEGER REFERENCES usuario(id)
            """)
            print("[OK] Coluna operador_id adicionada com sucesso!")
        else:
            print("[OK] Coluna operador_id já existe na tabela.")
        
        cursor.close()
        return True
    except Exception as e:
        print(f"[ERRO] Falha ao adicionar colunas: {e}")
        return False

def main():
    """Função principal"""
    print("Iniciando migração para adicionar colunas à tabela apontamento_producao...")
    
    # Conectar ao banco de dados
    conn = conectar_bd()
    
    # Adicionar colunas
    if adicionar_colunas(conn):
        print("Migração concluída com sucesso!")
    else:
        print("Falha na migração.")
    
    # Fechar conexão
    conn.close()
    print("Conexão fechada.")

if __name__ == "__main__":
    main()
