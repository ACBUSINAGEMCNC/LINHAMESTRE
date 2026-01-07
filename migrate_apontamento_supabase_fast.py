#!/usr/bin/env python3
"""
Script RÁPIDO para migrar/criar tabelas do módulo de apontamento no Supabase/PostgreSQL
Versão otimizada para não travar
"""

import os
import sys
from urllib.parse import urlparse

try:
    import psycopg2  # type: ignore
except Exception:
    psycopg2 = None

try:
    import psycopg  # type: ignore
except Exception:
    psycopg = None

print("🚀 Migração RÁPIDA do módulo de apontamento para Supabase/PostgreSQL...")

# Obter URL do banco
database_url = os.getenv('DATABASE_URL')
if not database_url or not database_url.startswith('postgresql://'):
    print("❌ DATABASE_URL não configurada ou não é PostgreSQL")
    sys.exit(0)  # Exit sem erro para não travar o app

# Parse da URL
parsed = urlparse(database_url)

try:
    # Conectar ao PostgreSQL com timeout muito baixo
    print("⚡ Conectando rapidamente ao PostgreSQL...")
    if psycopg2 is not None:
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            connect_timeout=3  # Timeout muito baixo
        )
    elif psycopg is not None:
        conn = psycopg.connect(
            host=parsed.hostname,
            port=parsed.port,
            dbname=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            connect_timeout=3
        )
    else:
        print("❌ Nenhum driver PostgreSQL disponível (psycopg2/psycopg)")
        sys.exit(0)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Timeout muito baixo para statements
    cursor.execute("SET statement_timeout = '5s'")
    
    print("✅ Conectado!")
    
    # Executar comandos básicos rapidamente
    commands = [
        # 1. Coluna codigo_operador (sem constraint por enquanto)
        """
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name = 'usuario' AND column_name = 'codigo_operador') THEN
                ALTER TABLE usuario ADD COLUMN codigo_operador TEXT;
            END IF;
        END $$;
        """,
        
        # 2. Tabela apontamento_producao (sem foreign keys por enquanto)
        """
        CREATE TABLE IF NOT EXISTS apontamento_producao (
            id SERIAL PRIMARY KEY,
            ordem_servico_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            item_id INTEGER,
            trabalho_id INTEGER,
            tipo_acao TEXT NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            quantidade INTEGER,
            motivo_parada TEXT,
            tempo_decorrido INTEGER,
            lista_kanban TEXT,
            observacoes TEXT
        );
        """,
        
        # 3. Tabela status_producao_os (sem foreign keys por enquanto)
        """
        CREATE TABLE IF NOT EXISTS status_producao_os (
            id SERIAL PRIMARY KEY,
            ordem_servico_id INTEGER UNIQUE NOT NULL,
            status_atual TEXT NOT NULL DEFAULT 'Aguardando',
            operador_atual_id INTEGER,
            item_atual_id INTEGER,
            trabalho_atual_id INTEGER,
            inicio_acao TIMESTAMP,
            quantidade_atual INTEGER DEFAULT 0,
            previsao_termino TIMESTAMP,
            eficiencia_percentual FLOAT,
            motivo_pausa TEXT,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]
    
    for i, cmd in enumerate(commands, 1):
        try:
            cursor.execute(cmd)
            print(f"✅ Comando {i}/3 executado")
        except Exception as e:
            print(f"⚠️ Comando {i} falhou: {str(e)[:50]}... (continuando)")
    
    print("🎉 Migração rápida concluída!")
    
except Exception as e:
    print(f"⚠️ Erro na migração: {str(e)[:100]}")
    print("🔄 Sistema continuará normalmente")
    
finally:
    try:
        if 'conn' in locals():
            conn.close()
    except:
        pass
    
    print("⚡ Script rápido finalizado.")
