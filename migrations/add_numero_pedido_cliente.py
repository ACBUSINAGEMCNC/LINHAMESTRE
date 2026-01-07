"""
Migração para adicionar o campo numero_pedido_cliente na tabela pedido
"""
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

def upgrade(db_engine):
    """Adiciona a coluna numero_pedido_cliente"""
    try:
        with db_engine.connect() as conn:
            # Verificar se a coluna já existe
            if 'postgresql' in db_engine.dialect.name or 'postgres' in db_engine.dialect.name:
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='pedido' AND column_name='numero_pedido_cliente'
                """))
                exists = result.fetchone() is not None
            else:  # SQLite
                result = conn.execute(text("PRAGMA table_info(pedido)"))
                columns = [row[1] for row in result.fetchall()]
                exists = 'numero_pedido_cliente' in columns
            
            if not exists:
                logger.info("Adicionando coluna numero_pedido_cliente à tabela pedido...")
                conn.execute(text("ALTER TABLE pedido ADD COLUMN numero_pedido_cliente VARCHAR(100)"))
                conn.commit()
                logger.info("✅ Coluna numero_pedido_cliente adicionada com sucesso!")
            else:
                logger.info("✓ Coluna numero_pedido_cliente já existe")
                
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar coluna numero_pedido_cliente: {str(e)}")
        return False

def downgrade(db_engine):
    """Remove a coluna numero_pedido_cliente"""
    try:
        with db_engine.connect() as conn:
            logger.info("Removendo coluna numero_pedido_cliente da tabela pedido...")
            if 'postgresql' in db_engine.dialect.name or 'postgres' in db_engine.dialect.name:
                conn.execute(text("ALTER TABLE pedido DROP COLUMN IF EXISTS numero_pedido_cliente"))
            else:  # SQLite não suporta DROP COLUMN facilmente
                logger.warning("SQLite não suporta DROP COLUMN. Coluna não será removida.")
            conn.commit()
            logger.info("✅ Migração revertida com sucesso!")
        return True
    except Exception as e:
        logger.error(f"Erro ao reverter migração: {str(e)}")
        return False
