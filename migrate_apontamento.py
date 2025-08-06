#!/usr/bin/env python3
"""
Script para migrar/atualizar o banco de dados com as tabelas do módulo de apontamento
"""

import os
import sqlite3
import psycopg2
from werkzeug.security import generate_password_hash

def migrate_sqlite():
    """Migração para SQLite"""
    print("Migrando banco SQLite...")
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    try:
        # Verificar se coluna codigo_operador existe na tabela usuario
        cursor.execute("PRAGMA table_info(usuario)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'codigo_operador' not in columns:
            print("Adicionando coluna codigo_operador à tabela usuario...")
            cursor.execute('ALTER TABLE usuario ADD COLUMN codigo_operador TEXT UNIQUE')
            
        # Criar tabela apontamento_producao se não existir
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
        
        # Criar tabela status_producao_os se não existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status_producao_os (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_servico_id INTEGER UNIQUE NOT NULL,
                status_atual TEXT NOT NULL,
                operador_atual TEXT,
                ultimo_apontamento_id INTEGER,
                data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
                FOREIGN KEY (ultimo_apontamento_id) REFERENCES apontamento_producao (id)
            )
        ''')
        
        # Inserir operadores de teste se não existirem
        cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
        if cursor.fetchone()[0] == 0:
            print("Inserindo operadores de teste...")
            
            # Verificar se usuários já existem
            cursor.execute("SELECT id FROM usuario WHERE email = 'joao@acb.com'")
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('João Silva', 'joao@acb.com', generate_password_hash('1234'), 'operador', '1234', 1))
            
            cursor.execute("SELECT id FROM usuario WHERE email = 'maria@acb.com'")
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('Maria Santos', 'maria@acb.com', generate_password_hash('5678'), 'operador', '5678', 1))
        
        conn.commit()
        print("Migração SQLite concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro na migração SQLite: {e}")
        conn.rollback()
    finally:
        conn.close()

def migrate_postgresql():
    """Migração para PostgreSQL/Supabase"""
    print("Migrando banco PostgreSQL...")
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL não encontrada")
        return
        
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verificar se coluna codigo_operador existe
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='usuario' AND column_name='codigo_operador'
        """)
        
        if not cursor.fetchone():
            print("Adicionando coluna codigo_operador à tabela usuario...")
            cursor.execute('ALTER TABLE usuario ADD COLUMN codigo_operador VARCHAR(4) UNIQUE')
            
        # Criar tabela apontamento_producao se não existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS apontamento_producao (
                id SERIAL PRIMARY KEY,
                ordem_servico_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                codigo_operador VARCHAR(4) NOT NULL,
                item_trabalho_id INTEGER,
                tipo_acao VARCHAR(50) NOT NULL,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                quantidade INTEGER,
                motivo_parada TEXT,
                observacoes TEXT,
                FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
                FOREIGN KEY (usuario_id) REFERENCES usuario (id)
            )
        ''')
        
        # Criar tabela status_producao_os se não existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status_producao_os (
                id SERIAL PRIMARY KEY,
                ordem_servico_id INTEGER UNIQUE NOT NULL,
                status_atual VARCHAR(50) NOT NULL,
                operador_atual VARCHAR(100),
                ultimo_apontamento_id INTEGER,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
                FOREIGN KEY (ultimo_apontamento_id) REFERENCES apontamento_producao (id)
            )
        ''')
        
        # Inserir operadores de teste se não existirem
        cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
        result = cursor.fetchone()
        if result[0] == 0:
            print("Inserindo operadores de teste...")
            
            # Verificar se usuários já existem
            cursor.execute("SELECT id FROM usuario WHERE email = 'joao@acb.com'")
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', ('João Silva', 'joao@acb.com', generate_password_hash('1234'), 'operador', '1234', True))
            
            cursor.execute("SELECT id FROM usuario WHERE email = 'maria@acb.com'")
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO usuario (nome, email, senha_hash, nivel_acesso, codigo_operador, acesso_kanban)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', ('Maria Santos', 'maria@acb.com', generate_password_hash('5678'), 'operador', '5678', True))
        
        conn.commit()
        print("Migração PostgreSQL concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro na migração PostgreSQL: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Executa a migração apropriada baseada na configuração"""
    database_url = os.environ.get('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        migrate_postgresql()
    else:
        migrate_sqlite()
    
    print("Migração do módulo de apontamento concluída!")

if __name__ == '__main__':
    main()
