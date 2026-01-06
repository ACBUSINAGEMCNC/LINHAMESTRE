"""Migração para adicionar a coluna tamanho_peca à tabela item.
Este script pode ser executado diretamente ou importado pelo app.py
para ser executado durante a inicialização da aplicação.
"""

import os
import logging
import sqlite3
from dotenv import load_dotenv

try:
	import psycopg2
	from psycopg2 import sql
except Exception:  # psycopg2 pode não estar instalado em ambiente SQLite local
	psycopg2 = None
	sql = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_postgres():
    """Adiciona a coluna tamanho_peca à tabela item no PostgreSQL."""
    conn = None
    try:
        if psycopg2 is None or sql is None:
            logger.warning("psycopg2 não está disponível, pulando migração PostgreSQL")
            return False
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
                    WHERE table_name = 'item' AND column_name = 'tamanho_peca'
                );
                """
            )

            if cursor.fetchone()[0]:
                logger.info("Coluna 'tamanho_peca' já existe na tabela 'item' (PostgreSQL)")
                return True

            query = sql.SQL(
                """
                ALTER TABLE item
                ADD COLUMN IF NOT EXISTS tamanho_peca VARCHAR(100);
                """
            )
            cursor.execute(query)
            logger.info("Coluna 'tamanho_peca' adicionada com sucesso à tabela 'item' (PostgreSQL)")
            return True

    except Exception as e:
        logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def migrate_sqlite():
    """Adiciona a coluna tamanho_peca à tabela item no SQLite."""
    conn = None
    try:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')

        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(item)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'tamanho_peca' in columns:
            logger.info("Coluna 'tamanho_peca' já existe na tabela 'item' (SQLite)")
            return True

        cursor.execute("ALTER TABLE item ADD COLUMN tamanho_peca VARCHAR(100)")
        conn.commit()
        logger.info("Coluna 'tamanho_peca' adicionada com sucesso à tabela 'item' (SQLite)")
        return True

    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    logger.info("Iniciando migração para adicionar coluna 'tamanho_peca'...")

    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True

    logger.error("Falha na migração!")
    return False


if __name__ == "__main__":
    run_migration()
