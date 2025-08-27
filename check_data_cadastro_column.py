#!/usr/bin/env python3
"""
Script para verificar se a coluna 'data_cadastro' existe na tabela 'maquina'.
Suporta tanto PostgreSQL quanto SQLite.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def check_postgres():
    """Verifica se a coluna 'data_cadastro' existe na tabela 'maquina' para PostgreSQL."""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Obter URL do banco de dados
        database_url = os.getenv('DATABASE_URL')
        if not database_url or not database_url.startswith('postgresql://'):
            logger.error("DATABASE_URL não configurada ou não é PostgreSQL")
            return False
            
        # Criar engine
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            # Verificar se a coluna existe
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'maquina' AND column_name = 'data_cadastro'
            """)
            result = connection.execute(check_query)
            column_exists = result.scalar() is not None
            
            if column_exists:
                logger.info("✅ Coluna 'data_cadastro' existe na tabela 'maquina' (PostgreSQL)")
                return True
            else:
                logger.error("❌ Coluna 'data_cadastro' NÃO existe na tabela 'maquina' (PostgreSQL)")
                return False
                
    except Exception as e:
        logger.error(f"Erro ao verificar coluna 'data_cadastro': {e}")
        return False

def check_sqlite():
    """Verifica se a coluna 'data_cadastro' existe na tabela 'maquina' no SQLite."""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Obter caminho do banco SQLite
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(db_dir, 'database.db')
        
        if not os.path.exists(db_path):
            logger.error(f"Banco de dados SQLite não encontrado em {db_path}")
            return False
            
        # Criar engine
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Verificar se a coluna existe usando o inspetor do SQLAlchemy
        inspector = inspect(engine)
        columns = [column['name'] for column in inspector.get_columns('maquina')]
        
        if 'data_cadastro' in columns:
            logger.info("✅ Coluna 'data_cadastro' existe na tabela 'maquina' (SQLite)")
            return True
        else:
            logger.error("❌ Coluna 'data_cadastro' NÃO existe na tabela 'maquina' (SQLite)")
            
            # Tentar executar a migração
            logger.info("Tentando executar migração para adicionar a coluna 'data_cadastro'...")
            try:
                from migrations.add_columns_maquina import migrate_sqlite
                if migrate_sqlite():
                    logger.info("Migração concluída com sucesso. Verificando novamente...")
                    
                    # Verificar novamente após a migração
                    inspector = inspect(engine)
                    columns = [column['name'] for column in inspector.get_columns('maquina')]
                    
                    if 'data_cadastro' in columns:
                        logger.info("✅ Coluna 'data_cadastro' adicionada com sucesso à tabela 'maquina'")
                        return True
                    else:
                        logger.error("❌ Coluna 'data_cadastro' ainda não existe após a migração")
                        return False
                else:
                    logger.error("Falha na migração")
                    return False
            except Exception as e:
                logger.error(f"Erro ao executar migração: {e}")
                return False
                
    except Exception as e:
        logger.error(f"Erro ao verificar coluna 'data_cadastro': {e}")
        return False

if __name__ == "__main__":
    # Verificar qual banco de dados está sendo usado
    database_url = os.getenv('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        logger.info("Usando PostgreSQL - verificando coluna 'data_cadastro' na tabela 'maquina'...")
        success = check_postgres()
    else:
        logger.info("Usando SQLite - verificando coluna 'data_cadastro' na tabela 'maquina'...")
        success = check_sqlite()
        
    if success:
        logger.info("✅ Verificação concluída com sucesso: coluna 'data_cadastro' existe")
        sys.exit(0)
    else:
        logger.error("❌ Verificação falhou: coluna 'data_cadastro' não existe")
        sys.exit(1)
