import os
import logging
import sqlite3
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


def _normalize_db_url(db_url: str) -> str:
    if not db_url:
        return db_url
    if db_url.startswith('postgresql+psycopg://'):
        return 'postgresql://' + db_url[len('postgresql+psycopg://'):]
    if db_url.startswith('postgresql+psycopg2://'):
        return 'postgresql://' + db_url[len('postgresql+psycopg2://'):]
    if db_url.startswith('postgres://'):
        return 'postgresql://' + db_url[len('postgres://'):]
    return db_url


def migrate_postgres() -> bool:
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning('DATABASE_URL não encontrada, pulando migração PostgreSQL')
            return False

        db_url = _normalize_db_url(db_url)

        if psycopg is not None:
            conn = psycopg.connect(db_url)
            conn.autocommit = True
            cursor = conn.cursor()
        elif psycopg2 is not None:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cursor = conn.cursor()
        else:
            logger.warning('psycopg/psycopg2 não estão disponíveis, pulando migração PostgreSQL')
            return False

        stmts = [
            "ALTER TABLE item ADD COLUMN IF NOT EXISTS desenho_aprovado_em TIMESTAMP NULL;",
            "ALTER TABLE item ADD COLUMN IF NOT EXISTS desenho_aprovado_por_id INTEGER NULL;",
            "ALTER TABLE item ADD COLUMN IF NOT EXISTS desenho_aprovado_por_nome VARCHAR(120) NULL;",
        ]

        for s in stmts:
            cursor.execute(s)

        cursor.close()
        return True
    except Exception as e:
        logger.error(f'Erro ao migrar PostgreSQL: {str(e)}')
        return False
    finally:
        if conn:
            conn.close()


def _sqlite_add_column_if_missing(cursor, table: str, column: str, ddl: str) -> None:
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def migrate_sqlite() -> bool:
    conn = None
    try:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')

        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        _sqlite_add_column_if_missing(cursor, 'item', 'desenho_aprovado_em', 'DATETIME NULL')
        _sqlite_add_column_if_missing(cursor, 'item', 'desenho_aprovado_por_id', 'INTEGER NULL')
        _sqlite_add_column_if_missing(cursor, 'item', 'desenho_aprovado_por_nome', 'VARCHAR(120) NULL')

        conn.commit()
        return True
    except Exception as e:
        logger.error(f'Erro ao migrar SQLite: {str(e)}')
        return False
    finally:
        if conn:
            conn.close()


def run() -> bool:
    load_dotenv()
    db_url = os.getenv('DATABASE_URL', '') or ''
    if db_url.lower().startswith('postgres'):
        return migrate_postgres()
    return migrate_sqlite()


if __name__ == '__main__':
    ok = run()
    raise SystemExit(0 if ok else 1)
