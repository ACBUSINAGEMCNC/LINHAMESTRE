"""
Migração para adicionar campo pode_gerenciar_apontamentos na tabela usuario
"""
import os
import sys

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate_postgresql_engine(engine):
    """Migração para PostgreSQL usando SQLAlchemy engine"""
    from sqlalchemy import text
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Iniciando verificação da coluna pode_gerenciar_apontamentos...")
        
        with engine.connect() as conn:
            # Verificar se a coluna já existe
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='usuario' AND column_name='pode_gerenciar_apontamentos'
            """))
            
            if result.fetchone() is None:
                logger.info("Coluna pode_gerenciar_apontamentos não encontrada. Adicionando...")
                conn.execute(text("""
                    ALTER TABLE usuario 
                    ADD COLUMN pode_gerenciar_apontamentos BOOLEAN DEFAULT FALSE
                """))
                conn.commit()
                logger.info("✅ Coluna pode_gerenciar_apontamentos adicionada com sucesso!")
                return True
            else:
                logger.info("ℹ️ Coluna pode_gerenciar_apontamentos já existe.")
                return True
                
    except Exception as e:
        logger.error(f"❌ Erro na migração PostgreSQL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def migrate_postgresql(conn):
    """Migração para PostgreSQL"""
    cursor = conn.cursor()
    try:
        # Verificar se a coluna já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='usuario' AND column_name='pode_gerenciar_apontamentos'
        """)
        
        if cursor.fetchone() is None:
            print("Adicionando coluna pode_gerenciar_apontamentos na tabela usuario...")
            cursor.execute("""
                ALTER TABLE usuario 
                ADD COLUMN pode_gerenciar_apontamentos BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
            print("✅ Coluna pode_gerenciar_apontamentos adicionada com sucesso!")
            return True
        else:
            print("ℹ️ Coluna pode_gerenciar_apontamentos já existe.")
            return True
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro na migração PostgreSQL: {e}")
        return False
    finally:
        cursor.close()

def migrate_sqlite(conn):
    """Migração para SQLite"""
    cursor = conn.cursor()
    try:
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(usuario)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'pode_gerenciar_apontamentos' not in columns:
            print("Adicionando coluna pode_gerenciar_apontamentos na tabela usuario...")
            cursor.execute("""
                ALTER TABLE usuario 
                ADD COLUMN pode_gerenciar_apontamentos BOOLEAN DEFAULT 0
            """)
            conn.commit()
            print("✅ Coluna pode_gerenciar_apontamentos adicionada com sucesso!")
            return True
        else:
            print("ℹ️ Coluna pode_gerenciar_apontamentos já existe.")
            return True
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro na migração SQLite: {e}")
        return False
    finally:
        cursor.close()

def run_migration():
    """Executa a migração apropriada baseada no tipo de banco"""
    from app import app, db
    
    with app.app_context():
        engine = db.engine
        dialect_name = engine.dialect.name
        
        print(f"🔧 Executando migração para {dialect_name}...")
        
        with engine.connect() as conn:
            if dialect_name == 'postgresql':
                migrate_postgresql(conn.connection)
            elif dialect_name == 'sqlite':
                migrate_sqlite(conn.connection)
            else:
                print(f"⚠️ Dialeto {dialect_name} não suportado para esta migração")
                return False
        
        return True

if __name__ == '__main__':
    try:
        success = run_migration()
        if success:
            print("✅ Migração concluída com sucesso!")
        else:
            print("⚠️ Migração não foi executada")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erro ao executar migração: {e}")
        sys.exit(1)
