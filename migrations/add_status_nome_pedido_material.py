"""Migration para adicionar colunas status e nome na tabela pedido_material."""
import os
import sqlite3
import logging
from dotenv import load_dotenv

try:
    import psycopg2
except Exception:
    psycopg2 = None

try:
    import psycopg
except Exception:
    psycopg = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _get_postgres_conn():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        return None
    if db_url.startswith('postgresql+psycopg://'):
        db_url = 'postgresql://' + db_url[len('postgresql+psycopg://'):]
    elif db_url.startswith('postgres://'):
        db_url = 'postgresql://' + db_url[len('postgres://'):]

    if psycopg is not None:
        return psycopg.connect(db_url)
    if psycopg2 is not None:
        return psycopg2.connect(db_url)
    return None


def migrate_postgres():
    conn = None
    try:
        conn = _get_postgres_conn()
        if not conn:
            logger.warning("DATABASE_URL não encontrada ou driver PostgreSQL indisponível, pulando migração.")
            return False

        cur = conn.cursor()
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'pedido_material' AND column_name IN ('status', 'nome')
        """)
        colunas_existentes = {row[0] for row in cur.fetchall()}

        if 'status' not in colunas_existentes:
            cur.execute("ALTER TABLE pedido_material ADD COLUMN status VARCHAR(25) DEFAULT 'aberto'")
            logger.info("Coluna status adicionada em pedido_material (PostgreSQL).")
        else:
            logger.info("Coluna status já existe em pedido_material (PostgreSQL).")

        if 'nome' not in colunas_existentes:
            cur.execute("ALTER TABLE pedido_material ADD COLUMN nome VARCHAR(255)")
            logger.info("Coluna nome adicionada em pedido_material (PostgreSQL).")
        else:
            logger.info("Coluna nome já existe em pedido_material (PostgreSQL).")

        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar colunas em pedido_material (PostgreSQL): {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def migrate_sqlite():
    try:
        load_dotenv()
        db_path = os.getenv('SQLITE_DB_PATH', 'instance/linhamestre.db')
        if not os.path.exists(db_path):
            logger.warning(f"Banco SQLite não encontrado em {db_path}, pulando migração.")
            return False

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(pedido_material)")
        cols = [row[1] for row in cur.fetchall()]

        if 'status' not in cols:
            cur.execute("ALTER TABLE pedido_material ADD COLUMN status VARCHAR(25) DEFAULT 'aberto'")
            logger.info("Coluna status adicionada em pedido_material (SQLite).")
        else:
            logger.info("Coluna status já existe em pedido_material (SQLite).")

        if 'nome' not in cols:
            cur.execute("ALTER TABLE pedido_material ADD COLUMN nome VARCHAR(255)")
            logger.info("Coluna nome adicionada em pedido_material (SQLite).")
        else:
            logger.info("Coluna nome já existe em pedido_material (SQLite).")

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar colunas em pedido_material (SQLite): {e}")
        return False
