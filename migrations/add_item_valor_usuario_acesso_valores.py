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


def _pg_column_exists(conn, table_name: str, column_name: str) -> bool:
    from sqlalchemy import text

    result = conn.execute(text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
          AND column_name = :column_name
        LIMIT 1
    """), {
        'table_name': table_name,
        'column_name': column_name,
    }).scalar()
    return bool(result)


def migrate_postgres() -> bool:
    from sqlalchemy import create_engine, text

    database_url = _get_database_url_from_env()
    if not database_url:
        return False

    engine = create_engine(database_url)
    with engine.begin() as conn:
        if not _pg_column_exists(conn, 'item', 'valor_item'):
            conn.execute(text("ALTER TABLE item ADD COLUMN valor_item DOUBLE PRECISION DEFAULT 0"))
        if not _pg_column_exists(conn, 'item', 'valor_material'):
            conn.execute(text("ALTER TABLE item ADD COLUMN valor_material DOUBLE PRECISION DEFAULT 0"))
        if not _pg_column_exists(conn, 'item', 'outros_custos'):
            conn.execute(text("ALTER TABLE item ADD COLUMN outros_custos DOUBLE PRECISION DEFAULT 0"))
        if not _pg_column_exists(conn, 'item', 'imposto_percentual'):
            conn.execute(text("ALTER TABLE item ADD COLUMN imposto_percentual DOUBLE PRECISION DEFAULT 0"))
        if not _pg_column_exists(conn, 'usuario', 'acesso_valores_itens'):
            conn.execute(text("ALTER TABLE usuario ADD COLUMN acesso_valores_itens BOOLEAN DEFAULT FALSE"))
        conn.execute(text(f"UPDATE usuario SET acesso_valores_itens = TRUE WHERE lower(email) = lower('{ADMIN_EMAIL}')"))
    return True


def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def _resolve_sqlite_db_path(db_path: str = None) -> str:
    if db_path:
        return os.path.abspath(db_path)

    env_db_dir = os.getenv('DB_DIR', '').strip()
    if env_db_dir:
        return os.path.abspath(os.path.join(env_db_dir, 'database.db'))

    database_url = _get_database_url_from_env()
    if database_url.lower().startswith('sqlite:///'):
        raw_path = database_url[len('sqlite:///'):]
        if raw_path:
            return os.path.abspath(raw_path)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(repo_root, 'database.db'))


def migrate_sqlite(db_path: str = None) -> bool:
    db_path = _resolve_sqlite_db_path(db_path)
    if not os.path.exists(db_path):
        return False

    conn = sqlite3.connect(db_path)
    try:
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

        if _table_exists(cur, 'usuario') and _has_column('usuario', 'acesso_valores_itens'):
            cur.execute("UPDATE usuario SET acesso_valores_itens = 1 WHERE lower(email) = lower(?)", (ADMIN_EMAIL,))

        conn.commit()
        return changed
    finally:
        conn.close()


if __name__ == '__main__':
    db_url = _get_database_url_from_env()
    if db_url.startswith('postgresql'):
        ok = migrate_postgres()
        print('migrate_postgres:', ok)
    else:
        ok = migrate_sqlite()
        print('migrate_sqlite:', ok)
