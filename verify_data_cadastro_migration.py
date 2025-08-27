#!/usr/bin/env python3
"""
Script simples para verificar se a migração da coluna 'data_cadastro' foi bem-sucedida.
Este script tenta criar a coluna se ela não existir e depois verifica se ela existe.
"""

import os
import sys
import logging
import sqlite3
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def verify_sqlite():
    """Verifica e adiciona a coluna 'data_cadastro' no SQLite se necessário."""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Conectar ao banco SQLite
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Verificar se a tabela maquina existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maquina'")
        if not cursor.fetchone():
            logger.error("❌ Tabela 'maquina' não encontrada no banco de dados")
            conn.close()
            return False
        
        # Verificar se a coluna data_cadastro existe
        cursor.execute("PRAGMA table_info(maquina)")
        columns = [column[1] for column in cursor.fetchall()]
        logger.info(f"Colunas na tabela 'maquina': {columns}")
        
        if 'data_cadastro' not in columns:
            logger.warning("⚠️ Coluna 'data_cadastro' não encontrada. Tentando adicionar...")
            
            # Adicionar a coluna
            try:
                cursor.execute("ALTER TABLE maquina ADD COLUMN data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                conn.commit()
                logger.info("✅ Coluna 'data_cadastro' adicionada com sucesso")
                
                # Verificar novamente
                cursor.execute("PRAGMA table_info(maquina)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'data_cadastro' in columns:
                    logger.info("✅ Verificação confirmada: coluna 'data_cadastro' existe agora")
                else:
                    logger.error("❌ Falha ao adicionar coluna 'data_cadastro'")
                    conn.close()
                    return False
            except Exception as e:
                logger.error(f"❌ Erro ao adicionar coluna: {e}")
                conn.close()
                return False
        else:
            logger.info("✅ Coluna 'data_cadastro' já existe na tabela 'maquina'")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar/adicionar coluna 'data_cadastro': {e}")
        return False

def verify_postgres():
    """Verifica e adiciona a coluna 'data_cadastro' no PostgreSQL se necessário."""
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
            
            if not column_exists:
                logger.warning("⚠️ Coluna 'data_cadastro' não encontrada. Tentando adicionar...")
                
                # Adicionar a coluna
                try:
                    add_query = text("""
                        ALTER TABLE maquina 
                        ADD COLUMN data_cadastro TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    """)
                    connection.execute(add_query)
                    connection.commit()
                    logger.info("✅ Coluna 'data_cadastro' adicionada com sucesso")
                    
                    # Verificar novamente
                    result = connection.execute(check_query)
                    if result.scalar() is not None:
                        logger.info("✅ Verificação confirmada: coluna 'data_cadastro' existe agora")
                    else:
                        logger.error("❌ Falha ao adicionar coluna 'data_cadastro'")
                        return False
                except Exception as e:
                    logger.error(f"❌ Erro ao adicionar coluna: {e}")
                    return False
            else:
                logger.info("✅ Coluna 'data_cadastro' já existe na tabela 'maquina'")
                
            return True
                
    except Exception as e:
        logger.error(f"❌ Erro ao verificar/adicionar coluna 'data_cadastro': {e}")
        return False

if __name__ == "__main__":
    logger.info("=== VERIFICAÇÃO DA COLUNA 'data_cadastro' NA TABELA 'maquina' ===")
    
    # Verificar qual banco de dados está sendo usado
    database_url = os.getenv('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        logger.info("Usando PostgreSQL...")
        success = verify_postgres()
    else:
        logger.info("Usando SQLite...")
        success = verify_sqlite()
        
    if success:
        logger.info("✅ VERIFICAÇÃO CONCLUÍDA COM SUCESSO: A coluna 'data_cadastro' existe na tabela 'maquina'")
        sys.exit(0)
    else:
        logger.error("❌ VERIFICAÇÃO FALHOU: A coluna 'data_cadastro' não existe ou não pôde ser adicionada")
        sys.exit(1)
