"""Migration para adicionar coluna status na tabela pedido_consumo."""
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
            WHERE table_name = 'pedido_consumo' AND column_name = 'status'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE pedido_consumo ADD COLUMN status VARCHAR(25) DEFAULT 'aberto'")
            conn.commit()
            logger.info("Coluna status adicionada em pedido_consumo (PostgreSQL).")
        else:
            logger.info("Coluna status já existe em pedido_consumo (PostgreSQL).")
        cur.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar status em pedido_consumo (PostgreSQL): {e}")
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
        cur.execute("PRAGMA table_info(pedido_consumo)")
        cols = [row[1] for row in cur.fetchall()]
        if 'status' not in cols:
            cur.execute("ALTER TABLE pedido_consumo ADD COLUMN status VARCHAR(25) DEFAULT 'aberto'")
            conn.commit()
            logger.info("Coluna status adicionada em pedido_consumo (SQLite).")
        else:
            logger.info("Coluna status já existe em pedido_consumo (SQLite).")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar status em pedido_consumo (SQLite): {e}")
        return False
