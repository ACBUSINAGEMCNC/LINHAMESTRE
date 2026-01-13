"""
Migração para adicionar a coluna quantidade_snapshot à tabela pedido_ordem_servico.
Este script pode ser executado diretamente ou importado pelo app.py
para ser executado durante a inicialização da aplicação.
"""

import os
import logging
import psycopg2
from psycopg2 import sql
import sqlite3
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_postgres():
    """Adiciona a coluna quantidade_snapshot à tabela pedido_ordem_servico no PostgreSQL."""
    conn = None
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
            return False
            
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Verificar se a coluna já existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'pedido_ordem_servico' AND column_name = 'quantidade_snapshot'
                );
            """)
            
            if cursor.fetchone()[0]:
                logger.info("Coluna 'quantidade_snapshot' já existe na tabela 'pedido_ordem_servico' (PostgreSQL)")
                return True
                
            # Adicionar a coluna
            query = sql.SQL("""
                ALTER TABLE pedido_ordem_servico 
                ADD COLUMN IF NOT EXISTS quantidade_snapshot INTEGER;
            """)
            cursor.execute(query)
            
            # Preencher valores existentes com a quantidade atual do pedido
            cursor.execute("""
                UPDATE pedido_ordem_servico pos
                SET quantidade_snapshot = p.quantidade
                FROM pedido p
                WHERE pos.pedido_id = p.id AND pos.quantidade_snapshot IS NULL;
            """)
            
            logger.info("Coluna 'quantidade_snapshot' adicionada com sucesso à tabela 'pedido_ordem_servico' (PostgreSQL)")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def migrate_sqlite():
    """Adiciona a coluna quantidade_snapshot à tabela pedido_ordem_servico no SQLite."""
    conn = None
    try:
        # Obter caminho do banco de dados
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(db_dir, 'database.db')
        
        if not os.path.exists(db_path):
            logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(pedido_ordem_servico)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'quantidade_snapshot' in columns:
            logger.info("Coluna 'quantidade_snapshot' já existe na tabela 'pedido_ordem_servico' (SQLite)")
            return True
            
        # Adicionar a coluna
        cursor.execute("ALTER TABLE pedido_ordem_servico ADD COLUMN quantidade_snapshot INTEGER")
        
        # Preencher valores existentes com a quantidade atual do pedido
        cursor.execute("""
            UPDATE pedido_ordem_servico
            SET quantidade_snapshot = (
                SELECT quantidade FROM pedido WHERE pedido.id = pedido_ordem_servico.pedido_id
            )
            WHERE quantidade_snapshot IS NULL
        """)
        
        conn.commit()
        logger.info("Coluna 'quantidade_snapshot' adicionada com sucesso à tabela 'pedido_ordem_servico' (SQLite)")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao migrar SQLite: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def run_migration():
    """Executa a migração para ambos os bancos de dados."""
    logger.info("Iniciando migração para adicionar coluna 'quantidade_snapshot'...")
    
    pg_success = migrate_postgres()
    sqlite_success = migrate_sqlite()
    
    if pg_success or sqlite_success:
        logger.info("Migração concluída com sucesso!")
        return True
    else:
        logger.error("Falha na migração!")
        return False

if __name__ == "__main__":
    run_migration()
