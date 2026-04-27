"""
Migration: Adicionar índices na tabela Item para melhorar performance
Criado em: 2026-04-27
Versão: v2.11.0005
"""

import logging
import os
from sqlalchemy import create_engine, text, inspect

logger = logging.getLogger(__name__)

def migrate_postgres():
    """Adiciona índices na tabela Item no PostgreSQL/Supabase"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("DATABASE_URL não configurada, pulando migration de índices")
            return
        
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Verificar se os índices já existem
            inspector = inspect(engine)
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('item')]
            
            indexes_to_create = []
            
            # Índice para codigo_acb (já deve existir por UNIQUE, mas vamos garantir)
            if 'idx_item_codigo_acb' not in existing_indexes:
                indexes_to_create.append(
                    "CREATE INDEX IF NOT EXISTS idx_item_codigo_acb ON item(codigo_acb)"
                )
            
            # Índice para nome (já deve existir por UNIQUE, mas vamos garantir)
            if 'idx_item_nome' not in existing_indexes:
                indexes_to_create.append(
                    "CREATE INDEX IF NOT EXISTS idx_item_nome ON item(nome)"
                )
            
            # Índice para data_criacao (para ordenação)
            if 'idx_item_data_criacao' not in existing_indexes:
                indexes_to_create.append(
                    "CREATE INDEX IF NOT EXISTS idx_item_data_criacao ON item(data_criacao)"
                )
            
            # Índice para eh_composto (para filtros)
            if 'idx_item_eh_composto' not in existing_indexes:
                indexes_to_create.append(
                    "CREATE INDEX IF NOT EXISTS idx_item_eh_composto ON item(eh_composto)"
                )
            
            # Criar índices
            for idx_sql in indexes_to_create:
                logger.info(f"Criando índice: {idx_sql}")
                conn.execute(text(idx_sql))
                conn.commit()
            
            if indexes_to_create:
                logger.info(f"✅ {len(indexes_to_create)} índices criados na tabela Item")
            else:
                logger.info("✅ Todos os índices já existem na tabela Item")
            
            # VACUUM ANALYZE para atualizar estatísticas
            logger.info("Atualizando estatísticas da tabela Item...")
            conn.execute(text("ANALYZE item"))
            conn.commit()
            logger.info("✅ Estatísticas atualizadas")
            
    except Exception as e:
        logger.error(f"Erro ao criar índices na tabela Item: {e}")
        raise


def migrate_sqlite():
    """Adiciona índices na tabela Item no SQLite (desenvolvimento local)"""
    try:
        import sqlite3
        db_path = 'database.db'
        
        if not os.path.exists(db_path):
            logger.warning(f"Banco SQLite não encontrado em {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se os índices já existem
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='item'")
        existing_indexes = [row[0] for row in cursor.fetchall()]
        
        indexes_to_create = []
        
        if 'idx_item_codigo_acb' not in existing_indexes:
            indexes_to_create.append(
                "CREATE INDEX IF NOT EXISTS idx_item_codigo_acb ON item(codigo_acb)"
            )
        
        if 'idx_item_nome' not in existing_indexes:
            indexes_to_create.append(
                "CREATE INDEX IF NOT EXISTS idx_item_nome ON item(nome)"
            )
        
        if 'idx_item_data_criacao' not in existing_indexes:
            indexes_to_create.append(
                "CREATE INDEX IF NOT EXISTS idx_item_data_criacao ON item(data_criacao)"
            )
        
        if 'idx_item_eh_composto' not in existing_indexes:
            indexes_to_create.append(
                "CREATE INDEX IF NOT EXISTS idx_item_eh_composto ON item(eh_composto)"
            )
        
        for idx_sql in indexes_to_create:
            logger.info(f"Criando índice: {idx_sql}")
            cursor.execute(idx_sql)
        
        conn.commit()
        conn.close()
        
        if indexes_to_create:
            logger.info(f"✅ {len(indexes_to_create)} índices criados na tabela Item (SQLite)")
        else:
            logger.info("✅ Todos os índices já existem na tabela Item (SQLite)")
            
    except Exception as e:
        logger.error(f"Erro ao criar índices na tabela Item (SQLite): {e}")
        raise


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Tentar PostgreSQL primeiro
    if os.getenv('DATABASE_URL'):
        print("Executando migration para PostgreSQL/Supabase...")
        migrate_postgres()
    else:
        print("Executando migration para SQLite...")
        migrate_sqlite()
