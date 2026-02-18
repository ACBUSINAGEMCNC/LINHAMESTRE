"""Migração para criar tabelas de Pedido de Montagem e adicionar referência em Pedido.
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
except Exception:  # psycopg2 pode não estar instalado em ambiente SQLite local
    psycopg2 = None
    sql = None

try:
    import psycopg
except Exception:  # psycopg3 pode não estar instalado
    psycopg = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_postgres():
    """Cria tabelas pedido_montagem/item_pedido_montagem e adiciona coluna numero_pedido_montagem em pedido (PostgreSQL)."""
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
            return False

        # Normalizar URLs SQLAlchemy (postgresql+psycopg://) para drivers nativos
        if db_url.startswith('postgresql+psycopg://'):
            db_url = 'postgresql://' + db_url[len('postgresql+psycopg://'):]
        elif db_url.startswith('postgres://'):
            db_url = 'postgresql://' + db_url[len('postgres://'):]

        if psycopg is not None:
            conn = psycopg.connect(db_url)
            conn.autocommit = True
            cursor_ctx = conn.cursor()
            close_cursor = True
        elif psycopg2 is not None:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cursor_ctx = conn.cursor()
            close_cursor = True
        else:
            logger.warning("psycopg/psycopg2 não estão disponíveis, pulando migração PostgreSQL")
            return False

        try:
            cursor = cursor_ctx
            # Coluna em pedido
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'pedido' AND column_name = 'numero_pedido_montagem'
                );
                """
            )
            if not cursor.fetchone()[0]:
                cursor.execute(
                    """
                    ALTER TABLE pedido
                    ADD COLUMN IF NOT EXISTS numero_pedido_montagem VARCHAR(50);
                    """
                )
                logger.info("Coluna 'numero_pedido_montagem' adicionada com sucesso à tabela 'pedido' (PostgreSQL)")
            else:
                logger.info("Coluna 'numero_pedido_montagem' já existe na tabela 'pedido' (PostgreSQL)")

            # Tabela pedido_montagem
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'pedido_montagem'
                );
                """
            )
            if not cursor.fetchone()[0]:
                cursor.execute(
                    """
                    CREATE TABLE pedido_montagem (
                        id SERIAL PRIMARY KEY,
                        numero VARCHAR(20) UNIQUE,
                        data_criacao DATE
                    );
                    """
                )
                logger.info("Tabela 'pedido_montagem' criada (PostgreSQL)")

            # Tabela item_pedido_montagem
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'item_pedido_montagem'
                );
                """
            )
            if not cursor.fetchone()[0]:
                cursor.execute(
                    """
                    CREATE TABLE item_pedido_montagem (
                        id SERIAL PRIMARY KEY,
                        pedido_montagem_id INTEGER NOT NULL,
                        item_id INTEGER NOT NULL,
                        quantidade INTEGER NOT NULL DEFAULT 1,
                        CONSTRAINT fk_item_pedido_montagem_pedido_montagem
                            FOREIGN KEY (pedido_montagem_id)
                            REFERENCES pedido_montagem(id)
                            ON DELETE CASCADE,
                        CONSTRAINT fk_item_pedido_montagem_item
                            FOREIGN KEY (item_id)
                            REFERENCES item(id)
                    );
                    """
                )
                logger.info("Tabela 'item_pedido_montagem' criada (PostgreSQL)")

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
    """Cria tabelas pedido_montagem/item_pedido_montagem e adiciona coluna numero_pedido_montagem em pedido (SQLite)."""
    conn = None
    try:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')

        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Coluna em pedido
        cursor.execute("PRAGMA table_info(pedido)")
        pedido_columns = [column[1] for column in cursor.fetchall()]
        if 'numero_pedido_montagem' not in pedido_columns:
            cursor.execute("ALTER TABLE pedido ADD COLUMN numero_pedido_montagem VARCHAR(50)")
            logger.info("Coluna 'numero_pedido_montagem' adicionada com sucesso à tabela 'pedido' (SQLite)")
        else:
            logger.info("Coluna 'numero_pedido_montagem' já existe na tabela 'pedido' (SQLite)")

        # Tabela pedido_montagem
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pedido_montagem';")
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE pedido_montagem (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero VARCHAR(20) UNIQUE,
                    data_criacao DATE
                )
                """
            )
            logger.info("Tabela 'pedido_montagem' criada (SQLite)")

        # Tabela item_pedido_montagem
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_pedido_montagem';")
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE item_pedido_montagem (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_montagem_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    quantidade INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(pedido_montagem_id) REFERENCES pedido_montagem(id) ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES item(id)
                )
                """
            )
            logger.info("Tabela 'item_pedido_montagem' criada (SQLite)")

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    logger.info("Iniciando migração para criar Pedido de Montagem...")

    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True

    logger.error("Falha na migração!")
    return False


if __name__ == "__main__":
    run_migration()
