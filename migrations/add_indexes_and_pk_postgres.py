"""\
Migração para melhorar performance no PostgreSQL (Supabase):

1) Criar índices para chaves estrangeiras sem índice cobrindo as colunas do FK.
2) Adicionar primary key nas tabelas *_backup que não possuem.

A migração é idempotente e pode ser chamada no startup (app.py).
"""

import os
import re
import logging
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


BACKUP_TABLES_NEED_PK = [
    'apontamento_producao_backup',
    'status_producao_os_backup',
]


def _safe_index_name(name: str, max_len: int = 63) -> str:
    # Postgres identifiers default limit: 63 bytes
    name = re.sub(r'[^a-zA-Z0-9_]+', '_', name)
    if len(name) <= max_len:
        return name
    # Mantém começo e fim para reduzir colisão
    return f"{name[:40]}_{name[-(max_len-41):]}"


def _ensure_backup_table_pk(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = 'public'
            AND table_name = %s
        );
        """,
        (table_name,),
    )
    if not cursor.fetchone()[0]:
        logger.info(f"Tabela public.{table_name} não existe, pulando PK")
        return False

    cursor.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM pg_constraint
          WHERE contype = 'p'
            AND conrelid = ('public.' || %s)::regclass
        );
        """,
        (table_name,),
    )
    if cursor.fetchone()[0]:
        logger.info(f"Tabela public.{table_name} já possui primary key")
        return True

    # Garante coluna id
    cursor.execute(
        sql.SQL("ALTER TABLE public.{} ADD COLUMN IF NOT EXISTS id BIGSERIAL;").format(
            sql.Identifier(table_name)
        )
    )

    # Adiciona PK
    pk_name = _safe_index_name(f"{table_name}_pkey")
    cursor.execute(
        sql.SQL("ALTER TABLE public.{} ADD CONSTRAINT {} PRIMARY KEY (id);").format(
            sql.Identifier(table_name),
            sql.Identifier(pk_name),
        )
    )
    logger.info(f"Primary key adicionada em public.{table_name} (coluna id)")
    return True


def _create_indexes_for_unindexed_fks(cursor) -> int:
    # Busca FKs no schema public e marca se já existe índice cobrindo as colunas do FK
    cursor.execute(
        """
        WITH fks AS (
          SELECT
            c.oid AS constraint_oid,
            c.conname,
            n.nspname AS schema_name,
            cl.relname AS table_name,
            c.conrelid,
            c.conkey
          FROM pg_constraint c
          JOIN pg_class cl ON cl.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = cl.relnamespace
          WHERE c.contype = 'f'
            AND n.nspname = 'public'
        ), fk_cols AS (
          SELECT
            f.constraint_oid,
            f.conname,
            f.schema_name,
            f.table_name,
            f.conrelid,
            f.conkey,
            ARRAY_AGG(a.attname ORDER BY k.ord) AS col_names,
            ARRAY_AGG(k.attnum ORDER BY k.ord) AS attnums
          FROM fks f
          JOIN LATERAL unnest(f.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
          JOIN pg_attribute a ON a.attrelid = f.conrelid AND a.attnum = k.attnum
          GROUP BY f.constraint_oid, f.conname, f.schema_name, f.table_name, f.conrelid, f.conkey
        ), fk_needs_index AS (
          SELECT
            fk_cols.*,
            EXISTS (
              SELECT 1
              FROM pg_index i
              WHERE i.indrelid = fk_cols.conrelid
                AND i.indisvalid
                AND i.indisready
                AND i.indpred IS NULL
                AND i.indexprs IS NULL
                AND i.indkey[0:array_length(fk_cols.attnums,1)-1] = fk_cols.attnums
            ) AS has_covering_index
          FROM fk_cols
        )
        SELECT schema_name, table_name, conname, col_names
        FROM fk_needs_index
        WHERE NOT has_covering_index
        ORDER BY schema_name, table_name, conname;
        """
    )

    rows = cursor.fetchall()
    created = 0

    for schema_name, table_name, conname, col_names in rows:
        idx_name = _safe_index_name(f"idx_{table_name}_{conname}")

        cursor.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {}.{} ({});").format(
                sql.Identifier(idx_name),
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
                sql.SQL(', ').join(sql.Identifier(c) for c in col_names),
            )
        )
        logger.info(
            f"Índice criado/verificado: {schema_name}.{table_name} ({', '.join(col_names)}) -> {idx_name}"
        )
        created += 1

    if created == 0:
        logger.info("Nenhum FK sem índice encontrado (ou já estão cobertos).")

    return created


def migrate_postgres() -> bool:
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
            return False

        if not db_url.lower().startswith('postgres'):
            logger.info("DATABASE_URL não é PostgreSQL, pulando migração")
            return False

        conn = psycopg2.connect(db_url)
        conn.autocommit = True

        with conn.cursor() as cursor:
            _create_indexes_for_unindexed_fks(cursor)

            for table_name in BACKUP_TABLES_NEED_PK:
                _ensure_backup_table_pk(cursor, table_name)

        return True

    except Exception as e:
        logger.error(f"Erro na migração de índices/PK (PostgreSQL): {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def migrate_sqlite() -> bool:
    # SQLite: essas recomendações são do Postgres/Supabase
    logger.info("SQLite detectado: migração de índices/PK do Postgres não se aplica")
    return True


def run_migration() -> bool:
    logger.info("Iniciando migração: índices de FKs e PK em tabelas backup...")
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração de índices/PK concluída")
        return True

    logger.error("Falha na migração de índices/PK")
    return False


if __name__ == '__main__':
    run_migration()
