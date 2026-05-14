import logging
import os
import sqlite3
from dotenv import load_dotenv

try:
    import psycopg
except Exception:
    psycopg = None

try:
    import psycopg2
except Exception:
    psycopg2 = None

logger = logging.getLogger(__name__)


def _normalize_pg_url(db_url):
    if db_url.startswith('postgresql+psycopg://'):
        return 'postgresql://' + db_url[len('postgresql+psycopg://'):]
    if db_url.startswith('postgresql+psycopg2://'):
        return 'postgresql://' + db_url[len('postgresql+psycopg2://'):]
    if db_url.startswith('postgres://'):
        return 'postgresql://' + db_url[len('postgres://'):]
    return db_url


def migrate_postgres():
    conn = None
    cursor = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração item_classe.")
            return False
        db_url = _normalize_pg_url(db_url)

        if psycopg is not None:
            conn = psycopg.connect(db_url)
        elif psycopg2 is not None:
            conn = psycopg2.connect(db_url)
        else:
            logger.warning("psycopg/psycopg2 não disponíveis, pulando migração item_classe.")
            return False

        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_classe (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(120) NOT NULL,
                parent_id INTEGER NULL REFERENCES item_classe(id) ON DELETE SET NULL,
                ativa BOOLEAN DEFAULT TRUE,
                ordem INTEGER DEFAULT 0,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            ALTER TABLE item
            ADD COLUMN IF NOT EXISTS item_classe_id INTEGER;
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_item_classe_parent_id ON item_classe(parent_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_item_classe_ativa ON item_classe(ativa);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_item_item_classe_id ON item(item_classe_id);")
        return True
    except Exception as exc:
        logger.warning(f"Erro ao migrar item_classe no PostgreSQL: {exc}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def migrate_sqlite():
    conn = None
    try:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')
        if not os.path.exists(db_path):
            logger.warning(f"Banco SQLite não encontrado em {db_path}, pulando migração item_classe.")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_classe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(120) NOT NULL,
                parent_id INTEGER NULL REFERENCES item_classe(id) ON DELETE SET NULL,
                ativa BOOLEAN DEFAULT 1,
                ordem INTEGER DEFAULT 0,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("PRAGMA table_info(item)")
        item_columns = [column[1] for column in cursor.fetchall()]
        if 'item_classe_id' not in item_columns:
            cursor.execute("ALTER TABLE item ADD COLUMN item_classe_id INTEGER")

        cursor.execute("CREATE INDEX IF NOT EXISTS ix_item_classe_parent_id ON item_classe(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_item_classe_ativa ON item_classe(ativa)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_item_item_classe_id ON item(item_classe_id)")
        conn.commit()
        return True
    except Exception as exc:
        logger.warning(f"Erro ao migrar item_classe no SQLite: {exc}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    return migrate_postgres() or migrate_sqlite()


if __name__ == '__main__':
    run_migration()
