#!/usr/bin/env python3
"""
Script para verificar tipos de trabalho no banco Supabase
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# Configurar variáveis de ambiente
os.environ['DATABASE_URL'] = "postgresql://postgres.rxkuxdtpmrpfrufvnjxa:PIRULLITTO12@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"

print("Verificando tipos de trabalho no Supabase...")

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
    
    # 1. Verificar se tabela trabalho existe
    print("\n1. Verificando tabela 'trabalho'...")
    cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'trabalho'
    );
    """)
    tabela_existe = cursor.fetchone()['exists']
    
    if not tabela_existe:
        print("[ERRO] Tabela 'trabalho' não existe! Criando...")
        
        # Criar tabela trabalho
        cursor.execute("""
        CREATE TABLE trabalho (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            descricao TEXT
        );
        """)
        
        # Inserir tipos básicos
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
        
        print("[OK] Tabela 'trabalho' criada e populada com tipos básicos")
    else:
        print("[OK] Tabela 'trabalho' existe")
    
    # 2. Listar todos os tipos de trabalho
    print("\n2. Tipos de trabalho cadastrados:")
    cursor.execute("SELECT id, nome, descricao FROM trabalho ORDER BY nome")
    tipos = cursor.fetchall()
    
    if tipos:
        for tipo in tipos:
            print(f"   ID: {tipo['id']} | Nome: {tipo['nome']} | Desc: {tipo['descricao'] or 'N/A'}")
    else:
        print("[ERRO] Nenhum tipo de trabalho encontrado!")
    
    # 3. Verificar tabela item_trabalho
    print("\n3. Verificando tabela 'item_trabalho'...")
    cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'item_trabalho'
    );
    """)
    tabela_item_trabalho_existe = cursor.fetchone()['exists']
    
    if not tabela_item_trabalho_existe:
        print("[ERRO] Tabela 'item_trabalho' não existe! Criando...")
        cursor.execute("""
        CREATE TABLE item_trabalho (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL,
            trabalho_id INTEGER NOT NULL,
            tempo_setup INTEGER,
            tempo_peca INTEGER,
            tempo_real INTEGER,
            FOREIGN KEY (item_id) REFERENCES item (id),
            FOREIGN KEY (trabalho_id) REFERENCES trabalho (id)
        );
        """)
        print("[OK] Tabela 'item_trabalho' criada")
    else:
        print("[OK] Tabela 'item_trabalho' existe")
    
    # 4. Verificar se existem itens e vincular com trabalhos
    print("\n4. Verificando itens e vinculações...")
    cursor.execute("SELECT COUNT(*) as count FROM item")
    count_itens = cursor.fetchone()['count']
    print(f"   Itens cadastrados: {count_itens}")
    
    cursor.execute("SELECT COUNT(*) as count FROM item_trabalho")
    count_vinculacoes = cursor.fetchone()['count']
    print(f"   Vinculações item-trabalho: {count_vinculacoes}")
    
    # Se não há vinculações, criar algumas básicas
    if count_vinculacoes == 0 and count_itens > 0:
        print("   Criando vinculações básicas...")
        
        # Buscar alguns itens e tipos de trabalho
        cursor.execute("SELECT id FROM item LIMIT 5")
        itens = cursor.fetchall()
        
        cursor.execute("SELECT id FROM trabalho LIMIT 3")
        trabalhos = cursor.fetchall()
        
        # Criar vinculações básicas
        for item in itens:
            for trabalho in trabalhos:
                cursor.execute("""
                INSERT INTO item_trabalho (item_id, trabalho_id, tempo_setup, tempo_peca)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """, (item['id'], trabalho['id'], 1800, 300))  # 30min setup, 5min por peça
        
        print("   [OK] Vinculações básicas criadas")
    
    # 5. Testar a consulta da rota
    print("\n5. Testando consulta da rota para OS #1...")
    cursor.execute("""
    SELECT DISTINCT t.id, t.nome, t.descricao
    FROM trabalho t
    JOIN item_trabalho it ON t.id = it.trabalho_id
    JOIN item i ON it.item_id = i.id
    JOIN pedido p ON i.id = p.item_id
    JOIN pedido_ordem_servico pos ON p.id = pos.pedido_id
    WHERE pos.ordem_servico_id = 1
    """)
    
    tipos_os = cursor.fetchall()
    if tipos_os:
        print("   [OK] Tipos de trabalho encontrados para OS #1:")
        for tipo in tipos_os:
            print(f"      ID: {tipo['id']} | Nome: {tipo['nome']}")
    else:
        print("   [AVISO] Nenhum tipo específico encontrado para OS #1")
        print("   (Sistema usará todos os tipos disponíveis como fallback)")
    
    print(f"[SUCESSO] Verificação concluída! Total de tipos: {len(tipos)}")
    
except Exception as e:
    print(f"[ERRO] Erro: {e}")
    
finally:
    if 'conn' in locals():
        conn.close()
        print("Conexão fechada.")
