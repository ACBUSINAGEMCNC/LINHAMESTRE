"""Migration para adicionar coluna status na tabela pedido_montagem."""
from sqlalchemy import text


def migrate_postgres():
    try:
        from app import app
        from models import db
        with app.app_context():
            with db.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='pedido_montagem' AND column_name='status'"
                ))
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE pedido_montagem ADD COLUMN status VARCHAR(20) DEFAULT 'aberto'"))
                    conn.commit()
                    print("[migration] Coluna status adicionada em pedido_montagem (PostgreSQL).")
                else:
                    print("[migration] Coluna status já existe em pedido_montagem (PostgreSQL).")
    except Exception as e:
        print(f"[migration] Erro ao adicionar status em pedido_montagem (PostgreSQL): {e}")


def migrate_sqlite():
    try:
        from app import app
        from models import db
        with app.app_context():
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(pedido_montagem)"))
                cols = [row[1] for row in result.fetchall()]
                if 'status' not in cols:
                    conn.execute(text("ALTER TABLE pedido_montagem ADD COLUMN status VARCHAR(20) DEFAULT 'aberto'"))
                    conn.commit()
                    print("[migration] Coluna status adicionada em pedido_montagem (SQLite).")
                else:
                    print("[migration] Coluna status já existe em pedido_montagem (SQLite).")
    except Exception as e:
        print(f"[migration] Erro ao adicionar status em pedido_montagem (SQLite): {e}")
