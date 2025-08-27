import os
import logging
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """Estabelece conexão com o banco de dados PostgreSQL."""
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        raise

def column_exists(conn, table_name, column_name):
    """Verifica se uma coluna existe na tabela especificada."""
    with conn.cursor() as cursor:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        );
        """
        cursor.execute(query, (table_name, column_name))
        return cursor.fetchone()[0]

def add_categoria_trabalho_column():
    """Adiciona a coluna categoria_trabalho à tabela maquina se ela não existir."""
    conn = None
    try:
        conn = get_db_connection()
        
        if not column_exists(conn, 'maquina', 'categoria_trabalho'):
            logger.info("Adicionando coluna 'categoria_trabalho' à tabela 'maquina'...")
            with conn.cursor() as cursor:
                # Usando sql.SQL para evitar SQL injection
                query = sql.SQL("""
                ALTER TABLE maquina 
                ADD COLUMN IF NOT EXISTS categoria_trabalho VARCHAR(50);
                """)
                cursor.execute(query)
                logger.info("Coluna 'categoria_trabalho' adicionada com sucesso!")
        else:
            logger.info("A coluna 'categoria_trabalho' já existe na tabela 'maquina'.")
            
        return True
        
    except Exception as e:
        logger.error(f"Erro ao adicionar coluna 'categoria_trabalho': {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Iniciando migração para PostgreSQL...")
    load_dotenv()  # Carrega as variáveis de ambiente do .env
    
    if not os.getenv('DATABASE_URL'):
        logger.error("Variável de ambiente DATABASE_URL não encontrada!")
        exit(1)
        
    success = add_categoria_trabalho_column()
    if success:
        logger.info("Migração concluída com sucesso!")
    else:
        logger.error("Falha na migração!")
        exit(1)
