"""
Migração para criar tabelas de Proteção (EPI/EPC) e relacionamentos com Trabalho e ItemTrabalho.

- protecao
- trabalho_protecao (N:N)
- item_trabalho_protecao (snapshot no item)

Este script pode ser executado diretamente ou importado pelo app.py.
"""

import os
import logging
import sqlite3

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _get_db_url():
    load_dotenv()
    return os.getenv('DATABASE_URL')


def migrate_postgres():
    """Cria as tabelas no PostgreSQL (Supabase) se não existirem."""
    db_url = _get_db_url()
    if not db_url:
        logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
        return False

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True

        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS protecao (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(120) NOT NULL UNIQUE,
                    tipo VARCHAR(10) NOT NULL,
                    descricao TEXT
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trabalho_protecao (
                    id SERIAL PRIMARY KEY,
                    trabalho_id INTEGER NOT NULL REFERENCES trabalho(id) ON DELETE CASCADE,
                    protecao_id INTEGER NOT NULL REFERENCES protecao(id) ON DELETE CASCADE,
                    CONSTRAINT uq_trabalho_protecao UNIQUE (trabalho_id, protecao_id)
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS item_trabalho_protecao (
                    id SERIAL PRIMARY KEY,
                    item_trabalho_id INTEGER NOT NULL REFERENCES item_trabalho(id) ON DELETE CASCADE,
                    protecao_id INTEGER NOT NULL REFERENCES protecao(id) ON DELETE CASCADE,
                    CONSTRAINT uq_item_trabalho_protecao UNIQUE (item_trabalho_id, protecao_id)
                );
                """
            )

        logger.info("Tabelas protecao/trabalho_protecao/item_trabalho_protecao verificadas/criadas (PostgreSQL).")
        return True

    except Exception as e:
        logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def migrate_sqlite():
    """Cria as tabelas no SQLite se não existirem."""
    conn = None
    try:
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')

        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS protecao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(120) NOT NULL UNIQUE,
                tipo VARCHAR(10) NOT NULL,
                descricao TEXT
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trabalho_protecao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trabalho_id INTEGER NOT NULL,
                protecao_id INTEGER NOT NULL,
                UNIQUE (trabalho_id, protecao_id),
                FOREIGN KEY(trabalho_id) REFERENCES trabalho(id) ON DELETE CASCADE,
                FOREIGN KEY(protecao_id) REFERENCES protecao(id) ON DELETE CASCADE
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS item_trabalho_protecao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_trabalho_id INTEGER NOT NULL,
                protecao_id INTEGER NOT NULL,
                UNIQUE (item_trabalho_id, protecao_id),
                FOREIGN KEY(item_trabalho_id) REFERENCES item_trabalho(id) ON DELETE CASCADE,
                FOREIGN KEY(protecao_id) REFERENCES protecao(id) ON DELETE CASCADE
            );
            """
        )

        conn.commit()
        logger.info("Tabelas protecao/trabalho_protecao/item_trabalho_protecao verificadas/criadas (SQLite).")
        return True

    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    logger.info("Iniciando migração para tabelas de Proteção (EPI/EPC)...")
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True

    logger.error("Falha na migração!")
    return False


if __name__ == '__main__':
    run_migration()
