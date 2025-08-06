#!/usr/bin/env python3
"""
Script simplificado de inicialização do banco de dados
Funciona com SQLite e PostgreSQL
"""

import os
import sys
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

print("Iniciando criação do banco de dados...")

# Detectar tipo de banco baseado na DATABASE_URL
database_url = os.getenv('DATABASE_URL', '')
using_postgresql = database_url.startswith('postgresql://') and psycopg2

if using_postgresql:
    print("Usando PostgreSQL (Supabase)")
    conn = psycopg2.connect(database_url)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    cursor = conn.cursor()
    
    # Definir tipos de dados para PostgreSQL
    primary_key_type = "SERIAL PRIMARY KEY"
    text_type = "TEXT"
    integer_type = "INTEGER"
    boolean_type = "BOOLEAN"
    datetime_type = "TIMESTAMP"
    date_type = "DATE"
    param_placeholder = "%s"
    
else:
    print("Usando SQLite local")
    # Configuração do banco SQLite
    base_dir_default = os.path.abspath(os.path.dirname(__file__))
    DB_DIR = os.getenv('DB_DIR', base_dir_default)
    if not os.path.exists(DB_DIR):
        try:
            os.makedirs(DB_DIR, exist_ok=True)
        except PermissionError:
            pass
    
    db_path = os.path.join(DB_DIR, 'database.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Definir tipos de dados para SQLite
    primary_key_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
    text_type = "TEXT"
    integer_type = "INTEGER"
    boolean_type = "INTEGER"  # SQLite não tem BOOLEAN nativo
    datetime_type = "DATETIME"
    date_type = "DATE"
    param_placeholder = "?"

try:
    # Criar tabelas essenciais
    print("Criando tabelas essenciais...")
    
    # Tabela cliente
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS cliente (
        id {primary_key_type},
        nome {text_type} NOT NULL,
        cnpj {text_type},
        endereco {text_type},
        telefone {text_type},
        email {text_type},
        data_criacao {datetime_type} DEFAULT {'CURRENT_TIMESTAMP' if using_postgresql else 'CURRENT_TIMESTAMP'}
    )
    ''')
    
    # Tabela unidade_entrega
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS unidade_entrega (
        id {primary_key_type},
        nome {text_type} NOT NULL,
        cliente_id {integer_type} NOT NULL,
        endereco {text_type},
        FOREIGN KEY (cliente_id) REFERENCES cliente (id)
    )
    ''')
    
    # Tabela material
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS material (
        id {primary_key_type},
        nome {text_type} NOT NULL,
        tipo {text_type},
        material {text_type},
        liga {text_type},
        diametro REAL,
        lado REAL,
        largura REAL,
        altura REAL,
        especifico {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'}
    )
    ''')
    
    # Tabela trabalho
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS trabalho (
        id {primary_key_type},
        nome {text_type} NOT NULL,
        descricao {text_type}
    )
    ''')
    
    # Tabela item
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS item (
        id {primary_key_type},
        nome {text_type} NOT NULL UNIQUE,
        codigo_acb {text_type} UNIQUE,
        desenho_tecnico {text_type},
        imagem {text_type},
        instrucoes_trabalho {text_type},
        tempera {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        tipo_tempera {text_type},
        retifica {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        pintura {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        tipo_pintura {text_type},
        cor_pintura {text_type},
        oleo_protetivo {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        zincagem {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        tipo_zincagem {text_type},
        tipo_embalagem {text_type},
        peso REAL
    )
    ''')
    
    # Tabela item_trabalho
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS item_trabalho (
        id {primary_key_type},
        item_id {integer_type} NOT NULL,
        trabalho_id {integer_type} NOT NULL,
        tempo_setup {integer_type},
        tempo_peca {integer_type},
        tempo_real {integer_type},
        FOREIGN KEY (item_id) REFERENCES item (id),
        FOREIGN KEY (trabalho_id) REFERENCES trabalho (id)
    )
    ''')
    
    # Tabela pedido
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS pedido (
        id {primary_key_type},
        cliente_id {integer_type} NOT NULL,
        unidade_entrega_id {integer_type} NOT NULL,
        item_id {integer_type},
        nome_item {text_type},
        descricao {text_type},
        quantidade {integer_type} NOT NULL,
        data_entrada {date_type} NOT NULL DEFAULT {'CURRENT_DATE' if using_postgresql else 'CURRENT_DATE'},
        numero_pedido {text_type},
        previsao_entrega {date_type},
        numero_oc {text_type},
        numero_pedido_material {text_type},
        data_entrega {date_type},
        material_comprado {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        cancelado {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        motivo_cancelamento {text_type},
        cancelado_por {text_type},
        data_cancelamento {datetime_type},
        FOREIGN KEY (cliente_id) REFERENCES cliente (id),
        FOREIGN KEY (unidade_entrega_id) REFERENCES unidade_entrega (id),
        FOREIGN KEY (item_id) REFERENCES item (id)
    )
    ''')
    
    # Tabela ordem_servico
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS ordem_servico (
        id {primary_key_type},
        numero {text_type} UNIQUE,
        data_criacao {date_type} DEFAULT {'CURRENT_DATE' if using_postgresql else 'CURRENT_DATE'},
        status {text_type} DEFAULT 'Entrada'
    )
    ''')
    
    # Tabela pedido_ordem_servico
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS pedido_ordem_servico (
        id {primary_key_type},
        pedido_id {integer_type} NOT NULL,
        ordem_servico_id {integer_type} NOT NULL,
        FOREIGN KEY (pedido_id) REFERENCES pedido (id),
        FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id)
    )
    ''')
    
    # Tabela usuario
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS usuario (
        id {primary_key_type},
        nome {text_type} NOT NULL,
        email {text_type} UNIQUE NOT NULL,
        senha_hash {text_type} NOT NULL,
        nivel_acesso {text_type} NOT NULL DEFAULT 'usuario',
        acesso_kanban {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        acesso_estoque {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        acesso_pedidos {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        acesso_cadastros {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        pode_finalizar_os {boolean_type} DEFAULT {'FALSE' if using_postgresql else '0'},
        codigo_operador {text_type} UNIQUE,
        data_criacao {datetime_type} DEFAULT {'CURRENT_TIMESTAMP' if using_postgresql else 'CURRENT_TIMESTAMP'},
        ultimo_acesso {datetime_type}
    )
    ''')
    
    # Tabelas do módulo de apontamento
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS apontamento_producao (
        id {primary_key_type},
        ordem_servico_id {integer_type} NOT NULL,
        usuario_id {integer_type} NOT NULL,
        codigo_operador {text_type} NOT NULL,
        item_trabalho_id {integer_type},
        tipo_acao {text_type} NOT NULL,
        data_hora {datetime_type} DEFAULT {'CURRENT_TIMESTAMP' if using_postgresql else 'CURRENT_TIMESTAMP'},
        quantidade {integer_type},
        motivo_parada {text_type},
        observacoes {text_type},
        FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
        FOREIGN KEY (usuario_id) REFERENCES usuario (id)
    )
    ''')
    
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS status_producao_os (
        id {primary_key_type},
        ordem_servico_id {integer_type} UNIQUE NOT NULL,
        status_atual {text_type} NOT NULL DEFAULT 'Aguardando',
        operador_atual {text_type},
        ultimo_apontamento_id {integer_type},
        data_atualizacao {datetime_type} DEFAULT {'CURRENT_TIMESTAMP' if using_postgresql else 'CURRENT_TIMESTAMP'},
        FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
        FOREIGN KEY (ultimo_apontamento_id) REFERENCES apontamento_producao (id)
    )
    ''')
    
    print("Tabelas criadas com sucesso!")
    
    # Inserir dados básicos
    print("Inserindo dados básicos...")
    
    # Verificar se usuário admin existe
    cursor.execute("SELECT * FROM usuario WHERE email = 'admin@acbusinagem.com.br'")
    admin = cursor.fetchone()
    if not admin:
        if using_postgresql:
            cursor.execute('''
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, acesso_pedidos, acesso_kanban, acesso_estoque, acesso_cadastros, pode_finalizar_os)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', ('Administrador', 'admin@acbusinagem.com.br', generate_password_hash('admin123'), 'admin', True, True, True, True, True))
        else:
            cursor.execute('''
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, acesso_pedidos, acesso_kanban, acesso_estoque, acesso_cadastros, pode_finalizar_os)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('Administrador', 'admin@acbusinagem.com.br', generate_password_hash('admin123'), 'admin', 1, 1, 1, 1, 1))
        print("Usuário administrador criado!")
    
    # Inserir operadores de teste se não existirem
    if using_postgresql:
        cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
        result = cursor.fetchone()
        count = result[0]
    else:
        cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
        result = cursor.fetchone()
        count = result[0]
    
    if count == 0:
        print("Inserindo operadores de teste...")
        
        if using_postgresql:
            cursor.execute('''
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''', ('João Silva', 'joao@acb.com', generate_password_hash('1234'), 'operador', '1234', True))
            
            cursor.execute('''
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''', ('Maria Santos', 'maria@acb.com', generate_password_hash('5678'), 'operador', '5678', True))
        else:
            cursor.execute('''
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', ('João Silva', 'joao@acb.com', generate_password_hash('1234'), 'operador', '1234', 1))
            
            cursor.execute('''
            INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', ('Maria Santos', 'maria@acb.com', generate_password_hash('5678'), 'operador', '5678', 1))
        
        print("Operadores de teste criados!")
    
    # Inserir alguns dados de exemplo se não existirem
    cursor.execute("SELECT COUNT(*) FROM trabalho")
    result = cursor.fetchone()
    count = result[0] if using_postgresql else result[0]
    
    if count == 0:
        print("Inserindo tipos de trabalho básicos...")
        trabalhos = [
            ('Usinagem CNC', 'Usinagem em centro de usinagem CNC'),
            ('Torneamento', 'Torneamento em torno CNC'),
            ('Fresamento', 'Fresamento manual ou CNC'),
            ('Furação', 'Operações de furação'),
            ('Acabamento', 'Operações de acabamento e polimento')
        ]
        
        for nome, desc in trabalhos:
            if using_postgresql:
                cursor.execute('INSERT INTO trabalho (nome, descricao) VALUES (%s, %s)', (nome, desc))
            else:
                cursor.execute('INSERT INTO trabalho (nome, descricao) VALUES (?, ?)', (nome, desc))
        
        print("Tipos de trabalho criados!")
    
    # Commit das alterações
    conn.commit()
    print("Banco de dados inicializado com sucesso!")
    
except Exception as e:
    print(f"Erro ao inicializar banco de dados: {e}")
    conn.rollback()
    sys.exit(1)
    
finally:
    conn.close()

print("Inicialização concluída!")
