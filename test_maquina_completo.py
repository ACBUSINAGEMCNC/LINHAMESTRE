#!/usr/bin/env python3
"""
Teste completo para verificar se a coluna categoria_trabalho foi adicionada corretamente
na tabela maquina e se o módulo de máquinas está funcionando corretamente.
"""

import os
import sys
import requests
import json
import logging
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_connection():
    """Testa a conexão com o banco de dados."""
    try:
        # Importar apenas o necessário para testar a conexão
        from sqlalchemy import create_engine, text
        load_dotenv()
        
        # Obter URL do banco de dados
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            # Usar SQLite local como fallback
            db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(db_dir, 'database.db')
            database_url = f'sqlite:///{db_path}'
            
        # Criar engine e testar conexão
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                logger.info("✅ Conexão com o banco de dados estabelecida com sucesso")
                return True, engine
            else:
                logger.error("❌ Erro ao testar conexão com o banco de dados")
                return False, None
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao banco de dados: {str(e)}")
        return False, None

def test_maquina_table(engine):
    """Testa se a tabela maquina existe e tem a coluna categoria_trabalho."""
    try:
        from sqlalchemy import text
        
        with engine.connect() as conn:
            # Verificar se a tabela maquina existe
            if engine.url.drivername.startswith('postgresql'):
                # PostgreSQL
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_name = 'maquina'
                    );
                """))
                table_exists = result.scalar()
            else:
                # SQLite
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='maquina';
                """))
                table_exists = result.scalar() is not None
                
            if not table_exists:
                logger.error("❌ A tabela 'maquina' não existe no banco de dados")
                return False
                
            logger.info("✅ Tabela 'maquina' encontrada no banco de dados")
            
            # Verificar se a coluna categoria_trabalho existe
            if engine.url.drivername.startswith('postgresql'):
                # PostgreSQL
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'maquina' AND column_name = 'categoria_trabalho'
                    );
                """))
                column_exists = result.scalar()
            else:
                # SQLite
                result = conn.execute(text("PRAGMA table_info(maquina)"))
                columns = [row[1] for row in result.fetchall()]
                column_exists = 'categoria_trabalho' in columns
                
            if column_exists:
                logger.info("✅ Coluna 'categoria_trabalho' encontrada na tabela 'maquina'")
                return True
            else:
                logger.error("❌ Coluna 'categoria_trabalho' NÃO encontrada na tabela 'maquina'")
                return False
                
    except Exception as e:
        logger.error(f"❌ Erro ao verificar tabela maquina: {str(e)}")
        return False

def test_maquina_model():
    """Testa se o modelo Maquina está funcionando corretamente."""
    try:
        # Importar o modelo e o db
        from models import Maquina, db
        from flask import Flask
        
        # Criar uma aplicação Flask temporária para o contexto
        app = Flask(__name__)
        load_dotenv()
        
        # Configurar o banco de dados
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            # Usar SQLite local como fallback
            db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(db_dir, 'database.db')
            database_url = f'sqlite:///{db_path}'
            
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        
        with app.app_context():
            # Verificar se podemos consultar máquinas
            try:
                maquinas = Maquina.query.all()
                logger.info(f"✅ Consulta ao modelo Maquina bem-sucedida. {len(maquinas)} máquinas encontradas.")
                
                # Mostrar as máquinas encontradas
                if maquinas:
                    logger.info("\n📋 Máquinas encontradas:")
                    for m in maquinas:
                        logger.info(f"   ID: {m.id}, Código: {m.codigo}, Nome: {m.nome}, Categoria: {m.categoria_trabalho}")
                
                return True
            except Exception as model_error:
                logger.error(f"❌ Erro ao consultar modelo Maquina: {str(model_error)}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Erro ao testar modelo Maquina: {str(e)}")
        return False

def test_endpoint():
    """Testa se o endpoint /trabalhos/maquinas está funcionando."""
    try:
        response = requests.get('http://127.0.0.1:5000/trabalhos/maquinas', timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Endpoint /trabalhos/maquinas respondeu com sucesso (HTTP 200)")
            return True
        else:
            logger.error(f"❌ Erro HTTP {response.status_code} ao acessar /trabalhos/maquinas")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao acessar endpoint: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("TESTE COMPLETO DA TABELA MAQUINA E COLUNA CATEGORIA_TRABALHO")
    print("=" * 50)
    
    # Testar conexão com o banco de dados
    print("\n1. TESTANDO CONEXÃO COM O BANCO DE DADOS")
    print("-" * 50)
    db_success, engine = test_database_connection()
    
    if db_success and engine:
        # Testar tabela maquina
        print("\n2. VERIFICANDO TABELA MAQUINA E COLUNA CATEGORIA_TRABALHO")
        print("-" * 50)
        table_success = test_maquina_table(engine)
        
        # Testar modelo Maquina
        print("\n3. TESTANDO MODELO MAQUINA")
        print("-" * 50)
        model_success = test_maquina_model()
        
        # Testar endpoint
        print("\n4. TESTANDO ENDPOINT /trabalhos/maquinas")
        print("-" * 50)
        endpoint_success = test_endpoint()
        
        # Resumo dos testes
        print("\n" + "=" * 50)
        print("RESUMO DOS TESTES")
        print("=" * 50)
        print(f"✅ Conexão com o banco de dados: {'SUCESSO' if db_success else 'FALHA'}")
        print(f"✅ Tabela maquina e coluna categoria_trabalho: {'SUCESSO' if table_success else 'FALHA'}")
        print(f"✅ Modelo Maquina: {'SUCESSO' if model_success else 'FALHA'}")
        print(f"✅ Endpoint /trabalhos/maquinas: {'SUCESSO' if endpoint_success else 'FALHA'}")
        
        if db_success and table_success and model_success and endpoint_success:
            print("\n✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
            sys.exit(0)
        else:
            print("\n❌ ALGUNS TESTES FALHARAM!")
            sys.exit(1)
    else:
        print("\n❌ FALHA NA CONEXÃO COM O BANCO DE DADOS. TESTES INTERROMPIDOS.")
        sys.exit(1)
