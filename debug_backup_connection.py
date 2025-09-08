#!/usr/bin/env python3
"""Script para debugar especificamente a conexão do backup"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from urllib.parse import urlparse
from app import create_app
from models import db

# Carregar .env
load_dotenv()

# Criar app para ter contexto do Flask
app = create_app()

with app.app_context():
    print("=== DEBUG CONEXÃO DO BACKUP ===")
    
    # URL que o Flask está usando
    flask_url = str(db.engine.url)
    print(f"URL do Flask: {flask_url}")
    
    # Parse da URL do Flask
    parsed_flask = urlparse(flask_url)
    print(f"Flask - Host: {parsed_flask.hostname}")
    print(f"Flask - Username: {parsed_flask.username}")
    print(f"Flask - Password: {'*' * len(parsed_flask.password) if parsed_flask.password else 'None'}")
    
    # URL do .env
    env_url = os.getenv('DATABASE_URL')
    print(f"\nURL do .env: {env_url}")
    
    # Parse da URL do .env
    parsed_env = urlparse(env_url)
    print(f"Env - Host: {parsed_env.hostname}")
    print(f"Env - Username: {parsed_env.username}")
    print(f"Env - Password: {'*' * len(parsed_env.password) if parsed_env.password else 'None'}")
    
    # Testar conexão como o backup faria
    print("\n=== TESTE COMO O BACKUP FAZ ===")
    conn_info = {
        'type': 'postgresql',
        'host': parsed_flask.hostname,
        'port': parsed_flask.port or 5432,
        'database': parsed_flask.path.lstrip('/'),
        'username': parsed_flask.username,
        'password': parsed_flask.password
    }
    
    print(f"Conn Info: {conn_info}")
    
    # Criar string de conexão como o backup faz
    backup_connection_string = f"postgresql://{conn_info['username']}:{conn_info['password']}@{conn_info['host']}:{conn_info['port']}/{conn_info['database']}"
    print(f"String do backup: {backup_connection_string}")
    
    try:
        backup_engine = create_engine(backup_connection_string)
        backup_conn = backup_engine.connect()
        print("✅ Conexão do backup bem-sucedida!")
        backup_conn.close()
    except Exception as e:
        print(f"❌ Erro na conexão do backup: {e}")
