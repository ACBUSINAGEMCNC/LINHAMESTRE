#!/usr/bin/env python3
"""
Script para migrar/criar tabelas do módulo de apontamento no Supabase/PostgreSQL
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import signal

# Timeout handler
def timeout_handler(signum, frame):
    print("⚠️ Timeout na migração - abortando...")
    sys.exit(1)

# Definir timeout de 60 segundos
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(60)

print("Iniciando migração do módulo de apontamento para Supabase/PostgreSQL...")

# Obter URL do banco
database_url = os.getenv('DATABASE_URL')
if not database_url or not database_url.startswith('postgresql://'):
    print("DATABASE_URL não configurada ou não é PostgreSQL")
    exit(1)

# Parse da URL
parsed = urlparse(database_url)

try:
    # Conectar ao PostgreSQL com timeout
    print("Conectando ao PostgreSQL/Supabase...")
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path[1:],  # Remove o '/' inicial
        user=parsed.username,
        password=parsed.password,
        connect_timeout=5  # Timeout de 5 segundos
    )
    conn.autocommit = True
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Definir timeout para statements
    cursor.execute("SET statement_timeout = '10s'")
    
    print("Conectado ao PostgreSQL/Supabase com sucesso!")
    
    # 1. Verificar se coluna codigo_operador existe na tabela usuario
    print("Verificando coluna codigo_operador na tabela usuario...")
    try:
        # Verificar se a tabela usuario existe primeiro
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'usuario'
        )
        """)
        
        if not cursor.fetchone()[0]:
            print("⚠️ Tabela usuario não existe - pulando migração de coluna")
        else:
            # Verificar se a coluna já existe
            cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'usuario' AND column_name = 'codigo_operador'
            """)
            
            if cursor.fetchone():
                print("[OK] Coluna codigo_operador já existe na tabela usuario")
            else:
                # Coluna não existe, tentar adicionar sem UNIQUE primeiro
                print("Adicionando coluna codigo_operador...")
                cursor.execute("""
                ALTER TABLE usuario ADD COLUMN codigo_operador TEXT;
                """)
                print("[OK] Coluna codigo_operador adicionada à tabela usuario")
                
                # Tentar adicionar constraint UNIQUE separadamente
                try:
                    cursor.execute("""
                    ALTER TABLE usuario ADD CONSTRAINT usuario_codigo_operador_unique UNIQUE (codigo_operador);
                    """)
                    print("[OK] Constraint UNIQUE adicionada para codigo_operador")
                except Exception as ue:
                    print(f"⚠️ Não foi possível adicionar constraint UNIQUE: {ue}")
            
    except Exception as e:
        print(f"⚠️ Erro ao verificar/adicionar coluna codigo_operador: {e}")
        # Não falhar por causa disso, continuar com o resto da migração
    
    # 2. Criar tabela apontamento_producao
    print("Criando tabela apontamento_producao...")
    try:
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
    except Exception as e:
        print(f"⚠️ Erro ao criar tabela apontamento_producao: {e}")
    
    # 3. Criar tabela status_producao_os
    print("Criando tabela status_producao_os...")
    try:
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
    except Exception as e:
        print(f"⚠️ Erro ao criar tabela status_producao_os: {e}")
    
    # 4. Inserir operadores de teste se não existirem
    print("Verificando operadores de teste...")
    try:
        cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
        result = cursor.fetchone()
        count = result['count'] if result else 0
    except Exception as e:
        print(f"⚠️ Erro ao verificar operadores: {e}")
        count = 0
    
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
    try:
        cursor.execute("SELECT COUNT(*) FROM ordem_servico")
        result = cursor.fetchone()
        os_count = result['count'] if result else 0
    except Exception as e:
        print(f"⚠️ Erro ao verificar ordens de serviço: {e}")
        os_count = 0
    
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
    # Cancelar alarm
    signal.alarm(0)
    
    if 'conn' in locals():
        conn.close()
        print("Conexão fechada.")
        
    print("Script de migração finalizado.")
