#!/usr/bin/env python3
"""
Script de migração para adicionar suporte a Itens Compostos no PostgreSQL (Supabase)
Adiciona:
- Coluna 'eh_composto' na tabela 'item'
- Coluna 'data_criacao' na tabela 'item'
- Nova tabela 'item_composto' para relacionamentos
"""

import os
import psycopg2
from urllib.parse import urlparse
from datetime import datetime

def load_env_file():
    """Carrega variáveis de ambiente do arquivo .env"""
    env_path = '.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("✅ Arquivo .env carregado")
    else:
        print("⚠️  Arquivo .env não encontrado")

def get_database_connection():
    """Obtém conexão com o banco PostgreSQL a partir da DATABASE_URL"""
    
    # Tentar obter DATABASE_URL do ambiente
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL não encontrada nas variáveis de ambiente")
        print("   Configure a DATABASE_URL no arquivo .env")
        return None
    
    try:
        # Parse da URL do banco
        url = urlparse(database_url)
        
        # Conectar ao PostgreSQL
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            database=url.path[1:],  # Remove a barra inicial
            user=url.username,
            password=url.password
        )
        
        print(f"✅ Conectado ao PostgreSQL: {url.hostname}:{url.port}/{url.path[1:]}")
        return conn
        
    except Exception as e:
        print(f"❌ Erro ao conectar ao PostgreSQL: {str(e)}")
        return None

def migrate_database():
    """Executa a migração do banco de dados PostgreSQL"""
    
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        print("🔄 Iniciando migração para Itens Compostos no PostgreSQL...")
        
        # 1. Verificar se as colunas já existem
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'item' AND table_schema = 'public'
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Colunas existentes na tabela 'item': {', '.join(existing_columns)}")
        
        # 2. Adicionar coluna eh_composto se não existir
        if 'eh_composto' not in existing_columns:
            cursor.execute("ALTER TABLE item ADD COLUMN eh_composto BOOLEAN DEFAULT FALSE")
            print("✅ Coluna 'eh_composto' adicionada à tabela 'item'")
        else:
            print("⚠️  Coluna 'eh_composto' já existe na tabela 'item'")
        
        # 3. Adicionar coluna data_criacao se não existir
        if 'data_criacao' not in existing_columns:
            cursor.execute("ALTER TABLE item ADD COLUMN data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("✅ Coluna 'data_criacao' adicionada à tabela 'item'")
        else:
            print("⚠️  Coluna 'data_criacao' já existe na tabela 'item'")
        
        # 4. Verificar se a tabela item_composto já existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'item_composto'
            )
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            # 5. Criar tabela item_composto
            cursor.execute("""
                CREATE TABLE item_composto (
                    id SERIAL PRIMARY KEY,
                    item_pai_id INTEGER NOT NULL,
                    item_componente_id INTEGER NOT NULL,
                    quantidade INTEGER NOT NULL DEFAULT 1,
                    observacoes TEXT,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_pai_id) REFERENCES item (id) ON DELETE CASCADE,
                    FOREIGN KEY (item_componente_id) REFERENCES item (id) ON DELETE CASCADE,
                    UNIQUE(item_pai_id, item_componente_id)
                )
            """)
            print("✅ Tabela 'item_composto' criada")
        else:
            print("⚠️  Tabela 'item_composto' já existe")
        
        # 6. Atualizar itens existentes sem data_criacao
        cursor.execute("""
            UPDATE item 
            SET data_criacao = CURRENT_TIMESTAMP 
            WHERE data_criacao IS NULL
        """)
        
        updated_rows = cursor.rowcount
        if updated_rows > 0:
            print(f"✅ Atualizados {updated_rows} itens com data_criacao")
        
        # Commit das alterações
        conn.commit()
        
        # 7. Verificar se as alterações foram aplicadas
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'item' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        colunas_item = cursor.fetchall()
        
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'item_composto' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        colunas_item_composto = cursor.fetchall()
        
        print("\n📊 Verificação das alterações:")
        print("   Tabela 'item':")
        for col in colunas_item:
            if col[0] in ['eh_composto', 'data_criacao']:
                print(f"     ✅ {col[0]} ({col[1]}) - Nullable: {col[2]} - Default: {col[3]}")
        
        print("   Tabela 'item_composto':")
        for col in colunas_item_composto:
            print(f"     ✅ {col[0]} ({col[1]}) - Nullable: {col[2]}")
        
        # 8. Verificar se as colunas necessárias existem
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'item' AND table_schema = 'public'
            AND column_name IN ('eh_composto', 'data_criacao')
        """)
        
        new_columns = [row[0] for row in cursor.fetchall()]
        
        if len(new_columns) < 2:
            missing = set(['eh_composto', 'data_criacao']) - set(new_columns)
            print(f"❌ Colunas faltantes na tabela 'item': {', '.join(missing)}")
            return False
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'item_composto'
            )
        """)
        
        if not cursor.fetchone()[0]:
            print("❌ Tabela 'item_composto' não foi criada")
            return False
        
        print("\n✅ Migração concluída com sucesso!")
        print("   - Suporte a Itens Compostos adicionado ao PostgreSQL")
        print("   - Banco de dados atualizado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante a migração: {str(e)}")
        conn.rollback()
        return False
    
    finally:
        if conn:
            conn.close()

def check_environment():
    """Verifica se o ambiente está configurado corretamente"""
    print("🔍 Verificando configuração do ambiente...")
    
    # Verificar se DATABASE_URL existe
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL não encontrada")
        print("   Certifique-se de que o arquivo .env está configurado")
        return False
    
    # Verificar se é PostgreSQL
    if not database_url.startswith('postgresql://') and not database_url.startswith('postgres://'):
        print("❌ DATABASE_URL não é PostgreSQL")
        print(f"   URL atual: {database_url[:20]}...")
        return False
    
    print("✅ Ambiente configurado corretamente")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("MIGRAÇÃO: SUPORTE A ITENS COMPOSTOS - POSTGRESQL")
    print("=" * 70)
    
    # Carregar arquivo .env
    load_env_file()
    
    # Verificar ambiente
    if not check_environment():
        print("\n💥 Falha na verificação do ambiente!")
        print("   Configure o DATABASE_URL no arquivo .env")
        exit(1)
    
    # Executar migração
    success = migrate_database()
    
    if success:
        print("\n🎉 Migração executada com sucesso!")
        print("   Agora você pode:")
        print("   1. Reiniciar a aplicação Flask")
        print("   2. Cadastrar itens compostos")
        print("   3. Gerar OS que desmembram automaticamente")
        print("   4. Usar o sistema Kanban com itens compostos")
    else:
        print("\n💥 Falha na migração!")
        print("   Verifique os erros acima e tente novamente")
        print("   Se o problema persistir, verifique:")
        print("   - Credenciais do banco de dados")
        print("   - Permissões de escrita no banco")
        print("   - Conectividade com o Supabase")
    
    print("=" * 70)
