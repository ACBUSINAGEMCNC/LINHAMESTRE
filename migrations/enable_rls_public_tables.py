"""
Migração para habilitar RLS (Row Level Security) em tabelas do schema public
expostas via PostgREST no Supabase.

Sem políticas, o acesso via roles anon/authenticated fica bloqueado por padrão.
O usuário postgres (usado pela app via DATABASE_URL) continua com acesso.
"""

import os
import logging
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


PUBLIC_TABLES = [
    'medida_critica',
    'imagem_peca_processo',
    'nova_folha_processo',
    'item_composto',
    'audit_log',
    'fornecedor',
    'cotacao_pedido_material',
    'cotacao_item_pedido_material',
    'pedido_montagem',
    'item_pedido_montagem',
    'cotacao_pedido_montagem',
    'cotacao_item_pedido_montagem',
    'folha_processo_serra',
    'folha_processo_torno_cnc',
    'folha_processo_centro_usinagem',
    'folha_processo_manual_acabamento',
    'ferramenta_torno',
    'ferramenta_centro',
    'imagem_processo_geral',
]


def migrate_postgres():
    """Habilita RLS nas tabelas listadas (PostgreSQL/Supabase)."""
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
            return False

        if not db_url.lower().startswith('postgres'):
            logger.info("DATABASE_URL não é PostgreSQL, pulando migração RLS")
            return False

        conn = psycopg2.connect(db_url)
        conn.autocommit = True

        with conn.cursor() as cursor:
            for table_name in PUBLIC_TABLES:
                # Só aplica se a tabela existir no schema public
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
                exists = cursor.fetchone()[0]
                if not exists:
                    logger.info(f"Tabela public.{table_name} não encontrada, pulando")
                    continue

                cursor.execute(
                    sql.SQL("ALTER TABLE public.{} ENABLE ROW LEVEL SECURITY;").format(
                        sql.Identifier(table_name)
                    )
                )
                cursor.execute(
                    sql.SQL("ALTER TABLE public.{} FORCE ROW LEVEL SECURITY;").format(
                        sql.Identifier(table_name)
                    )
                )
                logger.info(f"RLS habilitado em public.{table_name}")

        return True

    except Exception as e:
        logger.error(f"Erro ao habilitar RLS no PostgreSQL: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


def migrate_sqlite():
    """SQLite não possui RLS (no-op)."""
    logger.info("SQLite detectado: migração de RLS não se aplica")
    return True


def run_migration():
    logger.info("Iniciando migração: habilitar RLS nas tabelas public...")
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()

    if pg_success or sqlite_success:
        logger.info("Migração de RLS concluída")
        return True

    logger.error("Falha na migração de RLS")
    return False


if __name__ == "__main__":
    run_migration()
