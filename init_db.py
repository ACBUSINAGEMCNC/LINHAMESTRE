import os
import sys
import sqlite3
from datetime import datetime
try:
    import psycopg2
except ImportError:
    psycopg2 = None

print("Iniciando criação do banco de dados...")

# Detectar tipo de banco baseado na DATABASE_URL
database_url = os.getenv('DATABASE_URL', '')
using_postgresql = database_url.startswith('postgresql://') and psycopg2

if using_postgresql:
    print("Usando PostgreSQL (Supabase)")
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    # PostgreSQL usa %s para parâmetros
    param_placeholder = '%s'
else:
    print("Usando SQLite local")
    # Configuração do banco SQLite
    base_dir_default = os.path.abspath(os.path.dirname(__file__))
    DB_DIR = os.getenv('DB_DIR', base_dir_default)
    if not os.path.exists(DB_DIR):
        try:
            os.makedirs(DB_DIR, exist_ok=True)
        except PermissionError:
            pass  # ambiente read-only
    
    db_path = os.path.join(DB_DIR, 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # SQLite usa ? para parâmetros
    param_placeholder = '?'

# Criar tabela cliente
cursor.execute('''
CREATE TABLE IF NOT EXISTS cliente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cnpj TEXT,
    endereco TEXT,
    telefone TEXT,
    email TEXT,
    contato TEXT
)
''')

# Criar tabela unidade_entrega
cursor.execute('''
CREATE TABLE IF NOT EXISTS unidade_entrega (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    nome TEXT NOT NULL,
    endereco TEXT,
    telefone TEXT,
    email TEXT,
    contato TEXT,
    FOREIGN KEY (cliente_id) REFERENCES cliente (id)
)
''')

# Criar tabela material
cursor.execute('''
CREATE TABLE IF NOT EXISTS material (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo TEXT,
    material TEXT,
    liga TEXT,
    diametro FLOAT,
    lado FLOAT,
    largura FLOAT,
    altura FLOAT,
    especifico BOOLEAN DEFAULT 0,
    descricao TEXT
)
''')

# Criar tabela trabalho
cursor.execute('''
CREATE TABLE IF NOT EXISTS trabalho (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    categoria TEXT
)
''')

# Criar tabela item_trabalho
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

# Criar tabela item_material
cursor.execute('''
CREATE TABLE IF NOT EXISTS item_material (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    comprimento FLOAT,
    quantidade INTEGER DEFAULT 1,
    FOREIGN KEY (item_id) REFERENCES item (id),
    FOREIGN KEY (material_id) REFERENCES material (id)
)
''')

# Criar tabela item
cursor.execute('''
CREATE TABLE IF NOT EXISTS item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    codigo_acb TEXT UNIQUE,
    desenho_tecnico TEXT,
    imagem TEXT,
    instrucoes_trabalho TEXT,
    tempera BOOLEAN DEFAULT 0,
    tipo_tempera TEXT,
    retifica BOOLEAN DEFAULT 0,
    pintura BOOLEAN DEFAULT 0,
    tipo_pintura TEXT,
    cor_pintura TEXT,
    oleo_protetivo BOOLEAN DEFAULT 0,
    zincagem BOOLEAN DEFAULT 0,
    tipo_zincagem TEXT,
    tipo_embalagem TEXT,
    peso FLOAT
)
''')

# Criar tabela pedido
cursor.execute('''
CREATE TABLE IF NOT EXISTS pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    unidade_entrega_id INTEGER NOT NULL,
    item_id INTEGER,
    nome_item TEXT,
    descricao TEXT,
    quantidade INTEGER NOT NULL,
    data_entrada DATE NOT NULL,
    numero_pedido TEXT,
    previsao_entrega DATE,
    numero_oc TEXT,
    numero_pedido_material TEXT,
    data_entrega DATE,
    material_comprado BOOLEAN DEFAULT 0,
    FOREIGN KEY (cliente_id) REFERENCES cliente (id),
    FOREIGN KEY (unidade_entrega_id) REFERENCES unidade_entrega (id),
    FOREIGN KEY (item_id) REFERENCES item (id)
)
''')

# Criar tabela ordem_servico
cursor.execute('''
CREATE TABLE IF NOT EXISTS ordem_servico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL UNIQUE,
    data_criacao DATE DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'Entrada'
)
''')

# Criar tabela pedido_ordem_servico
cursor.execute('''
CREATE TABLE IF NOT EXISTS pedido_ordem_servico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL,
    ordem_servico_id INTEGER NOT NULL,
    FOREIGN KEY (pedido_id) REFERENCES pedido (id),
    FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id)
)
''')

# Criar tabela pedido_material
cursor.execute('''
CREATE TABLE IF NOT EXISTS pedido_material (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL UNIQUE,
    data_criacao DATE DEFAULT CURRENT_DATE
)
''')

# Criar tabela item_pedido_material
cursor.execute('''
CREATE TABLE IF NOT EXISTS item_pedido_material (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_material_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    comprimento FLOAT,
    quantidade INTEGER,
    sufixo TEXT DEFAULT '',
    FOREIGN KEY (pedido_material_id) REFERENCES pedido_material (id),
    FOREIGN KEY (material_id) REFERENCES material (id)
)
''')

# Criar tabela estoque
cursor.execute('''
CREATE TABLE IF NOT EXISTS estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    quantidade INTEGER DEFAULT 0,
    comprimento_total FLOAT DEFAULT 0,
    FOREIGN KEY (material_id) REFERENCES material (id)
)
''')

# Criar tabela movimentacao_estoque
cursor.execute('''
CREATE TABLE IF NOT EXISTS movimentacao_estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estoque_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    comprimento FLOAT,
    data DATE DEFAULT CURRENT_DATE,
    referencia TEXT,
    observacao TEXT,
    FOREIGN KEY (estoque_id) REFERENCES estoque (id)
)
''')

# Criar tabela estoque_pecas
cursor.execute('''
CREATE TABLE IF NOT EXISTS estoque_pecas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    quantidade INTEGER DEFAULT 0,
    data_entrada DATE DEFAULT CURRENT_DATE,
    prateleira TEXT,
    posicao TEXT,
    observacao TEXT,
    FOREIGN KEY (item_id) REFERENCES item (id)
)
''')

# Criar tabela movimentacao_estoque_pecas
cursor.execute('''
CREATE TABLE IF NOT EXISTS movimentacao_estoque_pecas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estoque_pecas_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    data DATE DEFAULT CURRENT_DATE,
    referencia TEXT,
    observacao TEXT,
    FOREIGN KEY (estoque_pecas_id) REFERENCES estoque_pecas (id)
)
''')

# Criar tabela registro_mensal
cursor.execute('''
CREATE TABLE IF NOT EXISTS registro_mensal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem_servico_id INTEGER NOT NULL,
    data_finalizacao DATE DEFAULT CURRENT_DATE,
    mes_referencia TEXT,
    FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id)
)
''')

# Criar tabela usuario
cursor.execute('''
CREATE TABLE IF NOT EXISTS usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    nivel_acesso TEXT NOT NULL DEFAULT 'usuario',
    acesso_kanban BOOLEAN DEFAULT 0,
    acesso_estoque BOOLEAN DEFAULT 0,
    acesso_pedidos BOOLEAN DEFAULT 0,
    acesso_cadastros BOOLEAN DEFAULT 0,
    pode_finalizar_os BOOLEAN DEFAULT 0,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_acesso TIMESTAMP
)
''')

# Criar tabela backup
cursor.execute('''
CREATE TABLE IF NOT EXISTS backup (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_arquivo TEXT NOT NULL,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tamanho INTEGER,
    usuario_id INTEGER,
    descricao TEXT,
    automatico BOOLEAN DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuario (id)
)
''')

# Criar usuário administrador padrão
from werkzeug.security import generate_password_hash
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
    print("Usuário administrador padrão criado com sucesso!")
else:
    print("Usuário administrador já existe!")

# ===== SISTEMA DE APONTAMENTO =====
print("Criando tabelas do sistema de apontamento...")

# Adicionar campo codigo_operador na tabela usuario (se não existir)
try:
    cursor.execute("ALTER TABLE usuario ADD COLUMN codigo_operador VARCHAR(4)")
    print("✅ Campo codigo_operador adicionado na tabela usuario")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("ℹ️ Campo codigo_operador já existe na tabela usuario")
    else:
        print(f"⚠️ Erro ao adicionar campo codigo_operador: {e}")

# Criar tabela apontamento_producao
cursor.execute('''
CREATE TABLE IF NOT EXISTS apontamento_producao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem_servico_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    item_trabalho_id INTEGER NOT NULL,
    tipo_acao VARCHAR(20) NOT NULL,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
    quantidade INTEGER,
    motivo_parada VARCHAR(100),
    tempo_decorrido INTEGER,
    lista_kanban VARCHAR(100),
    observacoes TEXT,
    FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
    FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    FOREIGN KEY (item_trabalho_id) REFERENCES item_trabalho (id)
)
''')
print("✅ Tabela apontamento_producao criada")

# Criar tabela status_producao_os
cursor.execute('''
CREATE TABLE IF NOT EXISTS status_producao_os (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem_servico_id INTEGER UNIQUE NOT NULL,
    status_atual VARCHAR(50) DEFAULT 'Aguardando',
    operador_atual_id INTEGER,
    item_trabalho_atual_id INTEGER,
    inicio_acao DATETIME,
    quantidade_atual INTEGER DEFAULT 0,
    previsao_termino DATETIME,
    eficiencia_percentual REAL,
    motivo_pausa VARCHAR(100),
    data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
    FOREIGN KEY (operador_atual_id) REFERENCES usuario (id),
    FOREIGN KEY (item_trabalho_atual_id) REFERENCES item_trabalho (id)
)
''')
print("✅ Tabela status_producao_os criada")

# Criar índices para melhor performance
indices_apontamento = [
    "CREATE INDEX IF NOT EXISTS idx_apontamento_os ON apontamento_producao(ordem_servico_id)",
    "CREATE INDEX IF NOT EXISTS idx_apontamento_usuario ON apontamento_producao(usuario_id)",
    "CREATE INDEX IF NOT EXISTS idx_apontamento_data ON apontamento_producao(data_hora)",
    "CREATE INDEX IF NOT EXISTS idx_status_os ON status_producao_os(ordem_servico_id)",
    "CREATE INDEX IF NOT EXISTS idx_usuario_codigo ON usuario(codigo_operador)"
]

for indice in indices_apontamento:
    cursor.execute(indice)
print("✅ Índices do sistema de apontamento criados")

print("✅ Sistema de apontamento configurado com sucesso!")

# Commit das alterações e fechar conexão
conn.commit()

# Verificar se as tabelas foram criadas corretamente
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tabelas = cursor.fetchall()
print(f"Tabelas criadas: {[tabela[0] for tabela in tabelas]}")

conn.close()

print("\nBanco de dados inicializado com sucesso!")
print("\nAgora você pode executar a aplicação com o comando: python run.py")
