"""Migração para adicionar campos de suporte/BT e comprimento para fora nas tabelas de ferramentas.

Objetivo:
- suporte_bt: qual suporte/BT usado na ferramenta
- comprimento_fora: comprimento da ferramenta para fora

Compatível com PostgreSQL e SQLite.
"""

from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def _get_columns(conn, engine, table_name: str):
    if 'postgresql' in engine.dialect.name or 'postgres' in engine.dialect.name:
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name=:table
        """), {"table": table_name})
        return {row[0] for row in result.fetchall()}

    result = conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in result.fetchall()}


def _add_columns_if_missing(conn, engine, table_name: str):
    cols = _get_columns(conn, engine, table_name)
    changed = False

    if 'suporte_bt' not in cols:
        logger.info(f"Adicionando coluna suporte_bt à tabela {table_name}...")
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN suporte_bt VARCHAR(100)"))
        changed = True

    if 'comprimento_fora' not in cols:
        logger.info(f"Adicionando coluna comprimento_fora à tabela {table_name}...")
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN comprimento_fora VARCHAR(50)"))
        changed = True

    return changed


def upgrade(db_engine):
    """Adiciona suporte_bt/comprimento_fora em ferramenta_torno e ferramenta_centro."""
    try:
        with db_engine.connect() as conn:
            changed_any = False
            changed_any = _add_columns_if_missing(conn, db_engine, 'ferramenta_torno') or changed_any
            changed_any = _add_columns_if_missing(conn, db_engine, 'ferramenta_centro') or changed_any

            if changed_any:
                conn.commit()
                logger.info("✅ Colunas suporte_bt/comprimento_fora adicionadas com sucesso!")
            else:
                logger.info("✓ Colunas suporte_bt/comprimento_fora já existem em ferramenta_torno/ferramenta_centro")

        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar colunas suporte_bt/comprimento_fora em ferramentas: {str(e)}")
        return False


def downgrade(db_engine):
    """Remove colunas (quando suportado)."""
    try:
        with db_engine.connect() as conn:
            if 'postgresql' in db_engine.dialect.name or 'postgres' in db_engine.dialect.name:
                conn.execute(text("ALTER TABLE ferramenta_torno DROP COLUMN IF EXISTS suporte_bt"))
                conn.execute(text("ALTER TABLE ferramenta_torno DROP COLUMN IF EXISTS comprimento_fora"))
                conn.execute(text("ALTER TABLE ferramenta_centro DROP COLUMN IF EXISTS suporte_bt"))
                conn.execute(text("ALTER TABLE ferramenta_centro DROP COLUMN IF EXISTS comprimento_fora"))
                conn.commit()
                logger.info("✅ Colunas suporte_bt/comprimento_fora removidas com sucesso!")
            else:
                logger.warning("SQLite não suporta DROP COLUMN facilmente. Colunas não serão removidas.")
        return True
    except Exception as e:
        logger.error(f"Erro ao reverter migração suporte_bt/comprimento_fora: {str(e)}")
        return False
