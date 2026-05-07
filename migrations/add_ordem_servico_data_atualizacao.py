"""
Migração para adicionar a coluna data_atualizacao à tabela ordem_servico.
Permite sync incremental do Kanban entre sessões.
"""

import os
import logging
import psycopg2
import sqlite3
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_postgres():
    """Adiciona a coluna data_atualizacao à tabela ordem_servico no PostgreSQL."""
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
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'ordem_servico' AND column_name = 'data_atualizacao'
                );
                """
            )
            if cursor.fetchone()[0]:
                logger.info("Coluna 'data_atualizacao' já existe na tabela 'ordem_servico' (PostgreSQL)")
                return True

            cursor.execute(
                """
                ALTER TABLE ordem_servico
                ADD COLUMN IF NOT EXISTS data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                """
            )
            cursor.execute(
                """
                UPDATE ordem_servico SET data_atualizacao = CURRENT_TIMESTAMP
                WHERE data_atualizacao IS NULL;
                """
            )
            logger.info("Coluna 'data_atualizacao' adicionada com sucesso à tabela 'ordem_servico' (PostgreSQL)")
            return True
    except Exception as e:
        logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def migrate_sqlite():
    """Adiciona a coluna data_atualizacao à tabela ordem_servico no SQLite."""
    conn = None
    try:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')
        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(ordem_servico)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'data_atualizacao' in columns:
            logger.info("Coluna 'data_atualizacao' já existe na tabela 'ordem_servico' (SQLite)")
            return True

        cursor.execute("ALTER TABLE ordem_servico ADD COLUMN data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP")
        cursor.execute("UPDATE ordem_servico SET data_atualizacao = CURRENT_TIMESTAMP WHERE data_atualizacao IS NULL")
        conn.commit()
        logger.info("Coluna 'data_atualizacao' adicionada com sucesso à tabela 'ordem_servico' (SQLite)")
        return True
    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    logger.info("Iniciando migração para adicionar coluna 'data_atualizacao' em ordem_servico...")
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True

    logger.error("Falha na migração!")
    return False


if __name__ == "__main__":
    run_migration()
