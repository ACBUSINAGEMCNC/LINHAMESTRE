#!/usr/bin/env python3
"""
Script de inicialização APENAS para SQLite local
Ignora completamente PostgreSQL/Supabase
"""

import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

print("Iniciando criação do banco de dados SQLite local...")

# Forçar SQLite local
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

try:
    print("Criando tabelas essenciais...")
    
    # Tabela cliente
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cliente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cnpj TEXT,
        endereco TEXT,
        telefone TEXT,
        email TEXT,
        data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabela unidade_entrega
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS unidade_entrega (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cliente_id INTEGER NOT NULL,
        endereco TEXT,
        FOREIGN KEY (cliente_id) REFERENCES cliente (id)
    )
    ''')
    
    # Tabela material
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS material (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT,
        material TEXT,
        liga TEXT,
        diametro REAL,
        lado REAL,
        largura REAL,
        altura REAL,
        especifico INTEGER DEFAULT 0
    )
    ''')
    
    # Tabela trabalho
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trabalho (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT
    )
    ''')
    
    # Tabela item
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        codigo_acb TEXT UNIQUE,
        desenho_tecnico TEXT,
        imagem TEXT,
        instrucoes_trabalho TEXT,
        tempera INTEGER DEFAULT 0,
        tipo_tempera TEXT,
        retifica INTEGER DEFAULT 0,
        pintura INTEGER DEFAULT 0,
        tipo_pintura TEXT,
        cor_pintura TEXT,
        oleo_protetivo INTEGER DEFAULT 0,
        zincagem INTEGER DEFAULT 0,
        tipo_zincagem TEXT,
        tipo_embalagem TEXT,
        peso REAL
    )
    ''')
    
    # Tabela item_trabalho
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS item_trabalho (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        trabalho_id INTEGER NOT NULL,
        tempo_setup INTEGER,
        tempo_peca INTEGER,
        tempo_real INTEGER,
        FOREIGN KEY (item_id) REFERENCES item (id),
        FOREIGN KEY (trabalho_id) REFERENCES trabalho (id)
    )
    ''')
    
    # Tabela pedido
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        unidade_entrega_id INTEGER NOT NULL,
        item_id INTEGER,
        nome_item TEXT,
        descricao TEXT,
        quantidade INTEGER NOT NULL,
        data_entrada DATE NOT NULL DEFAULT CURRENT_DATE,
        numero_pedido TEXT,
        previsao_entrega DATE,
        numero_oc TEXT,
        numero_pedido_material TEXT,
        data_entrega DATE,
        material_comprado INTEGER DEFAULT 0,
        cancelado INTEGER DEFAULT 0,
        motivo_cancelamento TEXT,
        cancelado_por TEXT,
        data_cancelamento DATETIME,
        FOREIGN KEY (cliente_id) REFERENCES cliente (id),
        FOREIGN KEY (unidade_entrega_id) REFERENCES unidade_entrega (id),
        FOREIGN KEY (item_id) REFERENCES item (id)
    )
    ''')
    
    # Tabela ordem_servico
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ordem_servico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE,
        data_criacao DATE DEFAULT CURRENT_DATE,
        status TEXT DEFAULT 'Entrada'
    )
    ''')
    
    # Tabela pedido_ordem_servico
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pedido_ordem_servico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL,
        ordem_servico_id INTEGER NOT NULL,
        FOREIGN KEY (pedido_id) REFERENCES pedido (id),
        FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id)
    )
    ''')
    
    # Tabela usuario
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        nivel_acesso TEXT NOT NULL DEFAULT 'usuario',
        acesso_kanban INTEGER DEFAULT 0,
        acesso_estoque INTEGER DEFAULT 0,
        acesso_pedidos INTEGER DEFAULT 0,
        acesso_cadastros INTEGER DEFAULT 0,
        pode_finalizar_os INTEGER DEFAULT 0,
        codigo_operador TEXT UNIQUE,
        data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        ultimo_acesso DATETIME
    )
    ''')
    
    # Tabelas do módulo de apontamento
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS apontamento_producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ordem_servico_id INTEGER NOT NULL,
        usuario_id INTEGER NOT NULL,
        codigo_operador TEXT NOT NULL,
        item_trabalho_id INTEGER,
        tipo_acao TEXT NOT NULL,
        data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
        quantidade INTEGER,
        motivo_parada TEXT,
        observacoes TEXT,
        FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
        FOREIGN KEY (usuario_id) REFERENCES usuario (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS status_producao_os (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ordem_servico_id INTEGER UNIQUE NOT NULL,
        status_atual TEXT NOT NULL DEFAULT 'Aguardando',
        operador_atual TEXT,
        ultimo_apontamento_id INTEGER,
        data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
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
        cursor.execute('''
        INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, acesso_pedidos, acesso_kanban, acesso_estoque, acesso_cadastros, pode_finalizar_os)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Administrador', 'admin@acbusinagem.com.br', generate_password_hash('admin123'), 'admin', 1, 1, 1, 1, 1))
        print("Usuário administrador criado!")
    
    # Inserir operadores de teste se não existirem
    cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
    result = cursor.fetchone()
    count = result[0]
    
    if count == 0:
        print("Inserindo operadores de teste...")
        
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
    count = result[0]
    
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
            cursor.execute('INSERT INTO trabalho (nome, descricao) VALUES (?, ?)', (nome, desc))
        
        print("Tipos de trabalho criados!")
    
    # Inserir alguns dados de exemplo para teste
    cursor.execute("SELECT COUNT(*) FROM cliente")
    result = cursor.fetchone()
    count = result[0]
    
    if count == 0:
        print("Inserindo dados de exemplo...")
        
        # Cliente exemplo
        cursor.execute('''
        INSERT INTO cliente (nome, cnpj, endereco, telefone, email)
        VALUES (?, ?, ?, ?, ?)
        ''', ('Cliente Exemplo', '12.345.678/0001-90', 'Rua Exemplo, 123', '(11) 1234-5678', 'cliente@exemplo.com'))
        
        cliente_id = cursor.lastrowid
        
        # Unidade de entrega
        cursor.execute('''
        INSERT INTO unidade_entrega (nome, cliente_id, endereco)
        VALUES (?, ?, ?)
        ''', ('Matriz', cliente_id, 'Rua Exemplo, 123'))
        
        unidade_id = cursor.lastrowid
        
        # Item exemplo
        cursor.execute('''
        INSERT INTO item (nome, codigo_acb)
        VALUES (?, ?)
        ''', ('Peça Exemplo', 'ACB-001'))
        
        item_id = cursor.lastrowid
        
        # Relacionar item com trabalho
        cursor.execute('''
        INSERT INTO item_trabalho (item_id, trabalho_id, tempo_setup, tempo_peca)
        VALUES (?, ?, ?, ?)
        ''', (item_id, 1, 1800, 300))  # 30min setup, 5min por peça
        
        # Pedido exemplo
        cursor.execute('''
        INSERT INTO pedido (cliente_id, unidade_entrega_id, item_id, nome_item, descricao, quantidade, numero_pedido)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (cliente_id, unidade_id, item_id, 'Peça Exemplo', 'Peça de exemplo para teste', 10, 'PED-001'))
        
        pedido_id = cursor.lastrowid
        
        # Ordem de serviço exemplo
        cursor.execute('''
        INSERT INTO ordem_servico (numero, status)
        VALUES (?, ?)
        ''', ('OS-001', 'Aguardando'))
        
        os_id = cursor.lastrowid
        
        # Relacionar pedido com OS
        cursor.execute('''
        INSERT INTO pedido_ordem_servico (pedido_id, ordem_servico_id)
        VALUES (?, ?)
        ''', (pedido_id, os_id))
        
        # Mais algumas OS para teste
        for i in range(2, 6):
            cursor.execute('''
            INSERT INTO ordem_servico (numero, status)
            VALUES (?, ?)
            ''', (f'OS-{i:03d}', ['Aguardando', 'Setup', 'Em Produção', 'Pausado'][i % 4]))
            
            os_id = cursor.lastrowid
            
            cursor.execute('''
            INSERT INTO pedido (cliente_id, unidade_entrega_id, item_id, nome_item, descricao, quantidade, numero_pedido)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (cliente_id, unidade_id, item_id, f'Peça {i}', f'Peça de exemplo {i}', 5 + i, f'PED-{i:03d}'))
            
            pedido_id = cursor.lastrowid
            
            cursor.execute('''
            INSERT INTO pedido_ordem_servico (pedido_id, ordem_servico_id)
            VALUES (?, ?)
            ''', (pedido_id, os_id))
        
        print("Dados de exemplo criados!")
    
    # Commit das alterações
    conn.commit()
    print("Banco de dados SQLite inicializado com sucesso!")
    
except Exception as e:
    print(f"Erro ao inicializar banco de dados: {e}")
    conn.rollback()
    raise
    
finally:
    conn.close()

print("Inicialização SQLite concluída!")
