import os
import sqlite3


ADMIN_EMAIL = 'admin@acbusinagem.com.br'


def _get_database_url_from_env() -> str:
    url = (
        os.getenv('DATABASE_URL', '')
        or os.getenv('URL_DO_BANCO_DE_DADOS', '')
        or os.getenv('URL_BANCO_DE_DADOS', '')
    )
    if not url:
        return ''
    url_lower = url.lower()
    if url_lower.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
        url_lower = url.lower()
    if url_lower.startswith('postgresql://') and '+psycopg' not in url_lower and '+psycopg2' not in url_lower:
        try:
            import psycopg  # noqa: F401
            url = 'postgresql+psycopg://' + url[len('postgresql://'):]
        except Exception:
            pass
    return url


def migrate_postgres() -> bool:
    from sqlalchemy import create_engine, text

    database_url = _get_database_url_from_env()
    if not database_url:
        return False

    engine = create_engine(database_url)
    stmts = [
        "ALTER TABLE item ADD COLUMN IF NOT EXISTS valor_item DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE item ADD COLUMN IF NOT EXISTS valor_material DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE item ADD COLUMN IF NOT EXISTS outros_custos DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE item ADD COLUMN IF NOT EXISTS imposto_percentual DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE usuario ADD COLUMN IF NOT EXISTS acesso_valores_itens BOOLEAN DEFAULT FALSE",
        f"UPDATE usuario SET acesso_valores_itens = TRUE WHERE lower(email) = lower('{ADMIN_EMAIL}')",
    ]

    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
    return True


def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def migrate_sqlite(db_path: str = None) -> bool:
    if not db_path:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(db_dir, '..', 'database.db')
        db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        return False

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    def _has_column(table: str, column: str) -> bool:
        cur.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cur.fetchall()]
        return column in cols

    changed = False

    if _table_exists(cur, 'item') and not _has_column('item', 'valor_item'):
        cur.execute("ALTER TABLE item ADD COLUMN valor_item REAL DEFAULT 0")
        changed = True

    if _table_exists(cur, 'item') and not _has_column('item', 'valor_material'):
        cur.execute("ALTER TABLE item ADD COLUMN valor_material REAL DEFAULT 0")
        changed = True

    if _table_exists(cur, 'item') and not _has_column('item', 'outros_custos'):
        cur.execute("ALTER TABLE item ADD COLUMN outros_custos REAL DEFAULT 0")
        changed = True

    if _table_exists(cur, 'item') and not _has_column('item', 'imposto_percentual'):
        cur.execute("ALTER TABLE item ADD COLUMN imposto_percentual REAL DEFAULT 0")
        changed = True

    if _table_exists(cur, 'usuario') and not _has_column('usuario', 'acesso_valores_itens'):
        cur.execute("ALTER TABLE usuario ADD COLUMN acesso_valores_itens BOOLEAN DEFAULT 0")
        changed = True

    if _table_exists(cur, 'usuario'):
        cur.execute("UPDATE usuario SET acesso_valores_itens = 1 WHERE lower(email) = lower(?)", (ADMIN_EMAIL,))

    conn.commit()
    conn.close()
    return changed


if __name__ == '__main__':
    db_url = _get_database_url_from_env()
    if db_url.startswith('postgresql'):
        ok = migrate_postgres()
        print('migrate_postgres:', ok)
    else:
        ok = migrate_sqlite()
        print('migrate_sqlite:', ok)
