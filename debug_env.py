#!/usr/bin/env python3
"""Script para debugar as variáveis de ambiente e conexão do banco"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from urllib.parse import urlparse

# Carregar .env
load_dotenv()

print("=== DEBUG VARIÁVEIS DE AMBIENTE ===")
print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'NÃO DEFINIDA')}")
print(f"SECRET_KEY: {os.getenv('SECRET_KEY', 'NÃO DEFINIDA')}")
print()

# Testar conexão com a URL do .env
database_url = os.getenv('DATABASE_URL')
if database_url:
    print("=== TESTE DE CONEXÃO COM .env ===")
    try:
        engine = create_engine(database_url)
        conn = engine.connect()
        print("✅ Conexão com .env bem-sucedida!")
        conn.close()
    except Exception as e:
        print(f"❌ Erro de conexão com .env: {e}")
    
    # Parse da URL
    print("\n=== PARSE DA URL ===")
    parsed = urlparse(database_url)
    print(f"Scheme: {parsed.scheme}")
    print(f"Username: {parsed.username}")
    print(f"Password: {'*' * len(parsed.password) if parsed.password else 'None'}")
    print(f"Host: {parsed.hostname}")
    print(f"Port: {parsed.port}")
    print(f"Database: {parsed.path.lstrip('/')}")
else:
    print("❌ DATABASE_URL não encontrada no .env")

# Testar com a URL que funcionou no tetconecao.py
print("\n=== TESTE COM URL ORIGINAL (tetconecao.py) ===")
original_url = "postgresql+psycopg2://postgres.rxkuxdtpmrpfrufvnjxa:hsZQIE3QiOdprHB5@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
try:
    engine = create_engine(original_url)
    conn = engine.connect()
    print("✅ Conexão com URL original bem-sucedida!")
    conn.close()
except Exception as e:
    print(f"❌ Erro de conexão com URL original: {e}")
