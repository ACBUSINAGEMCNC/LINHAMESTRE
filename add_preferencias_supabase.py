#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adicionar coluna preferencias na tabela usuario (Supabase/PostgreSQL)
"""

import os
import sys
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

# Importar após carregar .env
try:
    import psycopg
    HAS_PSYCOPG = True
except:
    HAS_PSYCOPG = False

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except:
    HAS_PSYCOPG2 = False

if not HAS_PSYCOPG and not HAS_PSYCOPG2:
    print("❌ Nenhum driver PostgreSQL disponível (psycopg ou psycopg2)")
    sys.exit(1)

# Obter DATABASE_URL
database_url = os.getenv('DATABASE_URL')

if not database_url:
    print("❌ DATABASE_URL não configurada no .env")
    sys.exit(1)

if not database_url.startswith('postgresql://'):
    print("❌ DATABASE_URL não é PostgreSQL")
    sys.exit(1)

print(f"📂 Conectando ao Supabase...")

from urllib.parse import urlparse
parsed = urlparse(database_url)

try:
    # Conectar
    if HAS_PSYCOPG:
        conn = psycopg.connect(
            host=parsed.hostname,
            port=parsed.port,
            dbname=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            connect_timeout=10
        )
    else:
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            connect_timeout=10
        )
    
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("✅ Conectado!")
    
    # Verificar se a coluna já existe
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'usuario' AND column_name = 'preferencias'
    """)
    
    if cursor.fetchone():
        print("✅ Coluna 'preferencias' já existe!")
    else:
        print("📝 Adicionando coluna 'preferencias'...")
        cursor.execute("""
            ALTER TABLE usuario 
            ADD COLUMN preferencias TEXT
        """)
        print("✅ Coluna adicionada com sucesso!")
    
    cursor.close()
    conn.close()
    print("✨ Migração concluída!")
    
except Exception as e:
    print(f"❌ Erro: {str(e)}")
    sys.exit(1)
