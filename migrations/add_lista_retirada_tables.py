"""
Migration: Criar tabelas para Lista de Retirada permanente
Substitui armazenamento em sessão por banco de dados
"""
import os
import logging

logger = logging.getLogger(__name__)


def _get_database_url_from_env():
    """Retorna DATABASE_URL do ambiente."""
    return os.getenv('DATABASE_URL')


def migrate_postgres() -> bool:
    """Cria tabelas lista_retirada e lista_retirada_item (Postgres/Supabase)."""
    from sqlalchemy import create_engine, text
    
    database_url = _get_database_url_from_env()
    if not database_url:
        logger.warning("DATABASE_URL não encontrada, pulando migração lista_retirada.")
        return False
    
    engine = create_engine(database_url)
    
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS lista_retirada (
            id SERIAL PRIMARY KEY,
            numero VARCHAR(20) UNIQUE NOT NULL,
            referencia VARCHAR(200),
            responsavel VARCHAR(200),
            observacao TEXT,
            status VARCHAR(20) DEFAULT 'rascunho',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            baixado_em TIMESTAMP,
            criado_por_id INTEGER REFERENCES usuario(id),
            baixado_por_id INTEGER REFERENCES usuario(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lista_retirada_item (
            id SERIAL PRIMARY KEY,
            lista_id INTEGER NOT NULL REFERENCES lista_retirada(id) ON DELETE CASCADE,
            estoque_id INTEGER NOT NULL REFERENCES estoque_pecas(id),
            quantidade INTEGER NOT NULL,
            observacao TEXT,
            ordem INTEGER DEFAULT 0
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_lista_retirada_numero ON lista_retirada(numero)",
        "CREATE INDEX IF NOT EXISTS idx_lista_retirada_status ON lista_retirada(status)",
        "CREATE INDEX IF NOT EXISTS idx_lista_retirada_criado_em ON lista_retirada(criado_em DESC)",
        "CREATE INDEX IF NOT EXISTS idx_lista_retirada_item_lista_id ON lista_retirada_item(lista_id)",
    ]
    
    try:
        with engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))
        
        logger.info("✅ Tabelas lista_retirada criadas com sucesso")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabelas lista_retirada: {e}")
        return False


def migrate_sqlite(db_path: str = None) -> bool:
    """Cria tabelas lista_retirada e lista_retirada_item (SQLite)."""
    import sqlite3
    
    if not db_path:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(db_dir, '..', 'database.db')
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lista_retirada (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE NOT NULL,
                referencia TEXT,
                responsavel TEXT,
                observacao TEXT,
                status TEXT DEFAULT 'rascunho',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                baixado_em TIMESTAMP,
                criado_por_id INTEGER REFERENCES usuario(id),
                baixado_por_id INTEGER REFERENCES usuario(id)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lista_retirada_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lista_id INTEGER NOT NULL REFERENCES lista_retirada(id) ON DELETE CASCADE,
                estoque_id INTEGER NOT NULL REFERENCES estoque_pecas(id),
                quantidade INTEGER NOT NULL,
                observacao TEXT,
                ordem INTEGER DEFAULT 0
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lista_retirada_numero ON lista_retirada(numero)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lista_retirada_status ON lista_retirada(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lista_retirada_item_lista_id ON lista_retirada_item(lista_id)")
        
        conn.commit()
        logger.info("✅ Tabelas lista_retirada criadas com sucesso (SQLite)")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabelas lista_retirada (SQLite): {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    migrate_postgres()
