"""Migração para suportar linhas avulsas de material no item_pedido_material.
Adiciona descricao_material e item_origem_id e torna material_id opcional.
"""

import os
import logging
import sqlite3
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2 import sql
except Exception:
    psycopg2 = None
    sql = None

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
            cursor = conn.cursor()
        elif psycopg2 is not None and sql is not None:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cursor = conn.cursor()
        else:
            logger.warning("psycopg/psycopg2 não estão disponíveis, pulando migração PostgreSQL")
            return False

        try:
            cursor.execute(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'item_pedido_material'
                  AND column_name IN ('material_id', 'descricao_material', 'item_origem_id');
                """
            )
            rows = {row[0]: row[1] for row in cursor.fetchall()}

            if 'descricao_material' not in rows:
                cursor.execute("ALTER TABLE item_pedido_material ADD COLUMN IF NOT EXISTS descricao_material VARCHAR(255);")
                logger.info("Coluna 'descricao_material' adicionada em item_pedido_material (PostgreSQL)")

            if 'item_origem_id' not in rows:
                cursor.execute("ALTER TABLE item_pedido_material ADD COLUMN IF NOT EXISTS item_origem_id INTEGER;")
                logger.info("Coluna 'item_origem_id' adicionada em item_pedido_material (PostgreSQL)")

            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints
                        WHERE constraint_name = 'fk_item_pedido_material_item_origem_id'
                    ) THEN
                        ALTER TABLE item_pedido_material
                        ADD CONSTRAINT fk_item_pedido_material_item_origem_id
                        FOREIGN KEY (item_origem_id) REFERENCES item(id);
                    END IF;
                END
                $$;
                """
            )

            if rows.get('material_id') == 'NO':
                cursor.execute("ALTER TABLE item_pedido_material ALTER COLUMN material_id DROP NOT NULL;")
                logger.info("Coluna 'material_id' ajustada para aceitar NULL em item_pedido_material (PostgreSQL)")

            return True
        finally:
            cursor.close()
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
        cursor.execute("PRAGMA table_info(item_pedido_material)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        changed = False

        if 'descricao_material' not in column_names:
            cursor.execute("ALTER TABLE item_pedido_material ADD COLUMN descricao_material VARCHAR(255)")
            changed = True
            logger.info("Coluna 'descricao_material' adicionada em item_pedido_material (SQLite)")

        if 'item_origem_id' not in column_names:
            cursor.execute("ALTER TABLE item_pedido_material ADD COLUMN item_origem_id INTEGER")
            changed = True
            logger.info("Coluna 'item_origem_id' adicionada em item_pedido_material (SQLite)")

        material_col = next((col for col in columns if col[1] == 'material_id'), None)
        needs_rebuild = bool(material_col and material_col[3] == 1)

        if needs_rebuild:
            cursor.execute("PRAGMA foreign_keys=OFF")
            cursor.execute("ALTER TABLE item_pedido_material RENAME TO item_pedido_material_old")
            cursor.execute(
                """
                CREATE TABLE item_pedido_material (
                    id INTEGER NOT NULL PRIMARY KEY,
                    pedido_material_id INTEGER NOT NULL,
                    material_id INTEGER,
                    comprimento FLOAT,
                    quantidade INTEGER,
                    sufixo VARCHAR(10),
                    descricao_material VARCHAR(255),
                    item_origem_id INTEGER,
                    FOREIGN KEY(pedido_material_id) REFERENCES pedido_material (id),
                    FOREIGN KEY(material_id) REFERENCES material (id),
                    FOREIGN KEY(item_origem_id) REFERENCES item (id)
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO item_pedido_material (id, pedido_material_id, material_id, comprimento, quantidade, sufixo, descricao_material, item_origem_id)
                SELECT id, pedido_material_id, material_id, comprimento, quantidade, sufixo, descricao_material, item_origem_id
                FROM item_pedido_material_old
                """
            )
            cursor.execute("DROP TABLE item_pedido_material_old")
            cursor.execute("PRAGMA foreign_keys=ON")
            changed = True
            logger.info("Tabela item_pedido_material recriada para permitir material_id nulo (SQLite)")

        if changed:
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def run_migration():
    logger.info("Iniciando migração de item_pedido_material para suporte a laser...")
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()
    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True
    logger.error("Falha na migração!")
    return False


if __name__ == '__main__':
    run_migration()
