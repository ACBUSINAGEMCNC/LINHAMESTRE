#!/usr/bin/env python3
"""
Script de migração para adicionar as colunas 'imagem' e 'data_cadastro' na tabela 'maquina'.
Suporta tanto PostgreSQL quanto SQLite.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_postgres():
    """
    Adiciona a coluna 'imagem' na tabela 'maquina' no PostgreSQL.
    """
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
        
        def add_columns_pg(engine):
            """Adiciona as colunas 'imagem' e 'data_cadastro' na tabela 'maquina' para PostgreSQL."""
            try:
                with engine.connect() as connection:
                    # Verificar se a coluna 'imagem' já existe
                    check_imagem_query = text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'maquina' AND column_name = 'imagem'
                    """)
                    result = connection.execute(check_imagem_query)
                    imagem_exists = result.scalar() is not None
                    
                    if not imagem_exists:
                        # Adicionar a coluna 'imagem' se não existir
                        logging.info("Adicionando coluna 'imagem' na tabela 'maquina' (PostgreSQL)")
                        add_imagem_query = text("""
                            ALTER TABLE maquina 
                            ADD COLUMN imagem VARCHAR(255)
                        """)
                        connection.execute(add_imagem_query)
                        connection.commit()
                        logging.info("Coluna 'imagem' adicionada com sucesso")
                    else:
                        logging.info("Coluna 'imagem' já existe na tabela 'maquina'")
                    
                    # Verificar se a coluna 'data_cadastro' já existe
                    check_data_query = text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'maquina' AND column_name = 'data_cadastro'
                    """)
                    result = connection.execute(check_data_query)
                    data_exists = result.scalar() is not None
                    
                    if not data_exists:
                        # Adicionar a coluna 'data_cadastro' se não existir
                        logging.info("Adicionando coluna 'data_cadastro' na tabela 'maquina' (PostgreSQL)")
                        add_data_query = text("""
                            ALTER TABLE maquina 
                            ADD COLUMN data_cadastro TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        """)
                        connection.execute(add_data_query)
                        connection.commit()
                        logging.info("Coluna 'data_cadastro' adicionada com sucesso")
                    else:
                        logging.info("Coluna 'data_cadastro' já existe na tabela 'maquina'")
                        
                return True
            except Exception as e:
                logging.error(f"Erro ao adicionar colunas na tabela 'maquina': {e}")
                return False
        
        return add_columns_pg(engine)
        
    except Exception as e:
        logger.error(f"Erro ao adicionar colunas na tabela 'maquina': {str(e)}")
        return False

def migrate_sqlite():
    """
    Adiciona as colunas 'imagem' e 'data_cadastro' na tabela 'maquina' no SQLite.
    """
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Obter caminho do banco SQLite
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(os.path.dirname(db_dir), 'database.db')
        
        if not os.path.exists(db_path):
            logger.error(f"Banco de dados SQLite não encontrado em {db_path}")
            return False
            
        # Criar engine
        engine = create_engine(f'sqlite:///{db_path}')
        
        def add_columns_sqlite(connection):
            """Adiciona as colunas 'imagem' e 'data_cadastro' na tabela 'maquina' para SQLite."""
            try:
                # Verificar se as colunas já existem
                cursor = connection.cursor()
                cursor.execute("PRAGMA table_info(maquina)")
                columns = cursor.fetchall()
                column_names = [column[1] for column in columns]
                
                # Verificar e adicionar coluna 'imagem'
                if 'imagem' not in column_names:
                    # Adicionar a coluna se não existir
                    logging.info("Adicionando coluna 'imagem' na tabela 'maquina' (SQLite)")
                    cursor.execute("ALTER TABLE maquina ADD COLUMN imagem TEXT")
                    connection.commit()
                    logging.info("Coluna 'imagem' adicionada com sucesso")
                else:
                    logging.info("Coluna 'imagem' já existe na tabela 'maquina'")
                
                # Verificar e adicionar coluna 'data_cadastro'
                if 'data_cadastro' not in column_names:
                    # Adicionar a coluna se não existir
                    logging.info("Adicionando coluna 'data_cadastro' na tabela 'maquina' (SQLite)")
                    cursor.execute("ALTER TABLE maquina ADD COLUMN data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    connection.commit()
                    logging.info("Coluna 'data_cadastro' adicionada com sucesso")
                else:
                    logging.info("Coluna 'data_cadastro' já existe na tabela 'maquina'")
                    
                return True
            except Exception as e:
                logging.error(f"Erro ao adicionar colunas na tabela 'maquina': {e}")
                return False
        
        with engine.connect() as connection:
            return add_columns_sqlite(connection)
        
    except Exception as e:
        logger.error(f"Erro ao adicionar colunas na tabela 'maquina': {str(e)}")
        return False

if __name__ == "__main__":
    # Verificar qual banco de dados está sendo usado
    database_url = os.getenv('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        logger.info("Usando PostgreSQL - adicionando colunas 'imagem' e 'data_cadastro' à tabela 'maquina'...")
        success = migrate_postgres()
    else:
        logger.info("Usando SQLite - adicionando colunas 'imagem' e 'data_cadastro' à tabela 'maquina'...")
        success = migrate_sqlite()
        
    if success:
        logger.info("Migração concluída com sucesso")
        sys.exit(0)
    else:
        logger.error("Falha na migração")
        sys.exit(1)
