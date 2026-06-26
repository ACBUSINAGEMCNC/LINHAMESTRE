"""
Migration: Criar tabelas para módulo de Uso e Consumo
item_consumo, pedido_consumo, item_pedido_consumo
"""
import os
import logging

logger = logging.getLogger(__name__)


def _get_database_url_from_env():
    return os.getenv('DATABASE_URL')


def migrate_postgres() -> bool:
    from sqlalchemy import create_engine, text

    database_url = _get_database_url_from_env()
    if not database_url:
        logger.warning("DATABASE_URL não encontrada, pulando migração consumo.")
        return False

    engine = create_engine(database_url)

    stmts = [
        """
        CREATE TABLE IF NOT EXISTS item_consumo (
            id SERIAL PRIMARY KEY,
            codigo VARCHAR(30) UNIQUE NOT NULL,
            nome VARCHAR(150) NOT NULL,
            descricao TEXT,
            unidade VARCHAR(20) DEFAULT 'un',
            categoria VARCHAR(60),
            ativo BOOLEAN DEFAULT TRUE,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pedido_consumo (
            id SERIAL PRIMARY KEY,
            numero VARCHAR(20) UNIQUE NOT NULL,
            titulo VARCHAR(150),
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            observacoes TEXT,
            aprovado_em TIMESTAMP,
            aprovado_por_id INTEGER REFERENCES usuario(id),
            aprovado_por_nome VARCHAR(120)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS item_pedido_consumo (
            id SERIAL PRIMARY KEY,
            pedido_consumo_id INTEGER NOT NULL REFERENCES pedido_consumo(id) ON DELETE CASCADE,
            item_consumo_id INTEGER REFERENCES item_consumo(id),
            item_id INTEGER REFERENCES item(id),
            descricao_livre VARCHAR(255),
            quantidade FLOAT DEFAULT 1,
            unidade VARCHAR(20) DEFAULT 'un',
            observacao VARCHAR(255)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_item_consumo_ativo ON item_consumo(ativo)",
        "CREATE INDEX IF NOT EXISTS idx_pedido_consumo_numero ON pedido_consumo(numero)",
        "CREATE INDEX IF NOT EXISTS idx_item_pedido_consumo_pedido ON item_pedido_consumo(pedido_consumo_id)",
    ]

    try:
        with engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))
        logger.info("✅ Tabelas consumo criadas com sucesso")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabelas consumo: {e}")
        return False


def migrate_sqlite(db_path: str = None) -> bool:
    import sqlite3

    if not db_path:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(db_dir, '..', 'database.db')

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS item_consumo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nome TEXT NOT NULL,
                descricao TEXT,
                unidade TEXT DEFAULT 'un',
                categoria TEXT,
                ativo INTEGER DEFAULT 1,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pedido_consumo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE NOT NULL,
                titulo TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                observacoes TEXT,
                aprovado_em TIMESTAMP,
                aprovado_por_id INTEGER REFERENCES usuario(id),
                aprovado_por_nome TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS item_pedido_consumo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_consumo_id INTEGER NOT NULL REFERENCES pedido_consumo(id) ON DELETE CASCADE,
                item_consumo_id INTEGER REFERENCES item_consumo(id),
                item_id INTEGER REFERENCES item(id),
                descricao_livre TEXT,
                quantidade REAL DEFAULT 1,
                unidade TEXT DEFAULT 'un',
                observacao TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_item_consumo_ativo ON item_consumo(ativo)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pedido_consumo_numero ON pedido_consumo(numero)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_item_pedido_consumo_pedido ON item_pedido_consumo(pedido_consumo_id)")

        conn.commit()
        logger.info("✅ Tabelas consumo criadas com sucesso (SQLite)")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabelas consumo (SQLite): {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    migrate_postgres()
