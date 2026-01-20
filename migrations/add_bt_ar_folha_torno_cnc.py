"""Migração para adicionar as colunas bt e ar na tabela folha_processo_torno_cnc.

Objetivo:
- bt: campo para identificar BT
- ar: quantidade para fora do BT

Compatível com PostgreSQL e SQLite.
"""

from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def upgrade(db_engine):
    """Adiciona as colunas bt e ar na tabela folha_processo_torno_cnc (SQLite/PostgreSQL)."""
    try:
        with db_engine.connect() as conn:
            if 'postgresql' in db_engine.dialect.name or 'postgres' in db_engine.dialect.name:
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='folha_processo_torno_cnc'
                """))
                cols = {row[0] for row in result.fetchall()}
            else:
                result = conn.execute(text("PRAGMA table_info(folha_processo_torno_cnc)"))
                cols = {row[1] for row in result.fetchall()}

            changed = False

            if 'bt' not in cols:
                logger.info("Adicionando coluna bt à tabela folha_processo_torno_cnc...")
                conn.execute(text("ALTER TABLE folha_processo_torno_cnc ADD COLUMN bt VARCHAR(50)"))
                changed = True

            if 'ar' not in cols:
                logger.info("Adicionando coluna ar à tabela folha_processo_torno_cnc...")
                conn.execute(text("ALTER TABLE folha_processo_torno_cnc ADD COLUMN ar VARCHAR(50)"))
                changed = True

            if changed:
                conn.commit()
                logger.info("✅ Colunas bt/ar adicionadas com sucesso!")
            else:
                logger.info("✓ Colunas bt/ar já existem em folha_processo_torno_cnc")

        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar colunas bt/ar em folha_processo_torno_cnc: {str(e)}")
        return False


def downgrade(db_engine):
    """Remove colunas bt/ar (quando suportado)."""
    try:
        with db_engine.connect() as conn:
            logger.info("Removendo colunas bt/ar de folha_processo_torno_cnc...")
            if 'postgresql' in db_engine.dialect.name or 'postgres' in db_engine.dialect.name:
                conn.execute(text("ALTER TABLE folha_processo_torno_cnc DROP COLUMN IF EXISTS bt"))
                conn.execute(text("ALTER TABLE folha_processo_torno_cnc DROP COLUMN IF EXISTS ar"))
                conn.commit()
                logger.info("✅ Colunas bt/ar removidas com sucesso!")
            else:
                logger.warning("SQLite não suporta DROP COLUMN facilmente. Colunas não serão removidas.")
        return True
    except Exception as e:
        logger.error(f"Erro ao reverter migração bt/ar em folha_processo_torno_cnc: {str(e)}")
        return False
