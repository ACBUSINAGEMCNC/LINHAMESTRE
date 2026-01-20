"""
Migração para adicionar a coluna categoria_trabalho na tabela gabarito_centro_usinagem.

Objetivo: permitir cadastrar gabaritos para várias categorias/tipos de serviço,
baseado nos Tipos de Trabalho (Trabalho.categoria).
"""

from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def upgrade(db_engine):
    """Adiciona a coluna categoria_trabalho na tabela gabarito_centro_usinagem (SQLite/PostgreSQL)."""
    try:
        with db_engine.connect() as conn:
            if 'postgresql' in db_engine.dialect.name or 'postgres' in db_engine.dialect.name:
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='gabarito_centro_usinagem' AND column_name='categoria_trabalho'
                """))
                exists = result.fetchone() is not None
            else:
                result = conn.execute(text("PRAGMA table_info(gabarito_centro_usinagem)"))
                columns = [row[1] for row in result.fetchall()]
                exists = 'categoria_trabalho' in columns

            if not exists:
                logger.info("Adicionando coluna categoria_trabalho à tabela gabarito_centro_usinagem...")
                conn.execute(text("ALTER TABLE gabarito_centro_usinagem ADD COLUMN categoria_trabalho VARCHAR(50)"))
                conn.commit()
                logger.info("✅ Coluna categoria_trabalho adicionada com sucesso!")
            else:
                logger.info("✓ Coluna categoria_trabalho já existe em gabarito_centro_usinagem")

        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar coluna categoria_trabalho em gabarito_centro_usinagem: {str(e)}")
        return False


def downgrade(db_engine):
    """Remove a coluna categoria_trabalho (quando suportado)."""
    try:
        with db_engine.connect() as conn:
            logger.info("Removendo coluna categoria_trabalho de gabarito_centro_usinagem...")
            if 'postgresql' in db_engine.dialect.name or 'postgres' in db_engine.dialect.name:
                conn.execute(text("ALTER TABLE gabarito_centro_usinagem DROP COLUMN IF EXISTS categoria_trabalho"))
                conn.commit()
                logger.info("✅ Coluna categoria_trabalho removida com sucesso!")
            else:
                logger.warning("SQLite não suporta DROP COLUMN facilmente. Coluna não será removida.")
        return True
    except Exception as e:
        logger.error(f"Erro ao reverter migração categoria_trabalho em gabarito_centro_usinagem: {str(e)}")
        return False
