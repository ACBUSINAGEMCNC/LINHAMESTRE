#!/usr/bin/env python3
"""
Script para corrigir a tabela trabalho no Supabase
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# Configurar variáveis de ambiente
os.environ['DATABASE_URL'] = "postgresql://postgres.rxkuxdtpmrpfrufvnjxa:PIRULLITTO12@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"

print("Corrigindo tabela 'trabalho' no Supabase...")

# Obter URL do banco
database_url = os.getenv('DATABASE_URL')
parsed = urlparse(database_url)

try:
    # Conectar ao PostgreSQL
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],
        user=parsed.username,
        password=parsed.password
    )
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("Conectado ao PostgreSQL/Supabase com sucesso!")
    
    # 1. Verificar estrutura atual da tabela trabalho
    print("\n1. Verificando estrutura atual da tabela 'trabalho'...")
    cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'trabalho'
    ORDER BY ordinal_position;
    """)
    
    colunas = cursor.fetchall()
    print("   Colunas atuais:")
    for coluna in colunas:
        print(f"   - {coluna['column_name']}: {coluna['data_type']}")
    
    # 2. Adicionar coluna descricao se não existir
    tem_descricao = any(col['column_name'] == 'descricao' for col in colunas)
    
    if not tem_descricao:
        print("\n2. Adicionando coluna 'descricao'...")
        cursor.execute("ALTER TABLE trabalho ADD COLUMN descricao TEXT;")
        print("   [OK] Coluna 'descricao' adicionada")
    else:
        print("\n2. Coluna 'descricao' já existe")
    
    # 3. Verificar se há tipos de trabalho cadastrados
    print("\n3. Verificando tipos de trabalho cadastrados...")
    cursor.execute("SELECT COUNT(*) as count FROM trabalho")
    count = cursor.fetchone()['count']
    print(f"   Total de tipos: {count}")
    
    if count == 0:
        print("   Inserindo tipos básicos de trabalho...")
        tipos_basicos = [
            ('Usinagem CNC', 'Usinagem em centro de usinagem CNC'),
            ('Torneamento', 'Torneamento em torno CNC'),
            ('Fresamento', 'Fresamento manual ou CNC'),
            ('Furação', 'Operações de furação'),
            ('Acabamento', 'Operações de acabamento e polimento'),
            ('Desbaste', 'Operações de desbaste inicial'),
            ('Rebarbação', 'Remoção de rebarbas'),
            ('Inspeção', 'Controle de qualidade e inspeção')
        ]
        
        for nome, desc in tipos_basicos:
            cursor.execute("""
            INSERT INTO trabalho (nome, descricao) VALUES (%s, %s)
            """, (nome, desc))
        
        print(f"   [OK] {len(tipos_basicos)} tipos básicos inseridos")
    
    # 4. Listar todos os tipos de trabalho
    print("\n4. Tipos de trabalho finais:")
    cursor.execute("SELECT id, nome, descricao FROM trabalho ORDER BY nome")
    tipos = cursor.fetchall()
    
    for tipo in tipos:
        print(f"   ID: {tipo['id']} | Nome: {tipo['nome']} | Desc: {tipo['descricao'] or 'N/A'}")
    
    # 5. Testar a rota de tipos de trabalho
    print("\n5. Testando consulta da rota...")
    cursor.execute("SELECT id, nome, descricao FROM trabalho ORDER BY nome LIMIT 3")
    tipos_teste = cursor.fetchall()
    
    print("   Resultado da consulta (formato JSON):")
    for tipo in tipos_teste:
        print(f"   {{\"id\": {tipo['id']}, \"nome\": \"{tipo['nome']}\", \"descricao\": \"{tipo['descricao'] or ''}\"}}") 
    
    print(f"\n[SUCESSO] Tabela 'trabalho' corrigida! Total: {len(tipos)} tipos")
    
except Exception as e:
    print(f"[ERRO] Erro: {e}")
    
finally:
    if 'conn' in locals():
        conn.close()
        print("Conexão fechada.")
