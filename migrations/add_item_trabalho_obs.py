"""
Migration: Adicionar coluna obs na tabela item_trabalho
Para permitir OBS específica por item/trabalho (além da do tipo de trabalho)
"""

import logging

logger = logging.getLogger(__name__)

def run_migration():
    """Adiciona coluna obs na tabela item_trabalho"""
    try:
        from app import app
        from models import db
        
        with app.app_context():
            # Detectar se é PostgreSQL (Supabase) ou SQLite
            dialect = db.engine.dialect.name
            
            if dialect == 'postgresql':
                # PostgreSQL: verificar se coluna existe
                from sqlalchemy import text
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'item_trabalho' AND column_name = 'obs'
                """))
                
                if result.fetchone():
                    logger.info("[MIGRATION] Coluna 'obs' já existe em item_trabalho (PostgreSQL)")
                    return True
                
                # Adicionar coluna
                db.session.execute(text("""
                    ALTER TABLE item_trabalho 
                    ADD COLUMN obs TEXT
                """))
                db.session.commit()
                logger.info("[MIGRATION] Coluna 'obs' adicionada à tabela item_trabalho (PostgreSQL)")
                
            elif dialect == 'sqlite':
                # SQLite: usar PRAGMA para verificar colunas
                from sqlalchemy import text, inspect
                
                inspector = inspect(db.engine)
                columns = inspector.get_columns('item_trabalho')
                column_names = [col['name'] for col in columns]
                
                if 'obs' in column_names:
                    logger.info("[MIGRATION] Coluna 'obs' já existe em item_trabalho (SQLite)")
                    return True
                
                # SQLite não suporta ADD COLUMN diretamente em todas versões, mas vamos tentar
                try:
                    db.session.execute(text("""
                        ALTER TABLE item_trabalho 
                        ADD COLUMN obs TEXT
                    """))
                    db.session.commit()
                    logger.info("[MIGRATION] Coluna 'obs' adicionada à tabela item_trabalho (SQLite)")
                except Exception as e:
                    logger.warning(f"[MIGRATION] SQLite add column falhou (pode ser versão antiga): {e}")
                    return False
            else:
                logger.warning(f"[MIGRATION] Dialeto não suportado: {dialect}")
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"[MIGRATION] Erro ao adicionar coluna obs em item_trabalho: {e}")
        return False

if __name__ == "__main__":
    run_migration()
