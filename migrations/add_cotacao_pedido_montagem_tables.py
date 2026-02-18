"""Migração para criar tabelas de cotação/comparativo para Pedido de Montagem.
Este script pode ser executado diretamente ou importado pelo app.py
para ser executado durante a inicialização da aplicação.
"""

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


def migrate_postgres():
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
            return False

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

            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'cotacao_pedido_montagem'
                );
                """
            )
            if not cursor.fetchone()[0]:
                cursor.execute(
                    """
                    CREATE TABLE cotacao_pedido_montagem (
                        id SERIAL PRIMARY KEY,
                        pedido_montagem_id INTEGER NOT NULL,
                        fornecedor_id INTEGER NOT NULL,
                        data_criacao TIMESTAMP,
                        observacoes TEXT,
                        CONSTRAINT fk_cot_pm_pedido_montagem
                            FOREIGN KEY (pedido_montagem_id)
                            REFERENCES pedido_montagem(id)
                            ON DELETE CASCADE,
                        CONSTRAINT fk_cot_pm_fornecedor
                            FOREIGN KEY (fornecedor_id)
                            REFERENCES fornecedor(id),
                        CONSTRAINT uq_cotacao_pedido_montagem_fornecedor
                            UNIQUE (pedido_montagem_id, fornecedor_id)
                    );
                    """
                )
                logger.info("Tabela 'cotacao_pedido_montagem' criada (PostgreSQL)")

            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'cotacao_item_pedido_montagem'
                );
                """
            )
            if not cursor.fetchone()[0]:
                cursor.execute(
                    """
                    CREATE TABLE cotacao_item_pedido_montagem (
                        id SERIAL PRIMARY KEY,
                        cotacao_id INTEGER NOT NULL,
                        item_pedido_montagem_id INTEGER NOT NULL,
                        preco_total DOUBLE PRECISION,
                        preco_por_kg DOUBLE PRECISION,
                        preco_unitario DOUBLE PRECISION,
                        ipi_percent DOUBLE PRECISION,
                        prazo_entrega_dias INTEGER,
                        prazo_pagamento_dias INTEGER,
                        quantidade_escolhida INTEGER,
                        metros_escolhidos DOUBLE PRECISION,
                        CONSTRAINT fk_cot_item_pm_cotacao
                            FOREIGN KEY (cotacao_id)
                            REFERENCES cotacao_pedido_montagem(id)
                            ON DELETE CASCADE,
                        CONSTRAINT fk_cot_item_pm_item_pedido
                            FOREIGN KEY (item_pedido_montagem_id)
                            REFERENCES item_pedido_montagem(id)
                            ON DELETE CASCADE,
                        CONSTRAINT uq_cotacao_item_pedido_montagem
                            UNIQUE (cotacao_id, item_pedido_montagem_id)
                    );
                    """
                )
                logger.info("Tabela 'cotacao_item_pedido_montagem' criada (PostgreSQL)")

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
    conn = None
    try:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')

        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cotacao_pedido_montagem';")
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE cotacao_pedido_montagem (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_montagem_id INTEGER NOT NULL,
                    fornecedor_id INTEGER NOT NULL,
                    data_criacao DATETIME,
                    observacoes TEXT,
                    UNIQUE (pedido_montagem_id, fornecedor_id),
                    FOREIGN KEY(pedido_montagem_id) REFERENCES pedido_montagem(id) ON DELETE CASCADE,
                    FOREIGN KEY(fornecedor_id) REFERENCES fornecedor(id)
                )
                """
            )
            logger.info("Tabela 'cotacao_pedido_montagem' criada (SQLite)")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cotacao_item_pedido_montagem';")
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE cotacao_item_pedido_montagem (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cotacao_id INTEGER NOT NULL,
                    item_pedido_montagem_id INTEGER NOT NULL,
                    preco_total REAL,
                    preco_por_kg REAL,
                    preco_unitario REAL,
                    ipi_percent REAL,
                    prazo_entrega_dias INTEGER,
                    prazo_pagamento_dias INTEGER,
                    quantidade_escolhida INTEGER,
                    metros_escolhidos REAL,
                    UNIQUE (cotacao_id, item_pedido_montagem_id),
                    FOREIGN KEY(cotacao_id) REFERENCES cotacao_pedido_montagem(id) ON DELETE CASCADE,
                    FOREIGN KEY(item_pedido_montagem_id) REFERENCES item_pedido_montagem(id) ON DELETE CASCADE
                )
                """
            )
            logger.info("Tabela 'cotacao_item_pedido_montagem' criada (SQLite)")

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    logger.info("Iniciando migração para criar tabelas de comparativo (Pedido de Montagem)...")

    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True

    logger.error("Falha na migração!")
    return False


if __name__ == "__main__":
    run_migration()
