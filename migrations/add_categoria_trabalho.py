"""
Migração para adicionar a coluna categoria_trabalho à tabela maquina.
Este script pode ser executado diretamente ou importado pelo app.py
para ser executado durante a inicialização da aplicação.
"""

import os
import logging
import psycopg2
from psycopg2 import sql
import sqlite3
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_postgres():
    """Adiciona a coluna categoria_trabalho à tabela maquina no PostgreSQL."""
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
            return False
            
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'maquina' AND column_name = 'categoria_trabalho'
                );
            """)
            
            if cursor.fetchone()[0]:
                logger.info("Coluna 'categoria_trabalho' já existe na tabela 'maquina' (PostgreSQL)")
                return True
                
            # Adicionar a coluna
            query = sql.SQL("""
                ALTER TABLE maquina 
                ADD COLUMN IF NOT EXISTS categoria_trabalho VARCHAR(50);
            """)
            cursor.execute(query)
            logger.info("Coluna 'categoria_trabalho' adicionada com sucesso à tabela 'maquina' (PostgreSQL)")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def migrate_sqlite():
    """Adiciona a coluna categoria_trabalho à tabela maquina no SQLite."""
    conn = None
    try:
        # Obter caminho do banco de dados
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')
        
        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(maquina)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'categoria_trabalho' in columns:
            logger.info("Coluna 'categoria_trabalho' já existe na tabela 'maquina' (SQLite)")
            return True
            
        # Adicionar a coluna
        cursor.execute("ALTER TABLE maquina ADD COLUMN categoria_trabalho VARCHAR(50)")
        conn.commit()
        logger.info("Coluna 'categoria_trabalho' adicionada com sucesso à tabela 'maquina' (SQLite)")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def run_migration():
    """Executa a migração para ambos os bancos de dados."""
    logger.info("Iniciando migração para adicionar coluna 'categoria_trabalho'...")
    
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()
    
    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True
    else:
        logger.error("Falha na migração!")
        return False

if __name__ == "__main__":
    run_migration()
