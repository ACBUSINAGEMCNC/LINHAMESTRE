import os
import sys
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
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.error("Variável de ambiente DATABASE_URL não encontrada!")
            sys.exit(1)
            
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        logger.info("Conectado ao banco de dados PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        sys.exit(1)

def column_exists(conn, table_name, column_name):
    """Verifica se uma coluna existe na tabela especificada."""
    try:
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
    except Exception as e:
        logger.error(f"Erro ao verificar coluna {column_name}: {str(e)}")
        return False

def add_column(conn, table_name, column_name, column_type):
    """Adiciona uma coluna à tabela se ela não existir."""
    try:
        with conn.cursor() as cursor:
            query = sql.SQL("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                ) THEN
                    EXECUTE format('ALTER TABLE %I ADD COLUMN %I %s', %s, %s, %s);
                    RAISE NOTICE 'Coluna % adicionada com sucesso';
                END IF;
            END $$;
            """)
            
            # Usando sql.Identifier para evitar SQL injection
            cursor.execute(
                query, 
                [
                    table_name, 
                    column_name,
                    sql.Identifier(table_name).as_string(conn),  # Seguro contra SQL injection
                    sql.Identifier(column_name).as_string(conn),
                    column_type,
                    column_name
                ]
            )
            logger.info(f"Coluna '{column_name}' adicionada com sucesso à tabela '{table_name}'")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao adicionar coluna '{column_name}': {str(e)}")
        return False

def main():
    logger.info("Iniciando migração da tabela 'maquina'...")
    
    conn = None
    try:
        # Conectar ao banco de dados
        conn = get_db_connection()
        
        # Verificar se a tabela existe
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'maquina'
                );
            """)
            if not cursor.fetchone()[0]:
                logger.error("A tabela 'maquina' não existe no banco de dados!")
                sys.exit(1)
        
        # Verificar se a coluna já existe
        if column_exists(conn, 'maquina', 'categoria_trabalho'):
            logger.info("A coluna 'categoria_trabalho' já existe na tabela 'maquina'.")
        else:
            # Adicionar a coluna
            if add_column(conn, 'maquina', 'categoria_trabalho', 'VARCHAR(50)'):
                logger.info("Migração concluída com sucesso!")
            else:
                logger.error("Falha ao adicionar a coluna 'categoria_trabalho'.")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"Erro durante a migração: {str(e)}")
        sys.exit(1)
        
    finally:
        if conn:
            conn.close()
            logger.info("Conexão com o banco de dados encerrada.")

if __name__ == "__main__":
    main()
