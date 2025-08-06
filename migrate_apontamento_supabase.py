#!/usr/bin/env python3
"""
Script para migrar/criar tabelas do módulo de apontamento no Supabase/PostgreSQL
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

print("Iniciando migração do módulo de apontamento para Supabase/PostgreSQL...")

# Obter URL do banco
database_url = os.getenv('DATABASE_URL')
if not database_url or not database_url.startswith('postgresql://'):
    print("DATABASE_URL não configurada ou não é PostgreSQL")
    exit(1)

# Parse da URL
parsed = urlparse(database_url)

try:
    # Conectar ao PostgreSQL
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],  # Remove o '/' inicial
        user=parsed.username,
        password=parsed.password
    )
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("Conectado ao PostgreSQL/Supabase com sucesso!")
    
    # 1. Adicionar coluna codigo_operador na tabela usuario se não existir
    print("Verificando coluna codigo_operador na tabela usuario...")
    try:
        cursor.execute("""
        ALTER TABLE usuario ADD COLUMN codigo_operador TEXT UNIQUE;
        """)
        print("[OK] Coluna codigo_operador adicionada à tabela usuario")
    except psycopg2.errors.DuplicateColumn:
        print("[OK] Coluna codigo_operador já existe na tabela usuario")
    except Exception as e:
        print(f"⚠️ Erro ao adicionar coluna codigo_operador: {e}")
    
    # 2. Criar tabela apontamento_producao
    print("Criando tabela apontamento_producao...")
    cursor.execute("""
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
        observacoes TEXT,
        CONSTRAINT fk_apontamento_os FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
        CONSTRAINT fk_apontamento_usuario FOREIGN KEY (usuario_id) REFERENCES usuario (id),
        CONSTRAINT fk_apontamento_item FOREIGN KEY (item_id) REFERENCES item (id),
        CONSTRAINT fk_apontamento_trabalho FOREIGN KEY (trabalho_id) REFERENCES trabalho (id)
    );
    """)
    print("[OK] Tabela apontamento_producao criada/verificada")
    
    # 3. Criar tabela status_producao_os
    print("Criando tabela status_producao_os...")
    cursor.execute("""
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
        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_status_os FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
        CONSTRAINT fk_status_operador FOREIGN KEY (operador_atual_id) REFERENCES usuario (id),
        CONSTRAINT fk_status_item FOREIGN KEY (item_atual_id) REFERENCES item (id),
        CONSTRAINT fk_status_trabalho FOREIGN KEY (trabalho_atual_id) REFERENCES trabalho (id)
    );
    """)
    print("[OK] Tabela status_producao_os criada/verificada")
    
    # 4. Inserir operadores de teste se não existirem
    print("Verificando operadores de teste...")
    cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
    result = cursor.fetchone()
    count = result['count'] if result else 0
    
    if count == 0:
        print("Inserindo operadores de teste...")
        
        # Verificar se usuários já existem
        cursor.execute("SELECT id FROM usuario WHERE email = 'joao@acb.com'")
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, ('João Silva', 'joao@acb.com', 'pbkdf2:sha256:600000$salt$hash', 'operador', '1234', True))
            print("[OK] Operador João Silva (1234) criado")
        
        cursor.execute("SELECT id FROM usuario WHERE email = 'maria@acb.com'")
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, ('Maria Santos', 'maria@acb.com', 'pbkdf2:sha256:600000$salt$hash', 'operador', '5678', True))
            print("[OK] Operador Maria Santos (5678) criado")
    else:
        print(f"[OK] {count} operadores já existem no banco")
    
    # 5. Verificar se existem ordens de serviço para teste
    cursor.execute("SELECT COUNT(*) FROM ordem_servico")
    result = cursor.fetchone()
    os_count = result['count'] if result else 0
    
    if os_count == 0:
        print("Nenhuma ordem de serviço encontrada. O módulo de apontamento precisa de OS para funcionar.")
        print("   Crie algumas ordens de serviço através do sistema para testar o módulo de apontamento.")
    else:
        print(f"[OK] {os_count} ordens de serviço encontradas no banco")
    
    print("\nMigração do módulo de apontamento concluída com sucesso!")
    print("\nTabelas criadas/verificadas:")
    print("- usuario (com coluna codigo_operador)")
    print("- apontamento_producao")
    print("- status_producao_os")
    print("\nOperadores de teste:")
    print("- João Silva (código: 1234)")
    print("- Maria Santos (código: 5678)")
    
except Exception as e:
    print(f"[ERRO] Erro durante a migração: {e}")
    raise
    
finally:
    if 'conn' in locals():
        conn.close()
        print("Conexão fechada.")
