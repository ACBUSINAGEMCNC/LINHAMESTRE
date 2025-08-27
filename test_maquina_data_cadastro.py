#!/usr/bin/env python3
"""
Script para testar se a coluna 'data_cadastro' existe na tabela 'maquina'
usando o modelo SQLAlchemy e uma aplicação Flask simples.
"""

import os
import sys
import logging
import datetime
from flask import Flask
from sqlalchemy import inspect
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def test_maquina_model():
    """Testa se a coluna 'data_cadastro' existe no modelo Maquina."""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Configurar a variável de ambiente para pular verificações de banco de dados
        # Isso evita que a aplicação tente fazer migrações durante o teste
        os.environ['SKIP_DB_CHECKS'] = 'true'
        
        # Criar uma aplicação Flask
        app = Flask(__name__)
        
        # Configurar o banco de dados
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            # Usar SQLite local como fallback
            db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(db_dir, 'database.db')
            database_url = f'sqlite:///{db_path}'
        
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Importar o modelo e inicializar o banco de dados
        from models import db, Maquina
        db.init_app(app)
        
        with app.app_context():
            # Verificar se a tabela maquina existe
            inspector = inspect(db.engine)
            if 'maquina' not in inspector.get_table_names():
                logger.error("❌ Tabela 'maquina' não encontrada no banco de dados")
                return False
            
            # Verificar se a coluna data_cadastro existe
            columns = [column['name'] for column in inspector.get_columns('maquina')]
            logger.info(f"Colunas na tabela 'maquina': {columns}")
            
            if 'data_cadastro' not in columns:
                logger.warning("⚠️ Coluna 'data_cadastro' não encontrada. Executando migração...")
                
                # Executar a migração
                try:
                    # Determinar qual migração executar com base no tipo de banco de dados
                    if database_url.startswith('postgresql://'):
                        from migrations.add_columns_maquina import migrate_postgres
                        success = migrate_postgres()
                    else:
                        from migrations.add_columns_maquina import migrate_sqlite
                        success = migrate_sqlite()
                    
                    if success:
                        logger.info("✅ Migração executada com sucesso")
                        
                        # Verificar novamente
                        columns = [column['name'] for column in inspector.get_columns('maquina')]
                        if 'data_cadastro' in columns:
                            logger.info("✅ Verificação confirmada: coluna 'data_cadastro' existe agora")
                        else:
                            logger.error("❌ Coluna 'data_cadastro' ainda não existe após migração")
                            return False
                    else:
                        logger.error("❌ Falha na migração")
                        return False
                except Exception as e:
                    logger.error(f"❌ Erro ao executar migração: {e}")
                    return False
            else:
                logger.info("✅ Coluna 'data_cadastro' já existe na tabela 'maquina'")
            
            # Testar a criação de uma máquina com data_cadastro
            try:
                # Criar uma nova máquina
                nova_maquina = Maquina(
                    codigo="TEST-DATA-CADASTRO",
                    nome="Máquina de Teste Data Cadastro",
                    categoria_trabalho="Teste",
                    imagem="test.jpg",
                    data_cadastro=datetime.datetime.utcnow()
                )
                
                # Adicionar ao banco de dados
                db.session.add(nova_maquina)
                db.session.commit()
                logger.info(f"✅ Máquina criada com sucesso: ID={nova_maquina.id}")
                
                # Recuperar a máquina do banco de dados
                maquina_db = Maquina.query.filter_by(codigo="TEST-DATA-CADASTRO").first()
                if maquina_db and maquina_db.data_cadastro:
                    logger.info(f"✅ Máquina recuperada com data_cadastro: {maquina_db.data_cadastro}")
                    
                    # Limpar dados de teste
                    db.session.delete(maquina_db)
                    db.session.commit()
                    logger.info("✅ Dados de teste limpos")
                    
                    return True
                else:
                    logger.error("❌ Falha ao recuperar máquina com data_cadastro")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erro ao testar criação de máquina: {e}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Erro ao testar modelo Maquina: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== TESTE DO MODELO MAQUINA COM COLUNA 'data_cadastro' ===")
    
    success = test_maquina_model()
    
    if success:
        logger.info("✅ TESTE CONCLUÍDO COM SUCESSO: A coluna 'data_cadastro' existe e funciona corretamente")
        sys.exit(0)
    else:
        logger.error("❌ TESTE FALHOU: A coluna 'data_cadastro' não existe ou não funciona corretamente")
        sys.exit(1)
