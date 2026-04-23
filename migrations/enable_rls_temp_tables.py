"""
Migration: Habilitar RLS (Row Level Security) em tabelas temporárias
Corrige avisos de segurança do Supabase Database Linter
"""
import os
import logging

logger = logging.getLogger(__name__)


def _get_database_url_from_env():
    """Retorna DATABASE_URL do ambiente."""
    return os.getenv('DATABASE_URL')


def migrate_postgres() -> bool:
    """Habilita RLS nas tabelas temporárias (Postgres/Supabase)."""
    from sqlalchemy import create_engine, text
    
    database_url = _get_database_url_from_env()
    if not database_url:
        logger.warning("DATABASE_URL não encontrada, pulando migração RLS.")
        return False
    
    engine = create_engine(database_url)
    
    # Habilitar RLS nas tabelas temporárias
    stmts = [
        # Tabela estoque_pecas_slot_temp
        "ALTER TABLE estoque_pecas_slot_temp ENABLE ROW LEVEL SECURITY",
        
        # Criar política permissiva para usuários autenticados
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies 
                WHERE tablename = 'estoque_pecas_slot_temp' 
                AND policyname = 'allow_authenticated_all'
            ) THEN
                CREATE POLICY allow_authenticated_all 
                ON estoque_pecas_slot_temp 
                FOR ALL 
                TO authenticated 
                USING (true) 
                WITH CHECK (true);
            END IF;
        END $$;
        """,
        
        # Tabela import_valores_temp
        """
        CREATE TABLE IF NOT EXISTS import_valores_temp (
            id VARCHAR(36) PRIMARY KEY,
            dados JSONB NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "ALTER TABLE import_valores_temp ENABLE ROW LEVEL SECURITY",
        
        # Criar política permissiva para usuários autenticados
        """
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies 
                WHERE tablename = 'import_valores_temp' 
                AND policyname = 'allow_authenticated_all'
            ) THEN
                CREATE POLICY allow_authenticated_all 
                ON import_valores_temp 
                FOR ALL 
                TO authenticated 
                USING (true) 
                WITH CHECK (true);
            END IF;
        END $$;
        """
    ]
    
    try:
        with engine.begin() as conn:
            for stmt in stmts:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    # Ignorar erros de política já existente ou tabela já com RLS
                    if 'already exists' not in str(e).lower() and 'already enabled' not in str(e).lower():
                        logger.warning(f"Aviso ao executar RLS migration: {e}")
        
        logger.info("✅ RLS habilitado nas tabelas temporárias (estoque_pecas_slot_temp, import_valores_temp)")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao habilitar RLS: {e}")
        return False


def migrate_sqlite(db_path: str = None) -> bool:
    """SQLite não suporta RLS - retorna True (sem ação)."""
    logger.info("SQLite não requer RLS - pulando migração.")
    return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    migrate_postgres()
