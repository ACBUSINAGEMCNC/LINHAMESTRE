"""Migração para adicionar as colunas material_laser e espessura_laser à tabela item.
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
except Exception:
    psycopg2 = None
    sql = None

try:
    import psycopg
except Exception:
    psycopg = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_postgres():
    """Adiciona as colunas material_laser e espessura_laser à tabela item no PostgreSQL."""
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
            return False

        if db_url.startswith('postgresql+psycopg://'):
            db_url = 'postgresql://' + db_url[len('postgresql+psycopg://'):]
        elif db_url.startswith('postgres://'):
            db_url = 'postgresql://' + db_url[len('postgres://'):]

        if psycopg is not None:
            conn = psycopg.connect(db_url)
            conn.autocommit = True
            cursor_ctx = conn.cursor()
            close_cursor = True
        elif psycopg2 is not None and sql is not None:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cursor_ctx = conn.cursor()
            close_cursor = True
        else:
            logger.warning("psycopg/psycopg2 não estão disponíveis, pulando migração PostgreSQL")
            return False

        try:
            cursor = cursor_ctx
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'item' AND column_name IN ('material_laser', 'espessura_laser');
                """
            )
            existing = {row[0] for row in cursor.fetchall()}

            if 'material_laser' not in existing:
                cursor.execute(
                    """
                    ALTER TABLE item
                    ADD COLUMN IF NOT EXISTS material_laser VARCHAR(100);
                    """
                )
                logger.info("Coluna 'material_laser' adicionada com sucesso à tabela 'item' (PostgreSQL)")
            else:
                logger.info("Coluna 'material_laser' já existe na tabela 'item' (PostgreSQL)")

            if 'espessura_laser' not in existing:
                cursor.execute(
                    """
                    ALTER TABLE item
                    ADD COLUMN IF NOT EXISTS espessura_laser VARCHAR(50);
                    """
                )
                logger.info("Coluna 'espessura_laser' adicionada com sucesso à tabela 'item' (PostgreSQL)")
            else:
                logger.info("Coluna 'espessura_laser' já existe na tabela 'item' (PostgreSQL)")

            return True
        finally:
            if close_cursor:
                cursor_ctx.close()
    except Exception as e:
        logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def migrate_sqlite():
    """Adiciona as colunas material_laser e espessura_laser à tabela item no SQLite."""
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
        changed = False

        if 'material_laser' not in columns:
            cursor.execute("ALTER TABLE item ADD COLUMN material_laser VARCHAR(100)")
            logger.info("Coluna 'material_laser' adicionada com sucesso à tabela 'item' (SQLite)")
            changed = True
        else:
            logger.info("Coluna 'material_laser' já existe na tabela 'item' (SQLite)")

        if 'espessura_laser' not in columns:
            cursor.execute("ALTER TABLE item ADD COLUMN espessura_laser VARCHAR(50)")
            logger.info("Coluna 'espessura_laser' adicionada com sucesso à tabela 'item' (SQLite)")
            changed = True
        else:
            logger.info("Coluna 'espessura_laser' já existe na tabela 'item' (SQLite)")

        if changed:
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    logger.info("Iniciando migração para adicionar colunas de laser no item...")
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True

    logger.error("Falha na migração!")
    return False


if __name__ == "__main__":
    run_migration()
